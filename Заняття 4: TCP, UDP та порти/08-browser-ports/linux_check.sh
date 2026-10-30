#!/usr/bin/env bash
# Linux у Docker: діапазон ефемерних портів, вивід lsof і ss для TCP :443 та UDP :443.
# Браузера в контейнері немає, тому python3 відкриває один TCP- і один UDP-сокет до 1.1.1.1:443.
set -euo pipefail
cd "$(dirname "$0")"

docker rm -f demo08-linux > /dev/null 2>&1 || true
docker run --rm --name demo08-linux -v "$PWD":/demo:ro python:3.12-slim bash -c '
set -e
echo "=== cat /proc/sys/net/ipv4/ip_local_port_range ==="
cat /proc/sys/net/ipv4/ip_local_port_range
apt-get update -qq > /dev/null 2>&1 && apt-get install -y -qq lsof iproute2 > /dev/null 2>&1
python3 -c "
import socket, time
t = socket.create_connection((\"1.1.1.1\", 443), timeout=5)   # TCP: рукостискання
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
u.connect((\"1.1.1.1\", 443))                                  # UDP: лише запам’ятовує адресу, пакетів немає
time.sleep(5)
" &
sleep 2
echo; echo "=== lsof -i -P -n ==="; lsof -i -P -n
echo; echo "=== ss -tunp ==="; ss -tunp
echo; echo "=== browser_ports.py --all ==="; python3 /demo/browser_ports.py --all
wait'
