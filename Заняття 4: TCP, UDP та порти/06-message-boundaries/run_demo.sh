#!/usr/bin/env bash
# Живе демо: межі повідомлень. UDP їх зберігає, TCP (потік байтів) — ні.
# Використання:  ./run_demo.sh                  (усі сценарії по черзі)
#                ./run_demo.sh tcp framed       (лише вибрані: udp tcp big framed)
#                PYTHON=python3.12 ./run_demo.sh
# Порти: 9106/udp і 9116/tcp (змінні UDP_PORT, TCP_PORT).
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
UDP_PORT="${UDP_PORT:-9106}"
TCP_PORT="${TCP_PORT:-9116}"
TMP="$(mktemp -d)"
RECV_PID=""

cleanup() {
    if [ -n "$RECV_PID" ]; then kill "$RECV_PID" 2> /dev/null || true; fi
    rm -rf "$TMP"
}
trap cleanup EXIT

# Чекаємо рядок «слухає» від приймача (bind/listen зроблено), максимум 10 с.
# Без цього перша UDP-дейтаграма може піти «в нікуди» — і зникнути без помилки.
wait_ready() {
    for _ in $(seq 100); do
        grep -q 'слухає' "$1" 2> /dev/null && return 0
        sleep 0.1
    done
    echo "Приймач не запустився:"; cat "$1"; exit 1
}

# Один сценарій: приймач у фоні (вивід у файл), відправник на передньому плані,
# потім вивід приймача, щоб рядки двох програм не перемішувалися.
scenario() {
    local title="$1" recv_args="$2" send_args="$3"
    echo
    echo "=================================================================="
    echo "$title"
    echo "=================================================================="
    # shellcheck disable=SC2086  # аргументи навмисно розбиваються на слова
    "$PY" -u receiver.py $recv_args > "$TMP/recv.txt" 2>&1 &
    RECV_PID=$!
    wait_ready "$TMP/recv.txt"
    echo "--- відправник: python3 sender.py $send_args"
    # shellcheck disable=SC2086
    "$PY" -u sender.py $send_args
    wait "$RECV_PID"
    RECV_PID=""
    echo "--- приймач: python3 receiver.py $recv_args"
    cat "$TMP/recv.txt"
}

run_udp() {
    scenario "1. UDP: 3 × sendto() підряд -> скільки recvfrom()?" \
        "udp --port $UDP_PORT" "udp --port $UDP_PORT"
    echo
    echo "--- 1б. Той самий відправник, але приймача НЕМАЄ:"
    "$PY" -u sender.py udp --port "$UDP_PORT"
    echo "(жодної помилки: дейтаграми просто зникли)"
}
run_tcp() {
    scenario "2. TCP: 3 × send() підряд -> скільки recv()? (злиття)" \
        "tcp --port $TCP_PORT --delay 0.5" "tcp --port $TCP_PORT"
}
run_big() {
    scenario "3. TCP: ОДИН send() на 1 МБ -> скільки recv()? (розрізання)" \
        "tcp --port $TCP_PORT --delay 0 --bufsize 1000000" "big --port $TCP_PORT"
    echo "(розміри шматків щоразу інші — і саме це головне)"
}
run_framed() {
    scenario "4. Виправлення: префікс довжини (4 байти) перед кожним повідомленням" \
        "framed --port $TCP_PORT --delay 0.5" "framed --port $TCP_PORT"
    scenario "4б. Префікс довжини + ще одне повідомлення на 1 МБ (розрізане на шматки)" \
        "framed --port $TCP_PORT --delay 0 --bufsize 1000000" "framed --plus-big --port $TCP_PORT"
}

if [ "$#" -eq 0 ]; then set -- udp tcp big framed; fi
for s in "$@"; do
    case "$s" in
        udp | tcp | big | framed) "run_$s" ;;
        *) echo "Невідомий сценарій: $s (є: udp tcp big framed)"; exit 1 ;;
    esac
done
