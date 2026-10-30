"""Пояснює вивід tcpdump для демо zero window.

Показує, як вікно сервера зменшується до 0, нумерує zero-window probes
з інтервалами між ними і знаходить window update, коли сервер почав читати.
Використання:  python3 annotate.py [--port 9101] capture.txt
"""
import argparse
import re
import sys

parser = argparse.ArgumentParser(description="Пояснення tcpdump для zero window")
parser.add_argument("file", nargs="?", default="-", help="вивід tcpdump -n -tt або -ttttt (- = stdin)")
parser.add_argument("--port", type=int, default=9101, help="порт сервера")
parser.add_argument("--live", action="store_true",
                    help="живий режим: лише рядки з win 0 і проби, одразу на екран")
args = parser.parse_args()

LINE = re.compile(r"^(\d+\.\d+|\d+:\d+:\d+\.\d+) IP (\S+)\.(\d+) > (\S+)\.(\d+): Flags \[([^\]]*)\](.*)$")
f = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8")

if args.live:
    # tail -f capture.txt | python3 annotate.py --live: друкуємо одразу, без підсумку.
    # Показуємо перше win 0, проби клієнта, відповіді «досі 0» і момент, коли вікно відкрилось.
    probe = re.compile(rf"\.{args.port}: Flags \[\.\], (seq \d+:\d+, )?ack \d+, win \d+, length [01]$")
    from_server = re.compile(rf"IP \S+\.{args.port} > ")
    zero = False
    for raw in sys.stdin:
        line = re.sub(r", options \[[^\]]*\]", "", raw.strip())
        if "Flags [R" in line:
            print("[tcpdump]", line, " <- RST: з'єднання скинуто", flush=True)
            break
        if "win 0," in line:
            zero = True
            print("[tcpdump]", line, flush=True)
        elif zero and probe.search(line):
            print("[tcpdump]", line, " <- проба", flush=True)
        elif zero and from_server.search(line) and " win " in line:
            print("[tcpdump]", line, " <- WINDOW UPDATE: вікно відкрилось", flush=True)
            break  # далі сотні звичайних сегментів, їх не показуємо
    sys.exit(0)


def to_seconds(ts):
    """Час tcpdump: -tt (епоха, 1792701855.836404) або -ttttt (00:00:00.252000)."""
    if ":" in ts:
        h, m, sec = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(sec)
    return float(ts)


rows = []
for raw in f:
    m = LINE.match(raw.strip())
    if not m:
        continue
    ts, _, sport, _, dport, flags, rest = m.groups()
    ws = re.search(r"wscale (\d+)", rest)
    rest = re.sub(r", options \[[^\]]*\]", "", rest)  # опції TCP лише заважають читати
    win = re.search(r"win (\d+)", rest)
    length = re.search(r"length (\d+)", rest)
    rows.append({
        "t": to_seconds(ts), "from_server": int(sport) == args.port, "flags": flags,
        "text": f"{'сервер' if int(sport) == args.port else 'клієнт'} > "
                f"{'клієнт' if int(sport) == args.port else 'сервер'}: [{flags}]{rest}",
        "win": int(win.group(1)) if win else None,
        "len": int(length.group(1)) if length else 0,
        "wscale": int(ws.group(1)) if ws else None,
        "ack": re.search(r"ack (\d+)", rest),
    })

if not rows:
    sys.exit("Порожньо: немає рядків tcpdump для цього порту")

t0 = rows[0]["t"]
# масштаб вікна (window scale) береться з SYN / SYN-ACK; оголошений win треба множити на 2^wscale
scale = {False: 0, True: 0}
for r in rows:
    if "S" in r["flags"] and r["wscale"] is not None:
        scale[r["from_server"]] = r["wscale"]

out = []
state = "normal"  # normal -> zero (вікно 0) -> open (після window update) -> closing
zero_t = None     # коли вперше прийшло win 0
probes, replies, silent = [], [], []  # статистика лише для першої «заморозки»
zero_phases = 0
pending = []      # рядки, які згортаємо: дані, а також звичайні ACK
MAX_ACKS = 8      # скільки ACK зі зменшенням вікна показати до першого win 0


def window_note(r):
    free = r["win"] << scale[True]
    return f"вікно: {r['win']} × {2 ** scale[True]} = {free} байтів вільно"


def summary(chunk):
    if not chunk:
        return
    data = [r for r in chunk if not r["from_server"] and r["len"] > 0]
    acks = len(chunk) - len(data)
    parts = [f"{len(data)} сегм. з даними ({sum(r['len'] for r in data)} байтів)"] if data else []
    parts += [f"{acks} ACK"] if acks else []
    out.append((chunk[0]["t"], f"   ... {' + '.join(parts)} ...", ""))


