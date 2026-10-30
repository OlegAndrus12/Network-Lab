#!/usr/bin/env bash
# Linux-частина демо 05 (запускається всередині контейнера demo05-lab, потрібен NET_ADMIN).
# Детермінований «filtered»: iptables DROP проти REJECT --reject-with tcp-reset,
# tcpdump на lo показує, що насправді літає в мережі.
set -euo pipefail
cd /demo

CLOSED=9105                    # тут ніхто не слухає
OPEN=9115                      # тут слухає open_server.py
CAPTURE_WAIT="${CAPTURE_WAIT:-8}"  # скільки чекаємо SYN-ретрансмісії при DROP, с

title() { echo; echo "=================== $* ==================="; }
# чекаємо, поки open_server.py справді почне слухати
wait_port() { for _ in $(seq 50); do ss -ln"$1" | grep -q ":$2 " && return; sleep 0.1; done; echo "сервер не стартував"; exit 1; }

# tcpdump у фоні; -ttttt = час від першого пакета (видно паузи між ретрансмісіями)
cap_start() {
    rm -f /tmp/cap.txt /tmp/cap.log
    tcpdump -i lo -n -l -ttttt "$1" > /tmp/cap.txt 2> /tmp/cap.log &
    CAP_PID=$!
    for _ in $(seq 50); do grep -q 'listening on' /tmp/cap.log 2> /dev/null && break; sleep 0.1; done
}
cap_stop() {
    sleep 0.5
    kill -INT "$CAP_PID" 2> /dev/null || true
    wait "$CAP_PID" 2> /dev/null || true
    echo "--- tcpdump -i lo ($1):"
    sed 's/, options \[[^]]*\]//' /tmp/cap.txt   # прибираємо TCP-опції, щоб рядки були коротші
}
# time для nc: друкує лише реальний час
timed_nc() {
    echo "\$ time nc $*"
    local t0 t1
    t0=$(date +%s.%N)
    local rc=0
    nc "$@" 2>&1 || rc=$?
    t1=$(date +%s.%N)
    awk -v a="$t0" -v b="$t1" -v rc="$rc" 'BEGIN { printf "real %.3f s, код виходу nc: %d\n", b - a, rc }'
}

LINEAR=$(sysctl -n net.ipv4.tcp_syn_linear_timeouts 2> /dev/null || echo "немає в цьому ядрі")
title "Ядро: $(uname -sr), tcp_syn_retries=$(sysctl -n net.ipv4.tcp_syn_retries), tcp_syn_linear_timeouts=$LINEAR"
python3 -u open_server.py --port "$OPEN" &
SRV_PID=$!
wait_port t "$OPEN"
ss -ltn "sport = :$OPEN or sport = :$CLOSED"

title "1. Без правил: open і closed"
cap_start "tcp port $CLOSED or tcp port $OPEN"
timed_nc -vz -w 5 127.0.0.1 "$OPEN"
timed_nc -vz -w 5 127.0.0.1 "$CLOSED"
cap_stop "SYN -> SYN-ACK для open, SYN -> RST,ACK для closed"
python3 probe.py --timeout 3 "127.0.0.1:$OPEN" "127.0.0.1:$CLOSED"

title "2. iptables -j DROP: порт стає filtered"
iptables -A INPUT -p tcp --dport "$CLOSED" -j DROP
iptables -A INPUT -p tcp --dport "$OPEN" -j DROP
iptables -S INPUT
cap_start "tcp port $CLOSED"
timed_nc -vz -w "$CAPTURE_WAIT" 127.0.0.1 "$CLOSED"
cap_stop "лише SYN і його повтори; відповіді немає"
python3 probe.py --timeout 3 "127.0.0.1:$OPEN" "127.0.0.1:$CLOSED"
echo "(на $OPEN процес слухає, але DROP ховає його: ззовні це теж filtered)"
iptables -F INPUT

title "3. iptables -j REJECT --reject-with tcp-reset: виглядає як closed"
iptables -A INPUT -p tcp --dport "$CLOSED" -j REJECT --reject-with tcp-reset
iptables -A INPUT -p tcp --dport "$OPEN" -j REJECT --reject-with tcp-reset
iptables -S INPUT
cap_start "tcp port $CLOSED or tcp port $OPEN"
timed_nc -vz -w 5 127.0.0.1 "$OPEN"
cap_stop "RST від фаєрвола не відрізнити від RST ядра"
python3 probe.py --timeout 3 "127.0.0.1:$OPEN" "127.0.0.1:$CLOSED"
echo "(на $OPEN процес слухає, але REJECT робить його схожим на closed)"
iptables -F INPUT
kill "$SRV_PID"; wait "$SRV_PID" 2> /dev/null || true

title "4. UDP: closed = ICMP port unreachable, open і filtered = тиша"
python3 -u open_server.py --udp --port "$OPEN" > /tmp/udp_srv.log &
SRV_PID=$!
wait_port u "$OPEN"
cap_start "udp port $CLOSED or udp port $OPEN or icmp"
python3 probe.py --udp --timeout 2 "127.0.0.1:$CLOSED" "127.0.0.1:$OPEN"
cap_stop "ICMP port unreachable лише для closed"
iptables -A INPUT -p udp --dport "$CLOSED" -j DROP
echo "+ iptables -A INPUT -p udp --dport $CLOSED -j DROP"
python3 probe.py --udp --timeout 2 "127.0.0.1:$CLOSED"
echo "(відкритий мовчазний $OPEN і закритий фаєрволом $CLOSED дали однаковий результат: open|filtered)"
iptables -F INPUT
echo
echo "nc -u теж не може відрізнити: «succeeded» означає лише «ICMP-помилки не прийшло»"
timed_nc -vzu -w 2 127.0.0.1 "$OPEN"
timed_nc -vzu -w 2 127.0.0.1 "$CLOSED"
echo "--- що бачив UDP-сервер на $OPEN:"
cat /tmp/udp_srv.log
kill "$SRV_PID"; wait "$SRV_PID" 2> /dev/null || true
