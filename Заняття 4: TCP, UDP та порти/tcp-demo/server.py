"""TCP-сервер для демонстрації: приймає одного клієнта і рахує отримані байти."""
import socket
import sys

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    # дозволяє одразу перезапустити сервер на тому ж порту
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)  # стан LISTEN
    print(f"Сервер слухає {HOST}:{PORT}", flush=True)

    conn, addr = srv.accept()  # повертається після рукостискання (ESTABLISHED)
    with conn:
        print("Connected:", addr, flush=True)
        while True:
            data = conn.recv(4096)
            if not data:  # порожні дані = клієнт надіслав FIN
                break
            print(f"отримано {len(data)} байтів", flush=True)

print("Клієнт закрив з'єднання, сервер завершує роботу", flush=True)
