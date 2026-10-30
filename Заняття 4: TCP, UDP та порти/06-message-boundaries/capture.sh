#!/usr/bin/env bash
# Linux (Docker або root): tcpdump на lo під час сценарію «3 × send() -> 1 recv()».
# Показує, що на дроті було 3 сегменти, а злиття сталося в буфері прийому.
# Друге проходження — з увімкненим Нейглом (--nagle): тоді частину send зливає вже відправник.
# На loopback ACK приходить за мікросекунди, тож Нейгл майже не має чого чекати.
# NETEM=50ms ./capture.sh додає затримку на lo (tc netem, потрібен --cap-add NET_ADMIN),
# і тоді Нейгл помітно зливає 2-й і 3-й send в один сегмент.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
PORT="${TCP_PORT:-9116}"
TMP="$(mktemp -d)"
if [ "$(uname)" = "Darwin" ]; then IFACE=lo0; else IFACE=lo; fi

cleanup() {
    if [ -n "${NETEM:-}" ]; then tc qdisc del dev "$IFACE" root 2> /dev/null || true; fi
    rm -rf "$TMP"
}
trap cleanup EXIT

if [ -n "${NETEM:-}" ]; then
    # затримка в кожному напрямку => RTT = 2 × NETEM
    tc qdisc replace dev "$IFACE" root netem delay "$NETEM"
    echo "tc netem: затримка $NETEM на $IFACE (RTT = 2 × $NETEM)"
fi

one_run() {
    local label="$1"; shift
    echo
    echo "=================================================================="
    echo "$label"
    echo "=================================================================="
    tcpdump -i "$IFACE" -n -t -l "tcp port $PORT" > "$TMP/cap.txt" 2> "$TMP/tcpdump.log" &
    local tpid=$!
    for _ in $(seq 50); do grep -q 'listening on' "$TMP/tcpdump.log" && break; sleep 0.1; done
    "$PY" -u receiver.py tcp --port "$PORT" --delay 0.5 > "$TMP/recv.txt" &
    local rpid=$!
    for _ in $(seq 100); do grep -q 'слухає' "$TMP/recv.txt" && break; sleep 0.1; done
    "$PY" -u sender.py tcp --port "$PORT" "$@"
    wait "$rpid"
    sleep 0.5
    kill -INT "$tpid"; wait "$tpid" 2> /dev/null || true
    echo "--- на дроті (tcpdump; * = сегмент з даними):"
    sed -E 's/, options \[[^]]*\]//; /^ *$/d; s/^/   /; /length [1-9]/s/^  /* /' "$TMP/cap.txt"
    echo "    сегментів з даними: $(grep -cE 'length [1-9]' "$TMP/cap.txt")"
    echo "--- приймач:"
    grep -E 'recv #|Разом' "$TMP/recv.txt"
}

one_run "A. TCP_NODELAY=1 (Нейгл вимкнено): кожен send() -> окремий сегмент"
one_run "B. TCP_NODELAY=0 (Нейгл увімкнено): відправник може злити send() сам" --nagle
