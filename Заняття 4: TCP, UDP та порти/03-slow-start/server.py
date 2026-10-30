"""TCP-сервер для демо slow start: віддає клієнту великий «файл» (саме сервер тут відправник)."""
import argparse
import socket
import time

parser = argparse.ArgumentParser(description="Сервер, що віддає N МБ даних")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9103)
parser.add_argument("--size-mb", type=float, default=8, help="скільки мегабайтів віддати")
parser.add_argument("--clients", type=int, default=1, help="скільки клієнтів обслужити, 0 = безкінечно")
args = parser.parse_args()

total = int(args.size_mb * 1024 * 1024)
chunk = b"x" * 65536  # «файл» з однакових байтів, тут важлива лише кількість

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(1)
    print(f"Сервер слухає {args.host}:{args.port}, віддає {args.size_mb:g} МБ", flush=True)

    served = 0
    while args.clients == 0 or served < args.clients:
        conn, addr = srv.accept()
        with conn:
            print("Клієнт підключився:", addr, flush=True)
            start = time.monotonic()
            sent = 0
            while sent < total:
                # sendall блокується, коли буфер відправлення повний:
                # швидкість визначає TCP (cwnd), а не наш цикл
                part = chunk[: min(len(chunk), total - sent)]
                conn.sendall(part)
                sent += len(part)
            print(f"Віддано {sent} байтів за {time.monotonic() - start:.2f} с "
                  "(час до передачі у буфер ядра, не до останнього ACK)", flush=True)
        served += 1
