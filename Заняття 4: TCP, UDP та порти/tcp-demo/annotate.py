"""Читає текстовий вивід tcpdump, прибирає options [...] і додає пояснення українською.

Використання:  python3 annotate.py capture.txt   або   tcpdump ... | python3 annotate.py
"""
import argparse
import re
import sys

LINE_RE = re.compile(r"(\S+)\.(\d+) > (\S+)\.(\d+): Flags \[([^\]]*)\]")
SEQ_RE = re.compile(r"seq (\d+)(?::(\d+))?")
ACK_RE = re.compile(r"ack (\d+)")
LEN_RE = re.compile(r"length (\d+)")
OPTIONS_RE = re.compile(r", options \[[^\]]*\]")


def number(regex, text):
    m = regex.search(text)
    return int(m.group(1)) if m else None


def annotate(lines, server_port):
    rows = []
    counts = {"handshake": 0, "data": 0, "ack": 0, "window": 0, "close": 0, "rst": 0}
    state = "start"  # start -> syn-ack -> established
    fin_end = {}  # сторона -> номер, який підтверджує її FIN (seq FIN + 1)
    news = {True: False, False: False}  # чи прийшло щось нове, ще не підтверджене цією стороною

    for raw in lines:
        m = LINE_RE.search(raw)
        if not m:
            continue  # пропускаємо службові рядки tcpdump
        line = OPTIONS_RE.sub("", raw.strip())
        flags = m.group(5)
        side = int(m.group(4)) == server_port  # True = від клієнта
        who = "клієнт" if side else "сервер"
        seq = SEQ_RE.search(line)
        ack = number(ACK_RE, line)
        length = number(LEN_RE, line) or 0
        acks_fin = ack is not None and ack == fin_end.get(not side)

        if "R" in flags:
            note, kind = "RST: порт закритий / з'єднання скинуто", "rst"
        elif flags == "S":
            note, kind, state = "SYN", "handshake", "syn"
        elif flags == "S.":
            note, kind, state = "SYN-ACK (ack = seq + 1)", "handshake", "syn-ack"
        elif "F" in flags:
            fin_end[side] = int(seq.group(1)) + 1  # FIN займає один номер
            if acks_fin and news[side]:
                note = f"FIN+ACK: {who} підтверджує FIN і теж закриває"
            elif (not side) in fin_end:
                note = f"FIN: {who} теж закриває свій напрям"
            else:
                note = f"FIN: {who} закриває свій напрям"
            kind = "close"
        elif length > 0:
            start, end = int(seq.group(1)), int(seq.group(2))
            note, kind = f"байти {start}–{end - 1}", "data"
        elif state == "syn-ack":
            note, kind, state = "ACK: рукостискання завершено", "handshake", "established"
        elif acks_fin and side in fin_end:
            note, kind = "ACK на FIN: з'єднання закрито", "close"
        elif acks_fin:
            note, kind = f"ACK на FIN (FIN зайняв номер {ack - 1})", "close"
        elif not news[side]:
            note, kind = "ACK без нових даних (оновлення вікна)", "window"
        else:
            note, kind = f"«чекаю байт {ack}»", "ack"

        # SYN, FIN і дані потребують підтвердження від іншої сторони
        if "S" in flags or "F" in flags or length > 0:
            news[not side] = True
        if ack is not None:
            news[side] = False
        counts[kind] += 1
        rows.append((line, note))

    width = max((len(line) for line, _ in rows), default=0)
    for i, (line, note) in enumerate(rows, 1):
        print(f"{i:2}. {line.ljust(width)}  ← {note}")

    summary = (f"Підсумок: рукостискання — {counts['handshake']}, "
               f"дані — {counts['data']}, ACK — {counts['ack']}, "
               f"закриття — {counts['close']}")
    if counts["window"]:
        summary += f", оновлення вікна — {counts['window']}"
    if counts["rst"]:
        summary += f", RST — {counts['rst']}"
    print("\n" + summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", help="файл із виводом tcpdump (інакше stdin)")
    parser.add_argument("--port", type=int, default=9000, help="порт сервера")
    args = parser.parse_args()
    with (open(args.file, encoding="utf-8") if args.file else sys.stdin) as f:
        annotate(f, args.port)
