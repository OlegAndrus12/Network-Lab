"""Секундомір для портів: міряє, скільки триває connect() і що повернуло ядро.

open      -> SYN-ACK, connect() успішний          (nmap: open)
closed    -> RST, ConnectionRefusedError одразу   (nmap: closed)
filtered  -> тиша, чекаємо до тайм-ауту           (nmap: filtered)
"""
import argparse
import errno
import socket
import time

DEFAULT_TARGETS = ["127.0.0.1:9115", "127.0.0.1:9105", "10.255.255.1:80"]


def probe_tcp(host, port, timeout):
    """Повертає (що сталося, термін nmap)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))  # ядро шле SYN і чекає відповіді
            return "SYN-ACK: з'єднання встановлено", "open"
        except ConnectionRefusedError:
            return "RST: Connection refused", "closed"
        except (socket.timeout, TimeoutError):
            return f"тиша, тайм-аут {timeout:g} с", "filtered"
        except OSError as e:
            # ICMP host/network unreachable від маршрутизатора або «немає маршруту»
            name = errno.errorcode.get(e.errno, str(e.errno))
            return f"{name}: {e.strerror}", "filtered (ICMP/маршрут)"


def probe_udp(host, port, timeout):
    """UDP: відповіді на порожню датаграму зазвичай немає ні від open, ні від filtered."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))  # «підключений» UDP-сокет отримує ICMP-помилки
        try:
            s.send(b"ping")
            s.recv(1024)
            return "прийшла UDP-відповідь", "open"
        except ConnectionRefusedError:
            return "ICMP port unreachable", "closed"
        except (socket.timeout, TimeoutError):
            return f"тиша, тайм-аут {timeout:g} с", "open|filtered"


def parse_target(text):
    host, _, port = text.rpartition(":")
    return host, int(port)


parser = argparse.ArgumentParser(description="Порівняння open / closed / filtered за часом")
parser.add_argument("targets", nargs="*", default=DEFAULT_TARGETS,
                    help="адреси у форматі host:port (за замовчуванням: %(default)s)")
parser.add_argument("--timeout", type=float, default=5.0, help="тайм-аут connect(), с")
parser.add_argument("--udp", action="store_true", help="перевіряти UDP замість TCP")
args = parser.parse_args()

proto = "udp" if args.udp else "tcp"
rows = []
for target in args.targets:
    host, port = parse_target(target)
    print(f"перевіряю {target}/{proto} ...", flush=True)
    start = time.perf_counter()
    result, term = (probe_udp if args.udp else probe_tcp)(host, port, args.timeout)
    elapsed = time.perf_counter() - start
    shown = f"{elapsed * 1000:.2f} мс" if elapsed < 1 else f"{elapsed:.2f} с"
    rows.append((f"{target}/{proto}", result, shown, term))

header = ("ціль", "результат", "час", "термін nmap")
widths = [max(len(r[i]) for r in rows + [header]) for i in range(4)]
line = lambda r: " | ".join(c.ljust(w) for c, w in zip(r, widths))
print()
print(line(header))
print("-+-".join("-" * w for w in widths))
for r in rows:
    print(line(r))
