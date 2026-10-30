"""Приймач для демо меж повідомлень: показує, що саме повертає кожен recv()/recvfrom()."""
import argparse
import socket
import time

from common import HEADER, TCP_PORT, UDP_PORT, markers, short_repr

parser = argparse.ArgumentParser(description="Приймач: UDP зберігає межі, TCP — ні")
parser.add_argument("mode", choices=["udp", "tcp", "framed"],
                    help="udp: дейтаграми; tcp: сирий потік; framed: потік + префікс довжини")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, help="за замовчуванням 9106 (udp) або 9116 (tcp)")
parser.add_argument("--delay", type=float, default=0.5,
                    help="пауза перед першим recv, с (щоб усі send уже лежали в буфері)")
parser.add_argument("--bufsize", type=int, default=65536, help="скільки байтів просити в recv")
parser.add_argument("--rcvbuf", type=int, default=0,
                    help="розмір буфера прийому ядра SO_RCVBUF, байтів (0 = як в ОС за замовчуванням)")
args = parser.parse_args()
port = args.port or (UDP_PORT if args.mode == "udp" else TCP_PORT)


def show(n, data, extra=""):
    print("  recv #{}: {:>6} байтів  {}".format(n, len(data), short_repr(data)), flush=True)
    print("            {}{}".format(markers(data), extra), flush=True)


if args.mode == "udp":
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, port))
        print("UDP-приймач слухає {}:{} (recvfrom по {} байтів)".format(args.host, port, args.bufsize), flush=True)
        sock.settimeout(None)
        data, addr = sock.recvfrom(args.bufsize)  # чекаємо першу дейтаграму
        print("перша дейтаграма прийшла; далі пауза {} с — нехай решта теж ляже в буфер".format(args.delay), flush=True)
        n = 1
        show(n, data, "  від {}".format(addr))
        time.sleep(args.delay)
        sock.settimeout(1.0)  # 1 с тиші = відправник закінчив (у UDP немає «кінця з'єднання»)
        while True:
            try:
                data, addr = sock.recvfrom(args.bufsize)
            except socket.timeout:
                break
            n += 1
            show(n, data, "  від {}".format(addr))
        print("Разом recvfrom(): {} — по одному на кожен sendto()".format(n), flush=True)
    raise SystemExit(0)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.rcvbuf:
        # ставимо до listen(): прийняте з'єднання успадкує розмір буфера
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, args.rcvbuf)
    srv.bind((args.host, port))
    srv.listen(1)
    print("TCP-приймач ({}) слухає {}:{} (recv по {} байтів)".format(args.mode, args.host, port, args.bufsize), flush=True)
    conn, addr = srv.accept()
    with conn:
        if args.rcvbuf:
            # і ще раз на самому з'єднанні: macOS інакше автоматично збільшує буфер
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, args.rcvbuf)
        rcv = conn.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        print("Connected: {}; буфер прийому ядра {} байтів; пауза {} с перед першим recv()".format(addr, rcv, args.delay), flush=True)
        time.sleep(args.delay)  # відправник за цей час встигає все надіслати
        n = total = 0
        buf = bytearray()  # для framed: накопичуємо байти, поки не збереться цілий кадр
        messages = []
        while True:
            data = conn.recv(args.bufsize)
            if not data:  # порожньо = FIN від відправника
                break
            n += 1
            total += len(data)
            if args.mode == "tcp":
                show(n, data)
                continue
            print("  recv #{}: {:>6} байтів (сирі байти потоку)".format(n, len(data)), flush=True)
            buf += data
            # виймаємо всі цілі кадри: 4 байти довжини + стільки байтів даних
            while len(buf) >= HEADER.size:
                (length,) = HEADER.unpack(buf[:HEADER.size])
                if len(buf) < HEADER.size + length:
                    print("      (кадр ще неповний: є {} з {} байтів — чекаємо наступний recv)".format(
                        len(buf) - HEADER.size, length), flush=True)
                    break  # кадр ще не дійшов повністю: чекаємо наступний recv
                msg = bytes(buf[HEADER.size:HEADER.size + length])
                del buf[:HEADER.size + length]
                messages.append(msg)
                print("      -> повідомлення {}: {} байтів  {}".format(len(messages), len(msg), short_repr(msg)), flush=True)
        print("Разом recv(): {}, байтів: {}".format(n, total), flush=True)
        if args.mode == "framed":
            print("Після розбору кадрів: {} повідомлення(нь), залишок у буфері: {} байтів".format(len(messages), len(buf)), flush=True)
