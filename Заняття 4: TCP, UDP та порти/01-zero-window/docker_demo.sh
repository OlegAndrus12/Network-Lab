#!/usr/bin/env bash
# Те саме демо в Linux-контейнері: tcpdump, ss і tc без sudo на хості (macOS/Linux).
# Використання:  ./docker_demo.sh                    (аргументи йдуть у client.py)
#                READ_AFTER=0 RCVBUF=16384 ./docker_demo.sh
#                DELAY=50ms ./docker_demo.sh          (затримка netem на lo в контейнері)
# Перший запуск збирає образ demo01-zero-window (потрібен інтернет для apt-get).
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=demo01-zero-window
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
    echo "=== Збираю образ $IMAGE ==="
    docker build -q -t "$IMAGE" .
fi

# змінні середовища передаються в контейнер, лише якщо задані
ENV_ARGS=()
for v in PORT READ_AFTER RCVBUF SNDBUF TOTAL SNAP_AT DELAY CAPTURE; do
    if [ -n "${!v:-}" ]; then ENV_ARGS+=(-e "$v=${!v}"); fi
done

TTY=()
[ -t 1 ] && TTY=(-t)  # -t лише якщо ми в терміналі (Ctrl+C працює)
# NET_ADMIN потрібен лише для DELAY (tc netem); результати (capture.*) з'являться в цій теці
docker run --rm ${TTY[@]+"${TTY[@]}"} --name demo01-zero-window --cap-add NET_ADMIN \
    -v "$PWD":/demo -w /demo ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} "$IMAGE" ./run_demo.sh "$@"
