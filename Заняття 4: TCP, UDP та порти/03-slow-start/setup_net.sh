#!/usr/bin/env bash
# Налаштування мережі ВСЕРЕДИНІ контейнера (тільки Linux, потрібен NET_ADMIN).
# Не запускайте на своєму Linux-хості: затримка на lo сповільнить увесь localhost.
# Використання:  ./setup_net.sh [DELAY_MS] [MTU|default]
set -euo pipefail

DELAY_MS="${1:-100}"
MTU="${2:-1500}"

# 1. MTU як у звичайного Ethernet: MSS = 1448 байтів замість ~64 КБ на loopback
if [ "$MTU" != default ]; then ip link set dev lo mtu "$MTU"; fi

# 2. Без TSO/GSO: ядро ріже дані на сегменти по MSS одразу,
#    тож tcpdump і Wireshark бачать «справжні» пакети, а не шматки по 64 КБ
ethtool -K lo tso off gso off > /dev/null 2>&1 || echo "увага: ethtool не зміг вимкнути TSO/GSO"

# 3. Затримка: кожен пакет, що виходить через lo, чекає DELAY_MS.
#    Дані й ACK обидва проходять через lo, тому RTT = 2 × DELAY_MS.
#    limit 10000: черга netem достатньо довга, щоб сама не губила пакети
tc qdisc del dev lo root 2> /dev/null || true
tc qdisc add dev lo root netem delay "${DELAY_MS}ms" limit 10000

echo "lo: mtu $(cat /sys/class/net/lo/mtu), $(tc qdisc show dev lo | sed 's/ seed [0-9]*//')"
echo "алгоритм керування перевантаженням: $(sysctl -n net.ipv4.tcp_congestion_control)," \
     "tcp_rmem: $(sysctl -n net.ipv4.tcp_rmem | tr '\t' ' ')"
