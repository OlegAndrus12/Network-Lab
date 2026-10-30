"""TCP-клієнт, який шле дані в циклі й показує, де send() зупинився.

Коли вікно сервера = 0 і власний буфер відправлення заповнений, send()
не може покласти жодного байта і чекає. Ми друкуємо прогрес, щоб «заморозку»
було видно, і рахуємо, скільки байтів застрягло в нашому ж буфері.
"""
import argparse
import fcntl
import signal
import socket
import struct
import sys
import time

parser = argparse.ArgumentParser(description="TCP-клієнт для демо zero window")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9101)
parser.add_argument("--chunk", type=int, default=65536, help="байтів за один send()")
parser.add_argument("--sndbuf", type=int, default=0,
                    help="розмір буфера відправлення SO_SNDBUF, байтів (0 = як у системі)")
parser.add_argument("--total", type=int, default=0,
                    help="скільки всього надіслати, байтів (0 = без кінця)")
parser.add_argument("--every", type=int, default=262144,
                    help="друкувати прогрес кожні N байтів")
parser.add_argument("--give-up", type=float, default=0,
                    help="здатися, якщо send() стоїть N секунд (0 = чекати вічно)")
args = parser.parse_args()


def send_queue(sock):
    """Скільки байтів ще в НАШОМУ буфері відправлення (Send-Q у ss/netstat)."""
    if sys.platform == "darwin":
        return sock.getsockopt(socket.SOL_SOCKET, 0x1024)  # SO_NWRITE
    if sys.platform.startswith("linux"):
        buf = fcntl.ioctl(sock, 0x5411, struct.pack("i", 0))  # SIOCOUTQ
        return struct.unpack("i", buf)[0]
    return None


def fmt(n):
    return f"{n:,}".replace(",", " ")  # 2 883 584


def report(sent, sock):
    try:
        q = send_queue(sock)
    except OSError:
        q = None
    print(f"  передано в send():               {fmt(sent)} байтів")
    if q is not None:
        print(f"  ще лежить у МОЄМУ буфері (Send-Q): {fmt(q)} байтів")
        print(f"  дійшло до буфера сервера:         {fmt(sent - q)} байтів")
    sys.stdout.flush()


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    if args.sndbuf:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, args.sndbuf)
    try:
        sock.connect((args.host, args.port))
    except ConnectionRefusedError:
        print(f"Порт {args.port} закритий: сервер не запущено")
        raise SystemExit(1)
    sndbuf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
    print(f"Підключено до {args.host}:{args.port}, SO_SNDBUF = {fmt(sndbuf)} байтів", flush=True)

    # таймаут лише для того, щоб друкувати «чекаю»; сам send() так само
    # чекає, поки в буфері відправлення звільниться місце
    sock.settimeout(0.5)
    interrupted = False

    def on_ctrl_c(*_):
        global interrupted
        interrupted = True

    signal.signal(signal.SIGINT, on_ctrl_c)
    data = b"x" * args.chunk
    sent = 0
    next_print = args.every
    stalled = 0.0
    while not args.total or sent < args.total:
        try:
            if interrupted:
                print("\nЗупинено (Ctrl+C). Стан на цей момент:")
                report(sent, sock)
                break
            n = sock.send(data if not args.total else data[: args.total - sent])
        except (BrokenPipeError, ConnectionResetError):
            print("З'єднання розірвано (RST від сервера). Стан на цей момент:")
            report(sent, sock)
            break
        except socket.timeout:
            stalled += 0.5
            if stalled == 1.0:
                print(f"!!! send() ЗАБЛОКОВАНО: мій буфер відправлення повний, бо вікно сервера = 0", flush=True)
                report(sent, sock)
            elif stalled % 2 == 0:
                print(f"... send() чекає вже {stalled:g} с, надіслано {fmt(sent)} байтів", flush=True)
            if args.give_up and stalled >= args.give_up:
                print(f"Здаюся після {stalled:g} с очікування. Зупинилися на:", flush=True)
                report(sent, sock)
                break
            continue
        if stalled >= 1.0:
            print(f">>> send() знову працює після {stalled:g} с: вікно відкрилось (у сервера звільнилось місце)",
                  flush=True)
        stalled = 0.0
        sent += n
        if sent >= next_print:
            print(f"надіслано {fmt(sent)} байтів", flush=True)
            next_print = (sent // args.every + 1) * args.every

print(f"З'єднання закрито, усього надіслано {fmt(sent)} байтів", flush=True)
