#!/usr/bin/env bash
# Виконується ВСЕРЕДИНІ Linux-контейнера (див. run_demo.sh).
# Налаштовує втрати на lo, завантажує файл curl-ом з http.server і пише capture.pcap.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-9102}"
LOSS="${LOSS:-5%}"        # частка втрачених пакетів (netem)
DELAY="${DELAY:-5ms}"     # затримка в кожен бік, RTT = 2 × DELAY
MTU="${MTU:-1500}"        # як у звичайному Ethernet (замість 65536 на lo)
SIZE_KB="${SIZE_KB:-2048}"  # 2 МБ: майже завжди є і швидкі повтори, і хоча б один RTO
PCAP="${PCAP:-capture.pcap}"

echo "=== 1. Налаштування lo: MTU $MTU, без TSO/GSO/GRO, netem delay $DELAY loss $LOSS ==="
ip link set lo mtu "$MTU"
# без цього ядро віддає tcpdump «склеєні» сегменти по 64 КБ замість 1448 байтів
ethtool -K lo tso off gso off gro off 2> /dev/null || true
# TCP однаково складає кілька сегментів в один буфер (до 64 КБ), а netem стоїть ДО поділу
# на сегменти й губить буфер цілком: замість 5% поодиноких втрат були б «пачки» по 2–20.
# gso_max_segs 1 = один сегмент на буфер, тож кожен сегмент губиться незалежно.
ip link set lo gso_max_segs 1 2> /dev/null || echo "  (не вдалося задати gso_max_segs: втрати будуть пачками)"
tc qdisc replace dev lo root netem delay "$DELAY" loss "$LOSS"
tc qdisc show dev lo
echo "SACK увімкнено: $(sysctl -n net.ipv4.tcp_sack) (1 = так, 0 = ні)"

# 2. Файл для завантаження і HTTP-сервер на порту $PORT
mkdir -p /srv
head -c "$((SIZE_KB * 1024))" /dev/urandom > /srv/file.bin
(cd /srv && exec python3 -m http.server "$PORT" --bind 127.0.0.1 > /dev/null 2>&1) &
SERVER_PID=$!
# чекаємо стан LISTEN (через ss, щоб не створювати зайвого трафіку)
for _ in $(seq 50); do ss -ltn "sport = :$PORT" | grep -q LISTEN && break; sleep 0.1; done

# 3. Захоплення: tcpdump пише pcap для Wireshark
rm -f "$PCAP"
tcpdump -i lo -n -U -B 32768 -w "$PCAP" "tcp port $PORT" 2> tcpdump.log &
TCPDUMP_PID=$!
for _ in $(seq 50); do grep -q 'listening on' tcpdump.log 2> /dev/null && break; sleep 0.1; done

echo
echo "=== 2. curl завантажує ${SIZE_KB} КБ з http://127.0.0.1:$PORT/file.bin ==="
nstat -n  # обнуляємо лічильники ядра (вони свої для мережевого простору контейнера)
curl -sS -o /dev/null -w "отримано %{size_download} байтів за %{time_total} с\n" \
    "http://127.0.0.1:$PORT/file.bin"
sleep 0.5

kill -INT "$TCPDUMP_PID"; wait "$TCPDUMP_PID" 2> /dev/null || true
kill "$SERVER_PID" 2> /dev/null || true
# tcpdump сам каже, чи встиг усе записати; "0 packets dropped by kernel" = захоплення повне
grep -E "captured|dropped by kernel" tcpdump.log | sed 's/^/  tcpdump: /'
if ! grep -q "^0 packets dropped by kernel" tcpdump.log; then
    echo "  УВАГА: tcpdump пропустив пакети, pcap неповний. Запустіть ще раз."
fi
rm -f tcpdump.log

echo
echo "=== 3. Що порахувало саме ядро (nstat, лічильники відправника і отримувача разом) ==="
nstat -z 2> /dev/null | awk '
    $1=="TcpRetransSegs"        {print "  " $1 "\t" $2 "\tусього повторно надісланих сегментів"}
    $1=="TcpExtTCPFastRetrans"  {print "  " $1 "\t" $2 "\tшвидкі повтори (за дубльованими ACK / SACK)"}
    $1=="TcpExtTCPTimeouts"     {print "  " $1 "\t" $2 "\tспрацювань таймера RTO"}
    $1=="TcpExtTCPSynRetrans"   {print "  " $1 "\t" $2 "\tз них повторів SYN / SYN-ACK"}
    $1=="TcpExtTCPLossProbes"   {print "  " $1 "\t" $2 "\tзонди втрати хвоста (TLP)"}
    $1=="TcpExtTCPSackRecovery" {print "  " $1 "\t" $2 "\tепізоди відновлення з SACK"}
    $1=="TcpExtTCPRenoRecovery" {print "  " $1 "\t" $2 "\tепізоди відновлення без SACK (Reno)"}
' | sort

if [ "${LOSS%\%}" != 0 ] && [ "$(nstat -az TcpExtTCPTimeouts | awk '/Timeouts/ {print $2}')" = 0 ]; then
    echo "  (RTO цього разу не спрацював: втрати випадкові. Повторіть або LOSS=10%)"
fi

echo
echo "=== 4. Що побачить Wireshark у $PCAP ==="
python3 analyze.py "$PCAP"