def flush():
    """Друкує згорнуте; до першого win 0 лишає кілька ACK, щоб було видно, як вікно меншає."""
    if state == "normal":
        acks = [i for i, r in enumerate(pending) if r["from_server"]]
        keep = set(acks[:: -(-len(acks) // MAX_ACKS) or 1] + acks[-1:])
        chunk = []
        for i, r in enumerate(pending):
            if i in keep:
                summary(chunk)
                chunk = []
                out.append((r["t"], r["text"], window_note(r)))
            else:
                chunk.append(r)
        summary(chunk)
    else:
        summary(pending)
    pending.clear()


for r in rows:
    # проба: Linux шле 0 байтів (seq на 1 менший), macOS/BSD шле 1 байт за межею вікна
    is_probe = not r["from_server"] and state == "zero" and r["len"] <= 1 and "S" not in r["flags"]
    is_data = (not r["from_server"] and r["len"] > 0 and not is_probe
               and "S" not in r["flags"] and "F" not in r["flags"])
    plain_ack = (r["from_server"] and r["win"] and "S" not in r["flags"] and "F" not in r["flags"]
                 and "R" not in r["flags"] and state in ("normal", "open"))
    fin_or_rst = "F" in r["flags"] or "R" in r["flags"]
    if state == "closing" and not fin_or_rst and r is not rows[-1]:
        pending.append(r)  # після FIN показуємо лише FIN/RST і останній ACK
        continue
    if state != "closing" and (is_data or plain_ack or (state == "open" and not r["from_server"]
                                                       and "F" not in r["flags"])):
        pending.append(r)  # згортаємо
        continue
    flush()
    note = ""
    if "R" in r["flags"]:
        note = "RST: сокет закрито з непрочитаними даними -> скидання з'єднання"
        state = "closing"
    elif "F" in r["flags"] or state == "closing":
        note = "FIN: закриття" if "F" in r["flags"] else "ACK на FIN"
        state = "closing"
    elif "S" in r["flags"]:
        note = "рукостискання" + (f", wscale {r['wscale']} (вікно × {2 ** r['wscale']})"
                                  if r["wscale"] is not None else "")
    elif r["from_server"] and r["win"] == 0:
        if state != "zero":
            note = "<<< ВІКНО = 0: «стоп, мій буфер повний»"
            state = "zero"
            zero_phases += 1
            if zero_phases == 1:
                zero_t = r["t"]
        else:
            note = "відповідь на пробу: досі win 0"
        if zero_phases == 1:
            replies.append(r["t"])
    elif r["from_server"] and state == "zero":
        note = f"<<< WINDOW UPDATE: вікно знову відкрите, вільно {r['win'] << scale[True]} байтів"
        state = "open"
    elif is_probe and zero_phases > 1:
        note = "zero-window probe"
    elif is_probe:
        prev = probes[-1] if probes else zero_t
        if probes and replies[-1] < probes[-1]:
            silent.append(len(probes))  # на попередню пробу сервер не відповів
        probes.append(r["t"])
        note = f"zero-window probe №{len(probes)}, +{r['t'] - prev:.3f} с"
    out.append((r["t"], r["text"], note))
flush()

width = max(len(t) for _, t, _ in out)
for i, (t, text, note) in enumerate(out, 1):
    print(f"{t - t0:8.3f} с  {text:<{width}}  {'← ' + note if note else ''}".rstrip())

print()
if probes:
    gaps = [f"{b - a:.3f}" for a, b in zip([zero_t] + probes, probes)]
    print(f"Проби клієнта (zero-window probes): {len(probes)}, інтервали, с: {', '.join(gaps)}")
    if silent:
        print(f"Без відповіді сервера: проба №{', №'.join(map(str, silent))} "
              f"(Linux обмежує такі ACK: net.ipv4.tcp_invalid_ratelimit = 500 мс)")
    rgaps = [f"{b - a:.3f}" for a, b in zip(replies, replies[1:])]
    print(f"Відповіді сервера 'win 0': {len(replies)}, інтервали, с: {', '.join(rgaps) or '—'}")
stall = [r for r in rows if r["from_server"] and r["win"] == 0 and r["ack"]]
if stall:
    a = int(stall[0]["ack"].group(1))
    print(f"Сервер застряг на ack {a}: у його буфері {a - 1} байтів, які додаток не прочитав")
