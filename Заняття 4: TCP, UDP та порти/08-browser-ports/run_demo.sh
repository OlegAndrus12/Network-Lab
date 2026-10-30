#!/usr/bin/env bash
# Живе демо: порти вашого браузера просто зараз (TCP :443, QUIC = UDP :443, ефемерні порти).
# Перед запуском відкрийте YouTube у браузері.
# Використання:  ./run_demo.sh            (IP анонімізовано: безпечно для проєктора)
#                ANON=0 ./run_demo.sh     (справжні IP)
#                LINES=25 ./run_demo.sh   (більше рядків lsof)
set -euo pipefail
cd "$(dirname "$0")"

ANON="${ANON:-1}"
LINES="${LINES:-15}"
# Назви мережевих процесів: Chrome/Edge/Brave/Arc ("... Helper"), Safari (com.apple.WebKit.Networking), Firefox
PATTERN='chrom|safari|webkit|firefox|brave|edge|browser|opera|vivaldi'
ANON_FLAG=""; [ "$ANON" = "1" ] && ANON_FLAG="--anonymize"

if ! command -v lsof > /dev/null; then
    echo "lsof не знайдено. Linux: sudo apt install lsof   або   ss -tunp | grep ':443'"; exit 1
fi

# 1. Команда зі слайда «як є». На macOS lsof обрізає назву процесу до 9 символів
#    («Google\x20Chrome» -> «Google»), тож grep chrome нічого не знаходить
echo "=== 1. lsof -i -P -n | grep -iE 'chrome|safari'  (команда без +c 0) ==="
N_SHORT=$(lsof -i -P -n 2> /dev/null | grep -ciE 'chrome|safari' || true)
N_FULL=$(lsof +c 0 -i -P -n 2> /dev/null | grep -ciE "$PATTERN" || true)
echo "знайдено рядків: $N_SHORT"
echo "з +c 0 (повна назва процесу): $N_FULL"
echo

# 2. Виправлена команда: lsof +c 0 -i -P -n | grep -iE '...' | head
echo "=== 2. lsof +c 0 -i -P -n | grep -iE '$PATTERN' | head -$LINES ==="
python3 browser_ports.py $ANON_FLAG --lines "$LINES" --pattern "$PATTERN" | sed -n '2,/^$/p'

# 3. Підсумок за процесами + порівняння з діапазоном ефемерних портів ОС
echo "=== 3. Підсумок (browser_ports.py) ==="
python3 browser_ports.py $ANON_FLAG --pattern "$PATTERN"
echo

# 4. Діапазон ефемерних портів ядра напряму
echo "=== 4. Діапазон ефемерних портів ОС ==="
if [ "$(uname)" = "Darwin" ]; then
    sysctl net.inet.ip.portrange.first net.inet.ip.portrange.last
else
    echo "ip_local_port_range: $(cat /proc/sys/net/ipv4/ip_local_port_range)"
fi
