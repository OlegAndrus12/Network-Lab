"""Приймач для демо «надійність поверх UDP»: що доходить сирим UDP і як це виправити."""
import argparse
import socket

from common import (ACK, COUNT, DATA, FIN, TCP_PORT, UDP_PORT, make_message,
                    message_numbers, pack, ranges, rows, unpack)

parser = argparse.ArgumentParser(description="Приймач: сирий UDP, надійний UDP або TCP")
parser.add_argument("mode", choices=["naive", "reliable", "tcp"],
                    help="naive: лише записати, що прийшло; reliable: ACK + відкинути дублікати + "
                         "впорядкувати; tcp: прочитати потік")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, help="за замовчуванням 9109 (udp) або 9119 (tcp)")
parser.add_argument("--count", type=int, default=COUNT, help="скільки повідомлень очікуємо")
parser.add_argument("--idle", type=float, default=1.0,
                    help="naive: стільки секунд тиші = відправник закінчив (у UDP немає «кінця з'єднання»)")
parser.add_argument("--log", type=int, default=8, help="reliable: скільки подій показати (решту лише порахувати)")
args = parser.parse_args()
port = args.port or (TCP_PORT if args.mode == "tcp" else UDP_PORT)
expected = list(range(1, args.count + 1))


def check_order(delivered):
    if delivered == expected:
        return "{} з {}, усі по порядку, без дублікатів ✓".format(len(delivered), args.count)
    return "{} з {} — НЕ збігається з 1..{} ✗".format(len(delivered), args.count, args.count)


if args.mode == "tcp":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, port))
        srv.listen(1)
        print("TCP-приймач слухає {}:{}".format(args.host, port), flush=True)
        conn, addr = srv.accept()
        with conn:
            data = bytearray()
            while True:
                chunk = conn.recv(65536)
                if not chunk:  # FIN від відправника: усе прочитано
                    break
                data += chunk
        # conn закрито => відправник бачить кінець і зупиняє секундомір
        print("Прочитано {} байтів від {}".format(len(data), addr), flush=True)
        print("Доставлено застосунку: {}".format(check_order(message_numbers(bytes(data)))), flush=True)
    raise SystemExit(0)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind((args.host, port))
    print("UDP-приймач ({}) слухає {}:{}".format(args.mode, args.host, port), flush=True)

    if args.mode == "naive":
        arrived = []
        sock.settimeout(None)  # першої дейтаграми чекаємо скільки завгодно
        while True:
            try:
                datagram, addr = sock.recvfrom(2048)
            except socket.timeout:
                break
            kind, seq, _ = unpack(datagram)
            if kind == DATA:
                arrived.append(seq)
            sock.settimeout(args.idle)
        # Позначки: * = дублікат (вже було), < = прийшов пізніше за більший номер
        seen, labels, dups, late = set(), [], [], []
        top = 0
        for seq in arrived:
            if seq in seen:
                labels.append("{}*".format(seq))
                dups.append(seq)
            elif seq < top:
                labels.append("{}<".format(seq))
                late.append(seq)
            else:
                labels.append(str(seq))
            seen.add(seq)
            top = max(top, seq)
        lost = [n for n in expected if n not in seen]
        print("Порядок надходження ({} дейтаграм; * дублікат, < не по порядку):".format(len(arrived)), flush=True)
        for line in rows(labels, per_row=20, width=5):
            print(line, flush=True)
        print("Загублено:      {:>3}  [{}]".format(len(lost), ranges(lost)), flush=True)
        print("Дублікати:      {:>3}  [{}]".format(len(dups), ranges(dups)), flush=True)
        print("Не по порядку:  {:>3}  [{}]".format(len(late), ranges(late)), flush=True)
        print("Застосунок отримав би {} повідомлень замість {}; помилок ОС — жодної".format(
            len(arrived), args.count), flush=True)
        raise SystemExit(0)

    # reliable: відповідаємо ACK на кожен DATA, відкидаємо дублікати, впорядковуємо в буфері
    next_seq = 1      # наступний номер, який чекає застосунок
    buffer = {}       # прийшли раніше за next_seq: чекають, поки закриється «дірка»
    delivered = []    # що ми віддали застосунку, по порядку
    acks = dup_count = buffered = logged = 0
    fin_from = None

    def log(text):
        global logged
        logged += 1
        if logged <= args.log:
            print("  " + text, flush=True)
        elif logged == args.log + 1:
            print("  ... (далі події лише рахуємо)", flush=True)

    sock.settimeout(None)
    while True:
        try:
            datagram, addr = sock.recvfrom(2048)
        except socket.timeout:
            break  # після FIN 1 с тиші: відправник отримав нашу відповідь
        kind, seq, payload = unpack(datagram)
        if kind == FIN:
            sock.sendto(pack(FIN, seq), addr)  # відповідь на FIN; повторний FIN = наша відповідь загубилась
            fin_from = addr
            sock.settimeout(1.0)
            continue
        if kind != DATA:
            continue
        sock.sendto(pack(ACK, seq), addr)  # ACK навіть на дублікат: попередній ACK міг загубитися
        acks += 1
        if seq < next_seq or seq in buffer:
            dup_count += 1
            log("#{:<3} дублікат -> відкинули (ACK ще раз)".format(seq))
            continue
        if payload != make_message(seq, len(payload)):
            log("#{:<3} пошкоджені дані?".format(seq))
        if seq > next_seq:
            buffer[seq] = payload
            buffered += 1
            log("#{:<3} прийшов раніше за #{} -> у буфер, чекаємо #{}".format(seq, next_seq, next_seq))
            continue
        delivered.append(seq)
        next_seq += 1
        while next_seq in buffer:  # «дірка» закрилась: віддаємо все, що чекало
            buffer.pop(next_seq)
            delivered.append(next_seq)
            next_seq += 1

    print("ACK надіслано: {}; дублікатів відкинуто: {}; чекали в буфері: {}".format(
        acks, dup_count, buffered), flush=True)
    print("Доставлено застосунку: {}".format(check_order(delivered)), flush=True)
    if fin_from is None:
        print("(FIN не прийшов)", flush=True)
