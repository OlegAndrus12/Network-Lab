"""Сервер, який слухає, але НЕ викликає accept(): черга listen() заповнюється.

Після Enter (або сигналу SIGUSR1, або --accept-after N) сервер починає accept()
і показує, як черга спорожнюється, а клієнти, що чекали, нарешті «заходять».
"""
import argparse
import os
import select
import signal
import socket
import sys
import threading
import time


def ts():
    """Годинник ГГ:ХХ:СС.с: однаковий у сервера, клієнтів і tcpdump."""
    t = time.time()
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t * 10) % 10}"


def say(msg):
    """Один рядок = один write(): вивід сервера й клієнтів не перемішується посеред рядка."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

parser = argparse.ArgumentParser(description="Сервер, що не викликає accept()")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9107)
parser.add_argument("--backlog", type=int, default=2, help="аргумент listen()")
parser.add_argument("--accept-after", type=float, default=None,
                    help="почати accept() через N секунд (без Enter)")
parser.add_argument("--idle-exit", type=float, default=None,
                    help="завершитись, якщо N секунд немає нових клієнтів")
args = parser.parse_args()

start_accepting = threading.Event()
signal.signal(signal.SIGUSR1, lambda *_: start_accepting.set())  # kill -USR1 <pid>
signal.signal(signal.SIGTERM, signal.default_int_handler)  # kill <pid> == Ctrl+C


def wait_for_enter():
    try:
        input()
    except EOFError:
        return  # stdin закритий (запуск у фоні): чекаємо на сигнал або таймер
    start_accepting.set()


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((args.host, args.port))
srv.listen(args.backlog)  # стан LISTEN; ядро саме завершує рукостискання
say(f"[{ts()}] Сервер слухає {args.host}:{args.port}, listen(backlog={args.backlog}), PID {os.getpid()}")

if args.accept_after is not None:
    say(f"accept() НЕ викликаю ще {args.accept_after:g} с")
    threading.Timer(args.accept_after, start_accepting.set).start()
else:
    if sys.stdin.isatty():
        say("accept() НЕ викликаю. Натисніть Enter (або kill -USR1 PID), щоб почати accept()")
        threading.Thread(target=wait_for_enter, daemon=True).start()
    else:
        say(f"accept() НЕ викликаю, доки не отримаю сигнал: kill -USR1 {os.getpid()}")

conns = []  # тримаємо з'єднання відкритими, щоб їх було видно в ss/netstat
try:
    while not start_accepting.wait(0.2):
        pass
    say(f"[{ts()}] Починаю accept()")
    srv.settimeout(args.idle_exit)
    while True:
        try:
            conn, addr = srv.accept()  # забирає готове з'єднання з черги
        except socket.timeout:
            say(f"Нових клієнтів немає {args.idle_exit:g} с, завершую роботу")
            break
        conns.append(conn)
        # клієнт одразу після connect() надіслав свій номер; дані вже чекають у буфері
        ready, _, _ = select.select([conn], [], [], 0.2)
        hello = conn.recv(64).decode(errors="replace").strip() if ready else "(даних ще немає)"
        say(f"[{ts()}] accept() №{len(conns)}: {addr[0]}:{addr[1]}  повідомлення: {hello}")
except KeyboardInterrupt:
    say(f"[{ts()}] Зупинка (Ctrl+C): сервер закриває {len(conns)} з'єднань і сокет LISTEN")
finally:
    for c in conns:
        c.close()
    srv.close()
