#!/usr/bin/env bash
# Живе демо: надійність поверх UDP. Сирий UDP губить, дублює й переставляє пакети;
# номери + ACK + таймер повтору + ковзне вікно це виправляють (як TCP і QUIC).
# Втрати додає netem, а він є лише в Linux, тому сценарії працюють у Docker-контейнері.
#
# Використання:
#   ./run_demo.sh                         # усі сценарії: naive saw window tcp
#   ./run_demo.sh naive window            # лише вибрані
#   LOSS=20% DELAY=25ms ./run_demo.sh     # інші параметри netem (також DUP, REORDER)
#   ./run_demo.sh shell                   # контейнер у фоні для ручного режиму (2 термінали)
#   ./run_demo.sh stop                    # зупинити контейнер ручного режиму
#   NO_DOCKER=1 ./run_demo.sh             # без Docker і без netem (macOS): нічого не губиться
# Порти: 9109/udp і 9119/tcp (змінні UDP_PORT, TCP_PORT).
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=demo09-reliable-udp
NAME=demo09-reliable-udp
LOSS="${LOSS:-10%}"
DELAY="${DELAY:-25ms}"
DUP="${DUP:-5%}"
REORDER="${REORDER:-25%}"
# затримка в кожному напрямку => RTT = 2 × DELAY; reorder: частина пакетів іде без затримки й обганяє інших.
# MTU 1500 як в Ethernet/інтернеті: інакше на lo (MTU 65536) TCP віддає всі 10 КБ одним сегментом.
NETEM="ip link set lo mtu 1500 && tc qdisc add dev lo root netem delay $DELAY loss $LOSS duplicate $DUP reorder $REORDER"

PY="${PYTHON:-python3}"
UDP_PORT="${UDP_PORT:-9109}"
TCP_PORT="${TCP_PORT:-9119}"

# 1. Хост (macOS або Linux без root): усе робимо в контейнері, де можна ввімкнути netem
if [ "${NO_DOCKER:-0}" != 1 ] && [ "${INSIDE:-0}" != 1 ]; then
    if [ "${1:-}" = stop ]; then
        docker rm -f "$NAME" > /dev/null 2>&1 || true
        echo "Контейнер $NAME зупинено"
        exit 0
    fi
    docker build -q -t "$IMAGE" . > /dev/null  # будується один раз, далі з кешу
    if [ "${1:-}" = shell ]; then
        docker rm -f "$NAME" > /dev/null 2>&1 || true
        docker run -d --rm --cap-add NET_ADMIN --name "$NAME" "$IMAGE" sleep infinity > /dev/null
        docker exec "$NAME" sh -c "$NETEM"
        echo "Контейнер $NAME запущено, netem: $(docker exec "$NAME" tc qdisc show dev lo)"
        echo
        echo "Термінал 1 (приймач):     docker exec -it $NAME python3 receiver.py reliable"
        echo "Термінал 2 (відправник):  docker exec -it $NAME python3 sender.py window"
        echo "Сирий UDP:                receiver.py naive  +  sender.py naive"
        echo "Захоплення пакетів:       docker exec -it $NAME tcpdump -i lo -n -tttt 'udp port $UDP_PORT'"
        echo "Наприкінці:               ./run_demo.sh stop"
        exit 0
    fi
    echo "=== Docker (Linux), netem на lo: delay $DELAY loss $LOSS duplicate $DUP reorder $REORDER ==="
    exec docker run --rm -i --cap-add NET_ADMIN --name "$NAME-run" -e INSIDE=1 \
        -e UDP_PORT="$UDP_PORT" -e TCP_PORT="$TCP_PORT" "$IMAGE" \
        sh -c "$NETEM && bash run_demo.sh $*"
fi

# 2. Далі — всередині контейнера (або NO_DOCKER=1): самі сценарії
TMP="$(mktemp -d)"
RECV_PID=""

cleanup() {
    if [ -n "$RECV_PID" ]; then kill "$RECV_PID" 2> /dev/null || true; fi
    rm -rf "$TMP"
}
trap cleanup EXIT

# Чекаємо рядок «слухає» від приймача (bind зроблено), максимум 10 с.
# Без цього перші дейтаграми можуть піти «в нікуди» — і зникнути без помилки.
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

run_naive() {
    scenario "1. Сирий UDP: 100 × sendto() -> що дійшло?" \
        "naive --port $UDP_PORT" "naive --port $UDP_PORT"
}
run_saw() {
    scenario "2. Stop-and-wait: номер + ACK + таймер повтору (надійно, але повільно)" \
        "reliable --port $UDP_PORT" "saw --port $UDP_PORT"
}
run_window() {
    scenario "3. Ковзне вікно на 16 пакетів: надійно і швидко" \
        "reliable --port $UDP_PORT" "window --window 16 --port $UDP_PORT"
}
run_tcp() {
    scenario "4. Те саме через TCP: усе це робить ядро" \
        "tcp --port $TCP_PORT" "tcp --port $TCP_PORT"
}

if [ "$#" -eq 0 ]; then set -- naive saw window tcp; fi
for s in "$@"; do
    case "$s" in
        naive | saw | window | tcp) "run_$s" ;;
        *) echo "Невідомий сценарій: $s (є: naive saw window tcp)"; exit 1 ;;
    esac
done
