"""Відправник для демо «надійність поверх UDP»: від «відправив і забув» до ковзного вікна."""
import argparse
import socket
import time

from common import (ACK, COUNT, DATA, FIN, MSG_SIZE, RTO, TCP_PORT, UDP_PORT,
                    make_message, pack, unpack)

parser = argparse.ArgumentParser(description="Відправник: --count повідомлень поверх UDP (або TCP для порівняння)")
parser.add_argument("mode", choices=["naive", "saw", "window", "tcp"],
                    help="naive: просто sendto; saw: stop-and-wait (ACK + повтор); "
                         "window: ковзне вікно; tcp: те саме через TCP")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, help="за замовчуванням 9109 (udp) або 9119 (tcp)")
parser.add_argument("--count", type=int, default=COUNT, help="скільки повідомлень")
parser.add_argument("--size", type=int, default=MSG_SIZE, help="розмір одного повідомлення, байтів")
parser.add_argument("--rto", type=float, default=RTO, help="таймер повтору, с")
parser.add_argument("--window", type=int, default=16, help="window: скільки пакетів можна мати «в польоті»")
parser.add_argument("--gap", type=float, default=0.01,
                    help="naive: пауза між sendto, с (щоб перестановки були локальними, а не «все навпаки»)")
parser.add_argument("--log", type=int, default=8, help="скільки подій повтору показати (решту лише порахувати)")
args = parser.parse_args()
port = args.port or (TCP_PORT if args.mode == "tcp" else UDP_PORT)
msgs = {i: make_message(i, args.size) for i in range(1, args.count + 1)}
stats = {"sent": 0, "retx": 0, "logged": 0}


def send(sock, seq, retx=False, why=""):
    sock.send(pack(DATA, seq, msgs[seq]))
    stats["sent"] += 1
    if retx:
        stats["retx"] += 1
        if stats["logged"] < args.log:
            stats["logged"] += 1
            print("  повтор #{:<3} {}".format(seq, why), flush=True)
        elif stats["logged"] == args.log:
            stats["logged"] += 1
            print("  ... (далі повтори лише рахуємо)", flush=True)


def recv_packet(sock, timeout):
    """Наступний пакет від приймача або None, якщо таймер вийшов."""
    sock.settimeout(max(timeout, 0.001))
    try:
        return unpack(sock.recv(2048))
    except socket.timeout:
        return None
    except ConnectionRefusedError:
        # підключений UDP-сокет отримав ICMP «port unreachable»: приймача немає
        print("Приймача на порту {} немає (ICMP port unreachable)".format(port))
        raise SystemExit(1)


def send_fin(sock):
    """FIN теж може загубитись — тож і його повторюємо, доки не прийде відповідь."""
    for _ in range(20):
        sock.send(pack(FIN, args.count))
        pkt = recv_packet(sock, args.rto)
        if pkt and pkt[0] == FIN:
            return True
    return False


def summary(t0, delivered_note):
    took = time.monotonic() - t0
    total = args.count * args.size
    print("Готово: {} повідомлень, {} байтів за {:.2f} с ({:.1f} КБ/с)".format(
        args.count, total, took, total / 1024 / took), flush=True)
    if args.mode != "tcp":
        print("Відправлено дейтаграм DATA: {} (з них повторів: {})".format(stats["sent"], stats["retx"]), flush=True)
    print(delivered_note, flush=True)


if args.mode == "tcp":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        t0 = time.monotonic()
        try:
            sock.connect((args.host, port))
        except ConnectionRefusedError:
            print("Порт {} закритий: спершу запустіть receiver.py tcp".format(port))
            raise SystemExit(1)
        sock.sendall(b"".join(msgs[i] for i in sorted(msgs)))  # усе одним викликом
        sock.shutdown(socket.SHUT_WR)  # FIN: «більше даних не буде»
        sock.recv(1)  # приймач закриває з'єднання, коли прочитав усе: це і є «доставлено»
    summary(t0, "Повтори, порядок, дублікати: усе це зробило ядро (TCP), застосунок не бачив нічого")
    raise SystemExit(0)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    # «підключений» UDP: send() без адреси, а recv() приймає лише від приймача
    sock.connect((args.host, port))
    t0 = time.monotonic()

    if args.mode == "naive":
        for seq in sorted(msgs):
            sock.send(pack(DATA, seq, msgs[seq]))  # ні підтвердження, ні повтору
            stats["sent"] += 1
            time.sleep(args.gap)
        print("Надіслано {} дейтаграм. Що з них дійшло — відправник не знає".format(stats["sent"]), flush=True)
        raise SystemExit(0)

    if args.mode == "saw":
        # Stop-and-wait: один пакет «в польоті»; наступний лише після ACK на попередній
        print("Stop-and-wait: надсилаємо пакет, чекаємо ACK до {:.0f} мс, інакше повтор".format(args.rto * 1000), flush=True)
        for seq in sorted(msgs):
            send(sock, seq)
            deadline = time.monotonic() + args.rto
            while True:
                pkt = recv_packet(sock, deadline - time.monotonic())
                if pkt is None:  # таймер вийшов: загубився або DATA, або ACK — ми не знаємо, що саме
                    send(sock, seq, retx=True, why="(таймаут {:.0f} мс без ACK)".format(args.rto * 1000))
                    deadline = time.monotonic() + args.rto
                elif pkt[0] == ACK and pkt[1] == seq:
                    break
                # інакше: запізнілий або продубльований ACK на старий пакет — ігноруємо

    else:
        # Ковзне вікно (selective repeat): до --window пакетів «в польоті», свій таймер у кожного
        print("Ковзне вікно: до {} пакетів без ACK одночасно, таймер {:.0f} мс на кожен".format(
            args.window, args.rto * 1000), flush=True)
        base, next_seq = 1, 1
        in_flight = {}  # номер -> коли надіслано востаннє
        acked = set()
        while base <= args.count:
            while next_seq < base + args.window and next_seq <= args.count:
                send(sock, next_seq)
                in_flight[next_seq] = time.monotonic()
                next_seq += 1
            oldest = min(in_flight.values())
            pkt = recv_packet(sock, oldest + args.rto - time.monotonic())
            if pkt is not None:
                if pkt[0] == ACK and pkt[1] in in_flight:
                    del in_flight[pkt[1]]
                    acked.add(pkt[1])
                    while base in acked:  # зсуваємо вікно через усі підтверджені поспіль
                        base += 1
                continue
            now = time.monotonic()
            for seq, sent_at in sorted(in_flight.items()):
                if now - sent_at >= args.rto:
                    send(sock, seq, retx=True, why="(таймаут; вікно стоїть на #{})".format(base))
                    in_flight[seq] = now

    ok = send_fin(sock)
    summary(t0, "Приймач підтвердив кінець (FIN)" if ok else "FIN так і не підтвердили (20 спроб)")
