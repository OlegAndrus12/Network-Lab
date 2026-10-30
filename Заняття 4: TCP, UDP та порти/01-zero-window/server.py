"""Лінивий TCP-сервер: приймає з'єднання (accept), але НЕ читає дані (recv).

Байти накопичуються в буфері прийому ядра, вікно (win) зменшується до 0,
і клієнт зупиняється. З --read-after N сервер «прокидається» через N секунд
і починає читати: вікно знову відкривається (window update).
"""
import argparse
import fcntl
import signal
import socket
import sys
import struct
import termios
import time

parser = argparse.ArgumentParser(description="Лінивий TCP-сервер (zero window)")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9101)
parser.add_argument("--rcvbuf", type=int, default=0,
                    help="розмір буфера прийому SO_RCVBUF, байтів (0 = як у системі)")
parser.add_argument("--read-after", type=float, default=0,
                    help="почати читати через N секунд (0 = не читати ніколи)")
args = parser.parse_args()
# Ctrl+C: коротке повідомлення замість traceback
signal.signal(signal.SIGINT, lambda *_: sys.exit("\n[сервер] Зупинено (Ctrl+C)"))


def fmt(n):
    return f"{n:,}".replace(",", " ")  # 128 512


def recv_queue(sock):
    """Скільки байтів лежить у буфері прийому (те саме, що Recv-Q у ss/netstat)."""
    buf = fcntl.ioctl(sock, termios.FIONREAD, struct.pack("i", 0))
    return struct.unpack("i", buf)[0]


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.rcvbuf:
        # треба ДО listen(): від цього залежить вікно, яке сервер оголосить у SYN-ACK
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, args.rcvbuf)
    srv.bind((args.host, args.port))
    srv.listen(1)
    rcvbuf = srv.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    print(f"Сервер слухає {args.host}:{args.port}, SO_RCVBUF = {fmt(rcvbuf)} байтів", flush=True)

    conn, addr = srv.accept()  # рукостискання завершене
    with conn:
        print("Connected:", addr, flush=True)
        if args.read_after:
            print(f"recv() НЕ викликаю {args.read_after:g} с ...", flush=True)
        else:
            print("recv() НЕ викликаю взагалі (Ctrl+C, щоб зупинити) ...", flush=True)

        # фаза 1: лінуємося, лише дивимося на буфер прийому (це не читання)
        start = time.monotonic()
        last = -1
        while not args.read_after or time.monotonic() - start < args.read_after:
            try:
                q = recv_queue(conn)
            except OSError:
                break
            if q != last:
                print(f"[сервер] у буфері прийому {fmt(q)} байтів (прочитано додатком: 0)", flush=True)
                last = q
            time.sleep(0.2)

        # фаза 2: нарешті читаємо -> місце в буфері звільняється -> вікно відкривається
        print("[сервер] Прокинувся, починаю recv()", flush=True)
        total = 0
        next_report = 1 << 20
        while True:
            data = conn.recv(65536)
            if not data:  # FIN від клієнта
                break
            total += len(data)
            if total >= next_report:
                print(f"[сервер] прочитано {fmt(total)} байтів", flush=True)
                next_report += 1 << 20

print(f"[сервер] Клієнт закрив з'єднання. Усього прочитано {fmt(total)} байтів", flush=True)
