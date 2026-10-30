#!/usr/bin/env bash
# Живе демо «zero window»: лінивий сервер не читає, вікно падає до 0, send() клієнта зависає.
# Використання:  ./run_demo.sh                          (сервер «прокинеться» через 10 с)
#                READ_AFTER=0 ./run_demo.sh             (сервер не читає ніколи, клієнт здається через 8 с)
#                RCVBUF=16384 SNDBUF=16384 ./run_demo.sh (малі буфери: менші числа, швидше)
#                PORT=9111 ./run_demo.sh                (інший порт)
#                ./run_demo.sh --chunk 4096             (аргументи йдуть у client.py)
# tcpdump: Linux від root (Docker: ./docker_demo.sh) або macOS з доступом до /dev/bpf;
#          CAPTURE=sudo ./run_demo.sh  запустить tcpdump через sudo; CAPTURE=0 вимикає захоплення.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-9101}"
READ_AFTER="${READ_AFTER:-10}"   # через скільки секунд сервер почне recv()
RCVBUF="${RCVBUF:-0}"             # 0 = розмір буфера як у системі
SNDBUF="${SNDBUF:-0}"
TOTAL="${TOTAL:-8000000}"         # скільки всього шле клієнт
SNAP_AT="${SNAP_AT:-4}"           # коли показати таблицю сокетів (ss / netstat)
DELAY="${DELAY:-}"                # напр. 50ms: затримка netem на lo (лише Linux, root)
FILTER="tcp port $PORT"

if [ "$(uname)" = "Darwin" ]; then IFACE=lo0; else IFACE=lo; fi

# 1. Чи можемо запустити tcpdump?
SUDO=""
CAPTURE="${CAPTURE:-auto}"
if [ "$CAPTURE" = auto ]; then
    if command -v tcpdump > /dev/null && { [ "$(id -u)" -eq 0 ] || { [ "$IFACE" = lo0 ] && [ -r /dev/bpf0 ]; }; }; then
        CAPTURE=1
    else
        CAPTURE=0
        echo "(tcpdump пропущено: потрібен root. Варіанти: ./docker_demo.sh або CAPTURE=sudo ./run_demo.sh)"
    fi
elif [ "$CAPTURE" = sudo ]; then
    SUDO=sudo; CAPTURE=1; sudo -v
fi

PIDS=()
cleanup() {
    for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2> /dev/null || true; done
    if [ -n "${TCPD_PID:-}" ]; then
        $SUDO pkill -INT -f "tcpdump -i $IFACE -n -s 128" 2> /dev/null || true
        sleep 0.3
    fi
    if [ -n "$DELAY" ]; then tc qdisc del dev lo root 2> /dev/null || true; fi
    wait 2> /dev/null || true
}
trap cleanup EXIT

# 2. Необов'язково: штучна затримка на loopback (видно, що інтервал проб залежить від RTT)
if [ -n "$DELAY" ]; then
    tc qdisc add dev lo root netem delay "$DELAY"
    echo "=== netem: затримка $DELAY на lo (в кожен бік) ==="
fi

# 3. Захоплення трафіку
if [ "$CAPTURE" = 1 ]; then
    rm -f capture.txt capture.pcap tcpdump.log
    # два tcpdump: текст із часом від першого пакета (-ttttt) і pcap для Wireshark.
    # -s 128: лише заголовки; -B: великий буфер, щоб ядро не відкидало пакети,
    # коли вікно відкриється і дані поллються потоком
    $SUDO tcpdump -i "$IFACE" -n -s 128 -B 8192 -ttttt -l "$FILTER" < /dev/null > capture.txt 2>> tcpdump.log &
    $SUDO tcpdump -i "$IFACE" -n -s 128 -B 8192 -U -w capture.pcap "$FILTER" < /dev/null 2>> tcpdump.log &
    TCPD_PID=$!
    for _ in $(seq 50); do
        [ "$(grep -c 'listening on' tcpdump.log 2> /dev/null)" -ge 2 ] && break
        sleep 0.1
    done
    sleep 0.3
    echo "=== tcpdump на $IFACE ('$FILTER'): на екрані лише рядки з win 0 і проби ==="
    # $! = PID саме tail (а не python), щоб у кінці зупинити його напевно
    tail -n +1 -f capture.txt > >(python3 annotate.py --live --port "$PORT") &
    PIDS+=($!)
    disown $!  # без повідомлення «Terminated», коли зупинимо tail у кінці
fi

# 4. Сервер (не читає READ_AFTER секунд), потім клієнт
python3 server.py --port "$PORT" --rcvbuf "$RCVBUF" --read-after "$READ_AFTER" &
SERVER_PID=$!
PIDS+=("$SERVER_PID")
sleep 0.5
if ! kill -0 "$SERVER_PID" 2> /dev/null; then
    echo "Сервер не запустився (порт $PORT зайнятий?). Перевірте: lsof -nP -iTCP:$PORT"
    exit 1
fi
GIVE_UP=0
[ "$READ_AFTER" = 0 ] && GIVE_UP=8  # якщо сервер не читає ніколи, клієнт мусить здатися
python3 client.py --port "$PORT" --sndbuf "$SNDBUF" --total "$TOTAL" --give-up "$GIVE_UP" "$@" &
CLIENT_PID=$!
PIDS+=("$CLIENT_PID")

# 5. Поки клієнт «замерз»: таблиця сокетів (Recv-Q у сервера, Send-Q у клієнта)
sleep "$SNAP_AT"
echo
if command -v ss > /dev/null; then
    echo "=== ss -tn (Linux) ==="
    ss -tn "( sport = :$PORT or dport = :$PORT )"
else
    echo "=== netstat -an -p tcp (macOS) ==="
    netstat -an -p tcp | grep -E "Proto|[.:]$PORT " || true
fi
echo

wait "$CLIENT_PID"
if [ "$READ_AFTER" = 0 ]; then kill "$SERVER_PID" 2> /dev/null || true; fi
wait "$SERVER_PID" 2> /dev/null || true
sleep 1  # даємо останнім сегментам потрапити в захоплення

if [ "$CAPTURE" = 1 ]; then
    trap - EXIT
    cleanup
    echo
    echo "=== Пояснений вивід (capture.txt; для Wireshark: capture.pcap) ==="
    python3 annotate.py --port "$PORT" capture.txt
fi
