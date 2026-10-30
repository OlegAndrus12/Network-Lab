#!/usr/bin/env bash
# Те саме демо в Linux-контейнері (ss, nstat, tcpdump без sudo на macOS).
# Використання:  ./run_docker.sh            звичайний режим: зайві клієнти в SYN-SENT
#                ./run_docker.sh cookies    затримка 50 мс на lo (netem) + одночасні connect():
#                                           зайві клієнти «ESTABLISHED», а сервер про них не знає
#                SYNCOOKIES=0 ./run_docker.sh cookies   те саме, але з вимкненими SYN cookies
# Змінні N, BACKLOG, AUTO, ACCEPT_DELAY, DRAIN передаються в run_demo.sh.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=demo07-backlog
docker image inspect "$IMAGE" > /dev/null 2>&1 || docker build -q -t "$IMAGE" .

MODE="${1:-plain}"
PREP="true"
ENVS=()
if [ "$MODE" = cookies ]; then
    PREP="tc qdisc add dev lo root netem delay 50ms"
    ENVS+=(-e GAP=0)
fi
for v in N BACKLOG AUTO ACCEPT_DELAY DRAIN WAIT; do
    if [ -n "${!v:-}" ]; then ENVS+=(-e "$v=${!v}"); fi
done
TTY=(); if [ -t 0 ]; then TTY=(-it); fi

docker run --rm ${TTY[@]+"${TTY[@]}"} --name demo07-run \
    --cap-add NET_ADMIN --cap-add NET_RAW \
    --sysctl "net.ipv4.tcp_syncookies=${SYNCOOKIES:-1}" \
    ${ENVS[@]+"${ENVS[@]}"} -v "$PWD":/demo "$IMAGE" \
    bash -c "$PREP && echo \"Linux \$(uname -r), tcp_syncookies=\$(sysctl -n net.ipv4.tcp_syncookies), tcp_abort_on_overflow=\$(sysctl -n net.ipv4.tcp_abort_on_overflow)\" && ./run_demo.sh"
