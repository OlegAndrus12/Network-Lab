"""TCP-клієнт для демо slow start: «завантажує файл» із сервера і рахує швидкість."""
import argparse
import socket
import time

parser = argparse.ArgumentParser(description="Клієнт, що завантажує дані з сервера")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9103)
args = parser.parse_args()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    t0 = time.monotonic()
    try:
        sock.connect((args.host, args.port))  # рукостискання: тут з'являється перша оцінка RTT
    except ConnectionRefusedError:
        print(f"Порт {args.port} закритий: сервер не запущений")
        raise SystemExit(1)
    t1 = time.monotonic()
    print(f"Підключено до {args.host}:{args.port}, рукостискання зайняло {(t1 - t0) * 1000:.0f} мс")

    received = 0
    next_report = 1024 * 1024
    while True:
        data = sock.recv(262144)
        if not data:  # сервер надіслав FIN: файл закінчився
            break
        received += len(data)
        if received >= next_report:
            print(f"  t={time.monotonic() - t1:5.2f} с  отримано {received / 1048576:5.1f} МБ")
            next_report += 1024 * 1024

dt = time.monotonic() - t1
print(f"Отримано {received / 1048576:.1f} МБ за {dt:.2f} с, "
      f"середня швидкість {received * 8 / dt / 1e6:.1f} Мбіт/с")
