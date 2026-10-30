#!/usr/bin/env bash
# Живе демо TCP: рукостискання, сегменти з даними, закриття з'єднання.
# Використання:  ./run_demo.sh                    (3 × 100 байтів)
#                ./run_demo.sh --count 5 --size 50  (аргументи йдуть у client.py)
#                PORT=9100 ./run_demo.sh            (інший порт)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-9000}"
FILTER="tcp port $PORT"

# 1. Інтерфейс loopback: lo0 на macOS, lo на Linux
if [ "$(uname)" = "Darwin" ]; then IFACE=lo0; else IFACE=lo; fi

# 2. tcpdump потребує sudo, якщо немає прямого доступу до /dev/bpf (macOS + Wireshark)
SUDO=sudo
if [ "$(id -u)" -eq 0 ] || { [ "$IFACE" = lo0 ] && [ -r /dev/bpf0 ]; }; then SUDO=""; fi
if [ -n "$SUDO" ]; then sudo -v; fi  # пароль запитуємо зараз, а не у фоні

# 3. Два tcpdump: текст (capture.txt) і pcap для Wireshark (capture.pcap)
rm -f capture.txt capture.pcap tcpdump.log
$SUDO tcpdump -i "$IFACE" -n -t -l "$FILTER" < /dev/null > capture.txt 2>> tcpdump.log &
TXT_PID=$!
$SUDO tcpdump -i "$IFACE" -n -U -w - "$FILTER" < /dev/null > capture.pcap 2>> tcpdump.log &
PCAP_PID=$!

stop_capture() {
    $SUDO kill -INT "$TXT_PID" "$PCAP_PID" 2> /dev/null || true
    wait "$TXT_PID" "$PCAP_PID" 2> /dev/null || true
    if [ -n "${TAIL_PID:-}" ]; then kill "$TAIL_PID"; wait "$TAIL_PID" 2> /dev/null || true; fi
}
trap stop_capture EXIT

# чекаємо, поки обидва tcpdump почнуть слухати
for _ in $(seq 50); do
    [ "$(grep -c 'listening on' tcpdump.log 2> /dev/null)" -ge 2 ] && break
    sleep 0.1
done
if [ "$(grep -c 'listening on' tcpdump.log)" -lt 2 ]; then
    echo "tcpdump не запустився:"; cat tcpdump.log; exit 1
fi

echo "=== Захоплення на $IFACE, фільтр '$FILTER' ==="
tail -n +1 -f capture.txt &  # сирий вивід tcpdump на екран у реальному часі
TAIL_PID=$!

# 4. Сервер у фоні, клієнт на передньому плані
python3 -u server.py "$PORT" &
SERVER_PID=$!
sleep 0.5
python3 -u client.py --port "$PORT" "$@"
wait "$SERVER_PID"
sleep 1  # даємо останнім сегментам потрапити в захоплення

trap - EXIT
stop_capture

# 5. Очищений і пояснений вивід
echo
echo "=== Пояснений вивід (capture.txt; для Wireshark: capture.pcap) ==="
python3 annotate.py --port "$PORT" capture.txt
