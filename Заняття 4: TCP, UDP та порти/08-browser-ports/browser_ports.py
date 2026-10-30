"""Підсумок портів браузера з виводу `lsof -i -P -n`.

Групує сокети за процесом і протоколом: TCP → :443 (HTTPS), UDP → :443 (QUIC / HTTP/3),
TCP → :80 (HTTP), діапазон локальних ефемерних портів і порівняння з діапазоном ОС.

Приклади:
    python3 browser_ports.py                       # сам запускає lsof +c 0 -i -P -n
    python3 browser_ports.py --anonymize --lines 15
    lsof +c 0 -i -P -n | python3 browser_ports.py --file -
    python3 browser_ports.py --all                 # усі процеси, а не лише браузери
"""
import argparse
import ipaddress
import platform
import re
import subprocess
import sys
from collections import defaultdict

# Назви процесів, через які браузери ходять у мережу (macOS / Linux / Windows-WSL)
BROWSER_RE = r"chrom|safari|webkit|firefox|brave|edge|browser|opera|vivaldi|^arc$"

# Людська назва браузера за назвою процесу
FAMILIES = [
    (r"google chrome|chrome|chromium", "Chrome/Chromium"),
    (r"webkit|safari", "Safari (WebKit)"),
    (r"firefox", "Firefox"),
    (r"brave", "Brave"),
    (r"edge", "Edge"),
    (r"^arc$|^browser helper", "Arc"),
    (r"opera", "Opera"),
    (r"vivaldi", "Vivaldi"),
]

# Відомі «інші» порти, які часто бачимо в браузера
KNOWN = {"5353": "mDNS, пошук пристроїв у LAN", "5228": "Google push (FCM)", "53": "DNS",
         "3478": "STUN/WebRTC", "853": "DNS-over-TLS"}

# host:port, де host — IPv4, [IPv6] або *
ADDR_RE = re.compile(r"^(\[[^\]]*\]|[^:\[\]]+|\*):(\d+|\*)$")

parser = argparse.ArgumentParser(description="Порти браузера з lsof -i -P -n")
parser.add_argument("--file", help="готовий вивід lsof (шлях або '-' для stdin); інакше запускаємо lsof")
parser.add_argument("--all", action="store_true", help="усі процеси, а не лише браузери")
parser.add_argument("--pattern", default=BROWSER_RE, help="регулярний вираз для назви процесу")
parser.add_argument("--anonymize", action="store_true",
                    help="замінити IP на документаційні 203.0.113.x / 2001:db8::x (для екрана й слайдів)")
parser.add_argument("--lines", type=int, default=0, help="показати перші N відфільтрованих рядків lsof")
args = parser.parse_args()


