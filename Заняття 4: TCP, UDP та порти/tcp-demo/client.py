"""TCP-клієнт для демонстрації: надсилає кілька невеликих порцій байтів."""
import argparse
import socket
import time

parser = argparse.ArgumentParser(description="TCP-клієнт для демо")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9000)
parser.add_argument("--count", type=int, default=3, help="скільки разів надсилати")
parser.add_argument("--size", type=int, default=100, help="скільки байтів за раз")
parser.add_argument("--delay", type=float, default=1.0, help="пауза між надсиланнями, с")
args = parser.parse_args()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    # вимикаємо алгоритм Нейгла, щоб кожен send став окремим сегментом
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        sock.connect((args.host, args.port))  # тут відбувається рукостискання
    except ConnectionRefusedError:
        print(f"Порт {args.port} закритий: сервер відповів RST")
        raise SystemExit(1)
    print(f"Підключено до {args.host}:{args.port}")

    for i in range(args.count):
        if i > 0:
            time.sleep(args.delay)
        sock.sendall(b"x" * args.size)
        print(f"надіслано {args.size} байтів")

print("З'єднання закрито")  # вихід із with -> close() -> FIN
