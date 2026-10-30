#!/usr/bin/env bash
# Живе демо slow start: cwnd 10 → 20 → 40 → ... за кожен RTT.
# Linux-інструменти (tc/netem, ss, tcpdump) працюють у Docker-контейнері,
# тому однаково запускається на macOS і Linux, без sudo на хості.
#
# Використання:  ./run_demo.sh                  чистий slow start: 3 МБ, затримка 100 мс, MTU 1500
#                ./run_demo.sh --loss           24 МБ: видно ще й втрату, ssthresh і повтори
#                ./run_demo.sh --size-mb 16     інший розмір «файлу»
#                ./run_demo.sh --delay 50       інша затримка (RTT = 2 × delay)
#                ./run_demo.sh --mtu default    MTU loopback 65536 (для порівняння: картина гірша)
#                ./run_demo.sh --default-rmem   стандартний tcp_rmem (для порівняння: заважає вікно отримувача)
# Результати: cwnd_table.txt (таблиця семплера) і capture.pcap (Wireshark → Stevens).
set -euo pipefail
cd "$(dirname "$0")"

PORT=9103
IMAGE=demo03-slowstart
NAME=demo03-run
SIZE_MB=3 DELAY=100 MTU=1500 RMEM="4096 4194304 6291456" INSIDE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --loss) SIZE_MB=24 ;;
        --size-mb) SIZE_MB="$2"; shift ;;
        --delay) DELAY="$2"; shift ;;
        --mtu) MTU="$2"; shift ;;
        --default-rmem) RMEM="" ;;
        --inside) INSIDE=1 ;;
        *) echo "невідомий параметр: $1"; exit 1 ;;
    esac
    shift
done

# ---------- частина 1: на хості (macOS або Linux) -> запускаємо цей самий скрипт у контейнері ----------
if [ -z "$INSIDE" ]; then
    command -v docker > /dev/null || { echo "Потрібен Docker"; exit 1; }
    if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
        echo "Збираю образ $IMAGE (один раз, ~30 с)..."
        docker build -q -t "$IMAGE" . > /dev/null
    fi
    docker rm -f "$NAME" > /dev/null 2>&1 || true
    EXTRA=()
    # tcp_rmem окремий для кожного мережевого простору імен: хост не зачіпаємо
    if [ -n "$RMEM" ]; then EXTRA=(--sysctl "net.ipv4.tcp_rmem=$RMEM"); fi
    ARGS=(--inside --size-mb "$SIZE_MB" --delay "$DELAY" --mtu "$MTU")
    if [ -z "$RMEM" ]; then ARGS+=(--default-rmem); fi
    # -t лише якщо є термінал: тоді таблиця з'являється рядок за рядком
    if [ -t 1 ]; then EXTRA+=(-t); fi
    exec docker run --rm --cap-add NET_ADMIN ${EXTRA[@]+"${EXTRA[@]}"} --name "$NAME" \
        -v "$PWD":/demo -w /demo "$IMAGE" ./run_demo.sh "${ARGS[@]}"
fi

# ---------- частина 2: всередині контейнера (Linux) ----------
echo "=== Налаштування мережі в контейнері ($(uname -sr)) ==="
./setup_net.sh "$DELAY" "$MTU"

rm -f capture.pcap cwnd_table.txt
# лічильник пакетів, відкинутих у черзі прийому (backlog) — сюди потрапляють «втрати» на lo
softnet_drops() { python3 -c "print(sum(int(l.split()[1], 16) for l in open('/proc/net/softnet_stat')))"; }
DROPS_BEFORE=$(softnet_drops)
# заголовків (96 байтів) досить для графіка Стівенса; -B: великий буфер, щоб tcpdump не губив пакети
tcpdump -i lo -n -s 96 -B 32768 -U -w capture.pcap "tcp port $PORT" 2> tcpdump.log &
TCPDUMP_PID=$!
for _ in $(seq 50); do grep -q 'listening on' tcpdump.log 2> /dev/null && break; sleep 0.1; done

python3 -u server.py --port "$PORT" --size-mb "$SIZE_MB" > server.log &
SERVER_PID=$!
sleep 0.3

echo
echo "=== Клієнт завантажує $SIZE_MB МБ з порту $PORT; таблиця cwnd з боку сервера (відправника) ==="
echo "    ss -tin кожні 20 мс; новий рядок, коли змінився cwnd, ssthresh або retrans"
# таблиця друкується наживо і водночас пишеться у файл
python3 -u sampler.py --port "$PORT" | tee cwnd_table.txt &
SAMPLER_PID=$!
sleep 0.2
python3 -u client.py --port "$PORT" > client.log
wait "$SERVER_PID" "$SAMPLER_PID"
sleep 0.5
kill -INT "$TCPDUMP_PID"; wait "$TCPDUMP_PID" 2> /dev/null || true

echo
echo "=== Клієнт ==="
cat client.log
echo
# контейнер щойно створений: лічильники TCP його мережевого простору починаються з нуля
counter() { nstat -az "$1" | awk 'NR > 1 {print $2}'; }
echo "=== Лічильники ядра за час демо ==="
echo "повторно передано сегментів (TcpRetransSegs):          $(counter TcpRetransSegs)"
echo "відкинуто в черзі прийому lo (softnet backlog drops):  $(( $(softnet_drops) - DROPS_BEFORE ))"
echo "вихід зі slow start через HyStart (train/delay):       $(counter TcpExtTCPHystartTrainDetect)/$(counter TcpExtTCPHystartDelayDetect)"
echo
echo "=== Те саме з capture.pcap: сегменти з даними, згруповані в «пачки» (пауза > 50 мс = новий RTT) ==="
# саме цю «драбину» малює Wireshark → Stevens: кожна сходинка — одне вікно cwnd
tcpdump -r capture.pcap -n -tt "src port $PORT and greater 100" 2> /dev/null | awk '
    { t = $1
      if (n == 0 || t - last > 0.05) {
          if (n) printf "  t=%6.3f с  сегментів: %5d\n", start - t0, n
          if (!t0) t0 = t
          start = t; n = 0
      }
      n++; last = t }
    END { if (n) printf "  t=%6.3f с  сегментів: %5d\n", start - t0, n }' | head -n 12
echo
echo "capture.pcap: $(tcpdump -r capture.pcap 2> /dev/null | wc -l | tr -d ' ') пакетів" \
     "($(grep -o '[0-9]* packets dropped by kernel' tcpdump.log || echo '? втрачено tcpdump'));" \
     "Wireshark → Statistics → TCP Stream Graphs → Stevens"
rm -f tcpdump.log server.log client.log
