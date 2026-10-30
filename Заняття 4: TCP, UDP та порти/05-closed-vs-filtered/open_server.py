"""Відкритий порт для демо: TCP-слухач (або мовчазний UDP-сокет) на 9115."""
import argparse
import socket

parser = argparse.ArgumentParser(description="Слухач для випадку «open»")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9115)
parser.add_argument("--udp", action="store_true",
                    help="відкрити UDP-порт, який нічого не відповідає (як більшість UDP-сервісів на чужий запит)")
args = parser.parse_args()

kind = socket.SOCK_DGRAM if args.udp else socket.SOCK_STREAM
with socket.socket(socket.AF_INET, kind) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    if not args.udp:
        srv.listen(16)  # стан LISTEN: на SYN ядро саме відповість SYN-ACK
    proto = "udp" if args.udp else "tcp"
    print(f"Слухаю {args.host}:{args.port}/{proto} (відкритий порт)", flush=True)
    try:
        while True:
            if args.udp:
                data, addr = srv.recvfrom(1024)  # отримали, але мовчимо
                print(f"UDP: отримано {len(data)} байтів від {addr}, не відповідаю", flush=True)
            else:
                conn, _ = srv.accept()
                conn.close()  # нам потрібне лише рукостискання
    except KeyboardInterrupt:
        pass
