"""Відправник для демо меж повідомлень: кілька send() підряд, без пауз."""
import argparse
import socket

from common import TCP_PORT, UDP_PORT, frame, make_message, markers

parser = argparse.ArgumentParser(description="Відправник: 3 повідомлення підряд (або одне велике)")
parser.add_argument("mode", choices=["udp", "tcp", "big", "framed"],
                    help="udp: 3 sendto; tcp: 3 send; big: один send на --big-size; framed: 3 кадри з префіксом довжини")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, help="за замовчуванням 9106 (udp) або 9116 (tcp)")
parser.add_argument("--count", type=int, default=3, help="скільки повідомлень")
parser.add_argument("--size", type=int, default=100, help="розмір одного повідомлення, байтів")
parser.add_argument("--big-size", type=int, default=1_000_000, help="розмір одного великого send для режиму big (1 МБ)")
parser.add_argument("--plus-big", action="store_true",
                    help="framed: після 3 малих надіслати ще один кадр на --big-size байтів")
parser.add_argument("--nagle", action="store_true",
                    help="залишити алгоритм Нейгла увімкненим (за замовчуванням TCP_NODELAY=1)")
args = parser.parse_args()
port = args.port or (UDP_PORT if args.mode == "udp" else TCP_PORT)
msgs = [make_message(i, args.size) for i in range(1, args.count + 1)]
if args.mode == "framed" and args.plus_big:
    msgs.append(make_message(args.count + 1, args.big_size))

if args.mode == "udp":
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for m in msgs:
            sock.sendto(m, (args.host, port))  # ні з'єднання, ні підтвердження
            print("sendto(): {} байтів  ({})".format(len(m), markers(m)), flush=True)
    print("Готово. UDP не знає, чи хтось це отримав: «відправив і забув»", flush=True)
    raise SystemExit(0)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    if not args.nagle:
        # кожен send одразу йде окремим сегментом — злиття точно не «на дроті»
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        sock.connect((args.host, port))
    except ConnectionRefusedError:
        print("Порт {} закритий: спершу запустіть receiver.py".format(port))
        raise SystemExit(1)
    print("Підключено до {}:{} (TCP_NODELAY={})".format(args.host, port, 0 if args.nagle else 1), flush=True)

    if args.mode == "big":
        payload = make_message(1, args.big_size)
        sock.sendall(payload)  # ОДИН виклик send для всього повідомлення
        print("sendall(): {} байтів одним викликом".format(len(payload)), flush=True)
    else:
        for m in msgs:
            data = frame(m) if args.mode == "framed" else m
            sock.sendall(data)
            note = " (4 байти довжини + {})".format(len(m)) if args.mode == "framed" else ""
            print("send(): {} байтів{}  ({})".format(len(data), note, markers(m)), flush=True)
print("З'єднання закрито (FIN)", flush=True)
