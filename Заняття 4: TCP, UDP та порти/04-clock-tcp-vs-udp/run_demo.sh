#!/usr/bin/env bash
# Живе демо: годинник по UDP і TCP при 10% втрат («Застарілі дані гірші за втрачені»).
# Втрати додає netem, а він є лише в Linux, тому все працює в Docker-контейнері.
#
# Використання:
#   ./run_demo.sh                         # 15 с, втрати 10%, затримка 50 мс, дві колонки
#   ./run_demo.sh --duration 30           # аргументи йдуть у clock.py
#   LOSS=20% DELAY=50ms ./run_demo.sh     # інші параметри netem
#   ./run_demo.sh shell                   # контейнер у фоні для ручного режиму (2 термінали)
#   ./run_demo.sh stop                    # зупинити контейнер ручного режиму
#   NO_DOCKER=1 ./run_demo.sh             # без Docker і без втрат (macOS): нічого цікавого
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=demo04-clock
NAME=demo04-clock
LOSS="${LOSS:-10%}"
DELAY="${DELAY:-50ms}"
DELAY_MS="${DELAY%ms}"
NETEM="tc qdisc add dev lo root netem delay $DELAY loss $LOSS"

# 1. Без Docker: локальний запуск, втрат немає (для порівняння)
if [ "${NO_DOCKER:-0}" = 1 ]; then
    echo "=== Без netem: мережа нічого не губить, обидва годинники однакові ==="
    exec python3 -u clock.py "$@"
fi

if [ "${1:-}" = stop ]; then
    docker rm -f "$NAME" > /dev/null 2>&1 || true
    echo "Контейнер $NAME зупинено"
    exit 0
fi

# 2. Образ (будується один раз, далі з кешу)
docker build -q -t "$IMAGE" . > /dev/null

# 3. Ручний режим: контейнер живе у фоні, у ньому вже ввімкнено netem
if [ "${1:-}" = shell ]; then
    docker rm -f "$NAME" > /dev/null 2>&1 || true
    docker run -d --rm --cap-add NET_ADMIN --name "$NAME" "$IMAGE" sleep infinity > /dev/null
    docker exec "$NAME" sh -c "$NETEM"
    echo "Контейнер $NAME запущено, netem: $(docker exec "$NAME" tc qdisc show dev lo)"
    echo
    echo "Термінал 1 (UDP-отримувач):  docker exec -it $NAME python3 clock.py recv --proto udp"
    echo "Термінал 2 (TCP-отримувач):  docker exec -it $NAME python3 clock.py recv --proto tcp"
    echo "Термінал 3 (відправники):    docker exec -it $NAME sh -c 'python3 clock.py send --proto udp & python3 clock.py send --proto tcp; wait'"
    echo "Захоплення пакетів:          docker exec -it $NAME tcpdump -i lo -n -tttt 'tcp port 9114'"
    echo "Наприкінці:                  ./run_demo.sh stop"
    exit 0
fi

# 4. Одна команда: контейнер, netem і обидва годинники в двох колонках
TTY_FLAGS=-i
if [ -t 0 ] && [ -t 1 ]; then TTY_FLAGS=-it; fi  # кольори лише в справжньому терміналі
echo "=== Docker (Linux), netem на lo: delay $DELAY loss $LOSS ==="
docker run --rm "$TTY_FLAGS" --cap-add NET_ADMIN --name "$NAME-run" "$IMAGE" \
    sh -c "$NETEM && python3 -u clock.py --expect-delay-ms $DELAY_MS $*"
