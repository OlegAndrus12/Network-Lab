#!/usr/bin/env bash
# Живе демо: ретрансляції TCP при 5% втрат. Linux-частина (tc netem, tcpdump, tshark)
# працює в Docker-контейнері, тож однаково запускається на macOS і Linux, без sudo.
# Використання:  ./run_demo.sh                     (5% втрат, 2 МБ, SACK увімкнено)
#                LOSS=10% ./run_demo.sh            (більше втрат)
#                SACK=0 ./run_demo.sh              (без SACK: класичні дублі ACK)
#                SIZE_KB=4096 MTU=65536 ./run_demo.sh
# Результат: capture.pcap у цій теці, відкрийте його у Wireshark.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=demo02-retrans
NAME=demo02-retrans
SACK="${SACK:-1}"

command -v docker > /dev/null || { echo "Потрібен Docker (Docker Desktop на macOS)"; exit 1; }

# 1. Образ будуємо один раз (~1 хв, потрібен інтернет). Зробіть це ДО пари!
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "=== Будую образ $IMAGE (один раз) ==="
    docker build -q -t "$IMAGE" .
fi
docker rm -f "$NAME" > /dev/null 2>&1 || true

# 2. Контейнер: свій мережевий простір, тому lo, netem і лічильники ядра не чіпають хост.
#    NET_ADMIN потрібен для tc та ip link; SACK вмикається/вимикається через --sysctl.
docker run --rm --name "$NAME" --cap-add NET_ADMIN \
    --sysctl "net.ipv4.tcp_sack=$SACK" \
    -e LOSS -e DELAY -e MTU -e SIZE_KB -e PCAP -e PORT \
    -v "$PWD":/demo "$IMAGE" ./inside.sh

echo
echo "Готово: $(pwd)/${PCAP:-capture.pcap}"
if [ "$(uname)" = "Darwin" ]; then
    echo "Відкрити у Wireshark:  open -a Wireshark ${PCAP:-capture.pcap}"
else
    echo "Відкрити у Wireshark:  wireshark ${PCAP:-capture.pcap} &"
fi
