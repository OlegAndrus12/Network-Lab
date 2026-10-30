#!/usr/bin/env bash
# Демо 05: закритий порт (RST, миттєво) проти порту за фаєрволом (тиша, тайм-аут).
# Використання:  ./run_demo.sh            на цьому комп'ютері (macOS або Linux): nc + probe.py
#                ./run_demo.sh docker     Linux-лабораторія: iptables DROP/REJECT, tcpdump, UDP
#                CLASSIC_BACKOFF=1 ./run_demo.sh docker   SYN-повтори 1, 2, 4 с (без лінійної фази)
#                FILTERED_HOST=10.0.0.250 ./run_demo.sh   інша «мовчазна» адреса
set -euo pipefail
cd "$(dirname "$0")"

CLOSED=9105
OPEN=9115
FILTERED_HOST="${FILTERED_HOST:-10.255.255.1}"
TIMEOUT="${TIMEOUT:-5}"

if [ "${1:-}" = "docker" ]; then
    docker build -q -t demo05-lab . > /dev/null
    EXTRA=()
    if [ -n "${CLASSIC_BACKOFF:-}" ]; then EXTRA=(--sysctl net.ipv4.tcp_syn_linear_timeouts=0); fi
    exec docker run --rm --cap-add NET_ADMIN --name demo05-lab ${EXTRA[@]+"${EXTRA[@]}"} demo05-lab
fi

# 1. nc на macOS і Linux має різні ключі тайм-ауту підключення
if [ "$(uname)" = "Darwin" ]; then
    NC_TIMEOUT=(-G "$TIMEOUT")   # на macOS -w НЕ обмежує connect(): чекатиме ~75 с
    ROUTE_IF=$(route -n get "$FILTERED_HOST" 2> /dev/null | awk '/interface:/ {print $2}')
    LO=lo0
else
    NC_TIMEOUT=(-w "$TIMEOUT")   # netcat-openbsd: -w обмежує і connect()
    ROUTE_IF=$(ip route get "$FILTERED_HOST" 2> /dev/null | grep -o 'dev [^ ]*' | cut -d' ' -f2)
    LO=lo
fi
echo "Маршрут до $FILTERED_HOST: інтерфейс ${ROUTE_IF:-немає маршруту}"
case "${ROUTE_IF:-}" in
    utun*|tun*|wg*|ppp*) echo "УВАГА: маршрут іде через VPN, «filtered» може поводитися інакше" ;;
esac

# 2. Відкритий порт (спершу перевіряємо, що обидва порти вільні)
for p in "$OPEN" "$CLOSED"; do
    if nc -z 127.0.0.1 "$p" 2> /dev/null; then
        echo "Порт $p уже хтось слухає. Подивіться: lsof -nP -iTCP:$p -sTCP:LISTEN"; exit 1
    fi
done
python3 -u open_server.py --port "$OPEN" &
SRV_PID=$!
CAP_PIDS=()
cleanup() {
    kill "$SRV_PID" 2> /dev/null || true
    for p in ${CAP_PIDS[@]+"${CAP_PIDS[@]}"}; do kill -INT "$p" 2> /dev/null || true; done
    wait 2> /dev/null || true
}
trap cleanup EXIT
for _ in $(seq 50); do nc -z 127.0.0.1 "$OPEN" 2> /dev/null && break; sleep 0.1; done

# 3. tcpdump, лише якщо він працює без пароля (macOS з групою access_bpf або root)
if [ "$(id -u)" -eq 0 ] || { [ "$LO" = lo0 ] && [ -r /dev/bpf0 ]; }; then
    rm -f capture_lo.txt capture_out.txt tcpdump.log
    tcpdump -i "$LO" -n -l -ttttt "tcp port $CLOSED or tcp port $OPEN" > capture_lo.txt 2>> tcpdump.log &
    CAP_PIDS+=($!)
    if [ -n "${ROUTE_IF:-}" ]; then
        tcpdump -i "$ROUTE_IF" -n -l -ttttt "host $FILTERED_HOST" > capture_out.txt 2>> tcpdump.log &
        CAP_PIDS+=($!)
    fi
    for _ in $(seq 50); do
        [ "$(grep -c 'listening on' tcpdump.log 2> /dev/null)" -ge "${#CAP_PIDS[@]}" ] && break
        sleep 0.1
    done
else
    echo "(tcpdump пропущено: потрібен sudo; див. explanation.html)"
fi

# 4. Секундомір: time nc для кожного випадку
TIMEFORMAT='real %3R s'
for target in "127.0.0.1 $OPEN" "127.0.0.1 $CLOSED" "$FILTERED_HOST 80"; do
    echo
    echo "\$ time nc -vz ${NC_TIMEOUT[*]} $target"
    # shellcheck disable=SC2086
    time nc -vz "${NC_TIMEOUT[@]}" $target 2>&1 || true
done

# 5. Те саме однією таблицею
echo
python3 probe.py --timeout "$TIMEOUT" "127.0.0.1:$OPEN" "127.0.0.1:$CLOSED" "$FILTERED_HOST:80"

if [ "${#CAP_PIDS[@]}" -gt 0 ]; then
    sleep 0.5
    for p in "${CAP_PIDS[@]}"; do kill -INT "$p" 2> /dev/null || true; done
    wait "${CAP_PIDS[@]}" 2> /dev/null || true
    CAP_PIDS=()
    echo
    echo "=== tcpdump -i $LO (час від першого пакета, без TCP-опцій) ==="
    sed 's/, options \[[^]]*\]//' capture_lo.txt
    if [ -s capture_out.txt ]; then
        echo "=== tcpdump -i $ROUTE_IF host $FILTERED_HOST ==="
        sed 's/, options \[[^]]*\]//' capture_out.txt
    fi
fi
