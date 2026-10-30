"""Відкриває N TCP-з'єднань і показує, у яких connect() завершився, а в яких ні.

Не залежить від прапорців nc: неблокувальні сокети + select.
Після підключення клієнт надсилає «клієнт #i», щоб сервер бачив, хто зайшов.
"""
import argparse
import errno
import os
import selectors
import signal
import socket
import sys
import time


def ts():
    """Годинник ГГ:ХХ:СС.с: однаковий у сервера, клієнтів і tcpdump."""
    t = time.time()
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t * 10) % 10}"


def say(msg):
    """Один рядок = один write(): вивід сервера й клієнтів не перемішується посеред рядка."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

parser = argparse.ArgumentParser(description="N клієнтів до сервера без accept()")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9107)
parser.add_argument("-n", "--count", type=int, default=5, help="скільки клієнтів")
parser.add_argument("--gap", type=float, default=0.2, help="пауза між connect(), с")
parser.add_argument("--wait", type=float, default=3.0, help="скільки чекати перед першим звітом, с")
parser.add_argument("--hold", type=float, default=60.0,
                    help="скільки тримати з'єднання відкритими і чекати решту, с")
args = parser.parse_args()

signal.signal(signal.SIGTERM, signal.default_int_handler)  # kill <pid> == Ctrl+C
sel = selectors.DefaultSelector()
clients = {}  # номер -> dict(sock, port, state, t)
t0 = time.monotonic()


def now():
    return time.monotonic() - t0


def finish(i, err):
    c = clients[i]
    sel.unregister(c["sock"])
    if err == 0:
        c["state"], c["t"] = "ok", now()
        c["sock"].send(f"клієнт #{i}\n".encode())
    else:
        c["state"] = f"connect() не вдався: {errno.errorcode.get(err, err)} ({os.strerror(err)})"


def poll(timeout):
    """Чекає на події до timeout с; повертає номери клієнтів, у яких змінився стан."""
    changed = []
    for key, _ in sel.select(timeout):
        i = key.data
        finish(i, key.fileobj.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR))
        changed.append(i)
    return changed


def report_line(i):
    c = clients[i]
    if c["state"] == "ok":
        return f"  клієнт #{i} (порт {c['port']}): connect() завершився за {c['t'] - c['t_start']:.2f} с"
    if c["state"] == "pending":
        return f"  клієнт #{i} (порт {c['port']}): connect() ЩЕ ЧЕКАЄ (SYN без відповіді?)"
    return f"  клієнт #{i} (порт {c['port']}): {c['state']}"


say(f"[{ts()}] Відкриваю {args.count} з'єднань до {args.host}:{args.port}")
for i in range(1, args.count + 1):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(False)
    err = s.connect_ex((args.host, args.port))  # неблокувальний connect(): одразу повертає
    clients[i] = {"sock": s, "port": s.getsockname()[1], "state": "pending", "t_start": now()}
    sel.register(s, selectors.EVENT_WRITE, i)  # «можна писати» = рукостискання завершилось
    if err not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
        finish(i, err)
    gap_end = time.monotonic() + args.gap
    while time.monotonic() < gap_end:  # пауза між клієнтами, але події обробляємо
        poll(max(0.0, gap_end - time.monotonic()))

deadline = t0 + args.gap * args.count + args.wait
while time.monotonic() < deadline and any(c["state"] == "pending" for c in clients.values()):
    poll(max(0.0, deadline - time.monotonic()))

ok = [i for i, c in clients.items() if c["state"] == "ok"]
waiting = [i for i, c in clients.items() if c["state"] == "pending"]
say(f"\n[{ts()}] Звіт:")
for i in clients:
    say(report_line(i))
say(f"Разом: connect() завершився у {len(ok)}, чекають {len(waiting)}")

if waiting:
    say(f"Чекаю ще до {args.hold:g} с, поки сервер почне accept() ...")
end = t0 + args.hold
try:
    while time.monotonic() < end:
        if not any(c["state"] == "pending" for c in clients.values()):
            time.sleep(min(0.5, max(0.0, end - time.monotonic())))
            continue
        for i in poll(min(0.5, max(0.0, end - time.monotonic()))):
            c = clients[i]
            what = f"connect() нарешті завершився (чекав {c['t'] - c['t_start']:.1f} с)" if c["state"] == "ok" else c["state"]
            say(f"[{ts()}] клієнт #{i} (порт {c['port']}): {what}")
except KeyboardInterrupt:
    pass
still = [i for i, c in clients.items() if c["state"] == "pending"]
say(f"[{ts()}] Закриваю з'єднання" + (f"; так і не підключились: {still}" if still else ""))
for c in clients.values():
    c["sock"].close()