def read_lsof():
    if args.file == "-":
        return sys.stdin.read()
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            return f.read()
    # +c 0: повна назва процесу (без нього macOS показує лише «Google», і grep chrome нічого не знаходить)
    cmd = ["lsof", "+c", "0", "-i", "-P", "-n"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        sys.exit("lsof не знайдено. Linux: sudo apt install lsof (або дивіться ss -tunp)")
    return res.stdout


class Anonymizer:
    """Послідовно замінює IP-адреси: та сама адреса → той самий замінник."""

    def __init__(self):
        self.map = {}
        self.n4 = self.n6 = 0

    def keep(self, host, local):
        if host == "*":
            return True
        try:
            ip = ipaddress.ip_address(host.strip("[]").split("%")[0])
        except ValueError:
            return True
        # локальні приватні/loopback/link-local адреси не ідентифікують людину
        return local and (ip.is_private or ip.is_loopback or ip.is_link_local)

    def __call__(self, host, local=False):
        if not args.anonymize or self.keep(host, local):
            return host
        if host not in self.map:
            if host.startswith("["):
                self.n6 += 1
                self.map[host] = f"[2001:db8::{self.n6:x}]"
            else:
                self.n4 += 1
                self.map[host] = f"203.0.113.{self.n4}"
        return self.map[host]


anon = Anonymizer()


def split_addr(s):
    m = ADDR_RE.match(s)
    return (m.group(1), m.group(2)) if m else (s, "")


def family(name):
    for rx, fam in FAMILIES:
        if re.search(rx, name, re.I):
            return fam
    return "інше"


def os_ephemeral_range():
    """Діапазон ефемерних портів поточної ОС."""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(["sysctl", "-n", "net.inet.ip.portrange.first", "net.inet.ip.portrange.last"],
                                 capture_output=True, text=True).stdout.split()
            return "macOS sysctl net.inet.ip.portrange.first/last", int(out[0]), int(out[1])
        if system == "Linux":
            with open("/proc/sys/net/ipv4/ip_local_port_range") as f:
                lo, hi = f.read().split()
            return "Linux /proc/sys/net/ipv4/ip_local_port_range", int(lo), int(hi)
    except (OSError, ValueError, IndexError):
        pass
    return None


text = read_lsof()
pattern = re.compile(args.pattern, re.I)
rows, shown = [], []
for line in text.splitlines():
    parts = line.split()
    # COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME [(STATE)]
    if len(parts) < 9 or parts[0] == "COMMAND" or parts[7] not in ("TCP", "UDP"):
        continue
    name = parts[0].replace("\\x20", " ")
    if not args.all and not pattern.search(name):
        continue
    proto, addr = parts[7], parts[8]
    state = parts[9].strip("()") if len(parts) > 9 else ""
    local, _, remote = addr.partition("->")
    lhost, lport = split_addr(local)
    rhost, rport = split_addr(remote) if remote else ("", "")
    rows.append(dict(name=name, pid=parts[1], proto=proto, lport=lport, rport=rport, state=state))
    # той самий рядок, але з анонімізованими адресами
    new_addr = f"{anon(lhost, local=True)}:{lport}"
    if remote:
        new_addr += f"->{anon(rhost)}:{rport}"
    shown.append(line.replace(addr, new_addr))

if args.lines:
    header = next((l for l in text.splitlines() if l.startswith("COMMAND")), "")
    print(f"=== Перші {min(args.lines, len(shown))} з {len(shown)} рядків lsof"
          + (" (IP анонімізовано)" if args.anonymize else "") + " ===")
    if header:
        print(header)
    for l in shown[: args.lines]:
        print(l)
    print()

if not rows:
    print("Жодного мережевого сокета браузера не знайдено.")
    print("Відкрийте YouTube у браузері й запустіть ще раз (або --all, щоб побачити всі процеси).")
    sys.exit(0)

groups = defaultdict(list)
for r in rows:
    groups[(r["name"], r["pid"])].append(r)

print("=== Сокети за процесом ===" if args.all else "=== Сокети браузера за процесом ===")
all_eph = []
for (name, pid), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    tcp443 = [r for r in items if r["proto"] == "TCP" and r["rport"] == "443"]
    udp443 = [r for r in items if r["proto"] == "UDP" and r["rport"] == "443"]
    tcp80 = [r for r in items if r["proto"] == "TCP" and r["rport"] == "80"]
    other = defaultdict(int)
    for r in items:
        if r in tcp443 or r in udp443 or r in tcp80:
            continue
        port = r["rport"] or r["lport"]
        key = f"{r['proto']} → :{port}" if r["rport"] else f"{r['proto']} слухає :{port}"
        if port in KNOWN:
            key += f" ({KNOWN[port]})"
        other[key] += 1
    # ефемерні = локальні порти з'єднань, які відкрив браузер (є віддалена адреса)
    eph = sorted(int(r["lport"]) for r in items if r["rport"] and r["lport"].isdigit())
    all_eph += eph
    print(f"\n{name}  (PID {pid}, {family(name)}): усього {len(items)} сокетів")
    print(f"  TCP → :443  (HTTPS, HTTP/1.1 або HTTP/2): {len(tcp443)}")
    print(f"  UDP → :443  (QUIC = HTTP/3):              {len(udp443)}")
    print(f"  TCP → :80   (HTTP без шифрування):        {len(tcp80)}")
    for key, n in sorted(other.items()):
        print(f"  {key}: {n}")
    if eph:
        print(f"  Локальні (ефемерні) порти: {eph[0]}–{eph[-1]}  ({len(eph)} шт.)")

print("\n=== Ефемерні порти ===")
if all_eph:
    print(f"{'Процеси зараз використовують' if args.all else 'Браузер зараз використовує'} локальні порти {min(all_eph)}–{max(all_eph)}")
rng = os_ephemeral_range()
if rng:
    src, lo, hi = rng
    print(f"Діапазон ОС ({src}): {lo}–{hi}  ({hi - lo + 1} портів)")
    if all_eph:
        inside = sum(lo <= p <= hi for p in all_eph)
        print(f"У діапазоні ОС: {inside} з {len(all_eph)}")
print("Для порівняння: IANA 49152–65535; Linux за замовчуванням 32768–60999; Windows 49152–65535")
if args.anonymize:
    print("\n(Віддалені IP замінено на документаційні 203.0.113.x / 2001:db8::x; порти й процеси справжні.)")
