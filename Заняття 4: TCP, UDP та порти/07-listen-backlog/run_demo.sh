#!/usr/bin/env bash
# Живе демо: сервер робить listen(backlog) і НЕ викликає accept() -> черга заповнюється.
# Використання:  ./run_demo.sh                   (5 клієнтів, backlog 2, accept() після Enter)
#                N=8 BACKLOG=3 ./run_demo.sh     (інші числа)
#                AUTO=1 ./run_demo.sh            (без Enter: accept() через ACCEPT_DELAY с)
#                PORT=9117 ./run_demo.sh         (інший порт)
# Linux у Docker (ss, tcpdump, nstat):  ./run_docker.sh
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-9107}"
N="${N:-5}"
BACKLOG="${BACKLOG:-2}"
GAP="${GAP:-0.2}"            # пауза між connect() клієнтів
WAIT="${WAIT:-1}"            # скільки клієнти чекають перед першим звітом
ACCEPT_DELAY="${ACCEPT_DELAY:-1}"
PY="${PYTHON:-python3}"
OS="$(uname)"
if [ "$OS" = Darwin ]; then IFACE=lo0; DRAIN="${DRAIN:-3}"; else IFACE=lo; DRAIN="${DRAIN:-10}"; fi

show_queue() {
    if [ "$OS" = Darwin ]; then
        echo "\$ netstat -Lan -p tcp      # qlen/incqlen/maxqlen"
        netstat -Lan -p tcp | awk -v p="\\\\.$PORT " 'NR <= 2 || $0 ~ p'
        echo "\$ netstat -an -p tcp | grep $PORT      # без TIME_WAIT від попередніх запусків"
        netstat -an -p tcp | awk -v p="\\\\.$PORT " 'NR == 2 || ($0 ~ p && !/TIME_WAIT/)'
    else
        echo "\$ ss -ltn 'sport = :$PORT'      # LISTEN: Recv-Q = черга accept, Send-Q = backlog"
        ss -ltn "sport = :$PORT"
        echo "\$ ss -tan '( sport = :$PORT or dport = :$PORT )'      # без TIME-WAIT"
        ss -tan "( sport = :$PORT or dport = :$PORT )" | grep -v TIME-WAIT
        if command -v nstat > /dev/null; then
            echo "\$ nstat -az TcpExtListenOverflows TcpExtListenDrops TcpExtSyncookiesSent TcpExtSyncookiesRecv"
            nstat -az TcpExtListenOverflows TcpExtListenDrops TcpExtSyncookiesSent TcpExtSyncookiesRecv | tail -n +2
        fi
    fi
}

# 1. tcpdump, якщо він доступний без sudo (root у Docker або група access_bpf на macOS)
CAPTURE=""
if command -v tcpdump > /dev/null && { [ "$(id -u)" -eq 0 ] || { [ "$OS" = Darwin ] && [ -r /dev/bpf0 ]; }; }; then
    CAPTURE=capture.txt
    tcpdump -i "$IFACE" -n -l "tcp port $PORT" < /dev/null > "$CAPTURE" 2> tcpdump.log &
    TD_PID=$!
    for _ in $(seq 30); do grep -q 'listening on' tcpdump.log 2> /dev/null && break; sleep 0.1; done
fi

SERVER_PID="" CLIENTS_PID=""
cleanup() {
    if [ -n "$CLIENTS_PID" ]; then kill "$CLIENTS_PID" 2> /dev/null || true; wait "$CLIENTS_PID" 2> /dev/null || true; fi
    if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2> /dev/null || true; wait "$SERVER_PID" 2> /dev/null || true; fi
    CLIENTS_PID="" SERVER_PID=""
    if [ -n "$CAPTURE" ]; then kill "$TD_PID" 2> /dev/null || true; wait "$TD_PID" 2> /dev/null || true; fi
}
trap cleanup EXIT

# 2. Сервер (accept() почнеться лише після SIGUSR1) і N клієнтів у фоні
echo "=== 1. Сервер: listen($BACKLOG), accept() не викликає ==="
"$PY" -u server.py --port "$PORT" --backlog "$BACKLOG" < /dev/null &
SERVER_PID=$!
sleep 0.5
"$PY" -u clients.py --port "$PORT" -n "$N" --gap "$GAP" --wait "$WAIT" --hold 600 &
CLIENTS_PID=$!
sleep "$(awk "BEGIN { print $GAP * $N + $WAIT + 0.3 }")"

echo
echo "=== 2. Черга, поки сервер НЕ викликає accept() ==="
show_queue

echo
if [ -t 0 ] && [ -z "${AUTO:-}" ]; then
    if [ "$OS" = Darwin ]; then
        echo "macOS: клієнти, що чекають, здаються приблизно через 6 с після першого SYN (ETIMEDOUT)."
        echo "Щоб показати, як вони заходять, натисніть Enter одразу."
    fi
    read -r -p ">>> Натисніть Enter, щоб сервер почав accept() " _
else
    sleep "$ACCEPT_DELAY"
fi
echo "=== 3. Сервер викликає accept(): черга спорожнюється (чекаю $DRAIN с) ==="
kill -USR1 "$SERVER_PID"
sleep "$DRAIN"
echo
echo "=== 4. Черга після accept() ==="
show_queue

echo
echo "=== 5. Завершення ==="
trap - EXIT
cleanup

if [ -n "$CAPTURE" ]; then
    echo
    echo "=== 6. Скільки разів кожен клієнт надіслав SYN і свої 16 байтів (tcpdump, $CAPTURE) ==="
    # >1 = повтор: сервер відкинув сегмент, бо черга accept була повна
    awk -v port="$PORT" '{ n = split($3, a, "."); p = a[n]; sub(":", "", p) }
        p != port && /Flags \[S\],/ { syn[p]++ }
        p != port && /Flags \[P\.\]/ { dat[p]++ }
        END { for (p in syn) printf "  клієнтський порт %s: SYN x%d, дані x%d%s\n", p, syn[p], dat[p],
                  (syn[p] > 1 || dat[p] > 1 ? "  <- повтори" : "") }' "$CAPTURE" | sort
fi
