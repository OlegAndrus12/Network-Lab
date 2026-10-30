"""Рахує події втрат у pcap так, як їх позначає Wireshark (через tshark).

Працює і в контейнері, і на Mac, якщо встановлено Wireshark:
    python3 analyze.py capture.pcap
    python3 analyze.py capture.pcap --tshark /Applications/Wireshark.app/Contents/MacOS/tshark
"""
import argparse
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description="Підсумок ретрансляцій у pcap")
parser.add_argument("pcap", nargs="?", default="capture.pcap")
parser.add_argument("--tshark", default=None, help="шлях до tshark")
parser.add_argument("--examples", type=int, default=4, help="скільки прикладів кожної події показати")
parser.add_argument("--rto-gap", type=float, default=0.2,
                    help="пауза перед повтором, після якої вважаємо його RTO, с (мінімальний RTO у Linux = 0.2)")
args = parser.parse_args()

TSHARK = args.tshark or shutil.which("tshark") or "/Applications/Wireshark.app/Contents/MacOS/tshark"
# tcp.time_delta = час від попереднього кадру цього ж з'єднання (потрібна ця опція)
# без HTTP-дешифратора колонка Info показує Seq/Len замість "Continuation"
OPTS = ["-o", "tcp.calculate_timestamps:TRUE", "--disable-protocol", "http"]

RTO = (f"tcp.analysis.retransmission && !tcp.analysis.fast_retransmission"
       f" && tcp.time_delta >= {args.rto_gap}")

# (фільтр відображення Wireshark, пояснення)
EVENTS = [
    ("tcp.analysis.lost_segment", "TCP Previous segment not captured: діра в seq, сегмент загубився"),
    ("tcp.analysis.duplicate_ack", "TCP Dup ACK #N: отримувач повторює той самий ack"),
    ("tcp.analysis.duplicate_ack_num == 3", "  з них саме третій дубль (#3)"),
    ("tcp.options.sack_le", "ACK із блоками SACK (які байти ПІСЛЯ діри вже є)"),
    ("tcp.analysis.fast_retransmission", "TCP Fast Retransmission: повтор після дубльованих ACK"),
    ("tcp.analysis.retransmission", "TCP Retransmission: усі інші повтори (RTO, TLP, RACK)"),
    (RTO, f"  з них після паузи >= {args.rto_gap} с, тобто таймер RTO"),
    ("tcp.analysis.out_of_order", "TCP Out-Of-Order: повтор, що прийшов дуже швидко після діри"),
]


def tshark(*extra):
    try:
        res = subprocess.run([TSHARK, "-r", args.pcap, *OPTS, *extra],
                             capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit(f"tshark не знайдено ({TSHARK}). Встановіть Wireshark або запустіть у контейнері.")
    return [line for line in res.stdout.splitlines() if line.strip()]


total = len(tshark("-T", "fields", "-e", "frame.number"))
print(f"Усього кадрів у {args.pcap}: {total}\n")
print(f"{'кадрів':>7}  {'фільтр Wireshark':<62} що це")
for flt, text in EVENTS:
    # Fast Retransmission у Wireshark теж має позначку retransmission, тому віднімаємо
    shown = flt if flt != "tcp.analysis.retransmission" else flt + " && !tcp.analysis.fast_retransmission"
    print(f"{len(tshark('-Y', shown, '-T', 'fields', '-e', 'frame.number')):>7}  {shown:<62} {text}")

# Приклади: так само, як колонка Info у Wireshark
COLS = ["-T", "fields", "-E", "separator=/t", "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "tcp.time_delta", "-e", "tcp.srcport", "-e", "tcp.dstport", "-e", "_ws.col.info"]
for title, flt in [("Перша швидка ретрансляція і що їй передувало", None),
                   ("Ретрансляції за таймером RTO", RTO)]:
    print(f"\n--- {title} ---")
    if flt is None:
        first = tshark("-Y", "tcp.analysis.fast_retransmission", "-T", "fields", "-e", "frame.number")
        if not first:
            print("(немає)")
            continue
        n = int(first[0])
        seq = tshark("-Y", f"frame.number == {n}", "-T", "fields", "-e", "tcp.seq")[0]
        # «діра»: перший сегмент ПІСЛЯ втраченого (найменший seq, більший за повторений)
        after = [line.split() for line in tshark(
            "-Y", f"tcp.analysis.lost_segment && frame.number < {n} && tcp.seq > {seq}",
            "-T", "fields", "-e", "tcp.seq", "-e", "frame.number")]
        start = min(after, key=lambda x: int(x[0]))[1] if after else n - 10
        # діра, усі ACK «чекаю байт seq» (оригінал і дублі) і сам повтор
        flt = (f"frame.number >= {start} && frame.number <= {n} && "
               f"(frame.number == {start} || (tcp.len == 0 && tcp.ack == {seq}) || frame.number == {n})")
    rows = tshark("-Y", flt, *COLS)
    if not rows:
        print("(немає)")
    limit = args.examples * 3 if title.startswith("Перша") else args.examples
    if len(rows) > limit and title.startswith("Перша"):  # довгий ряд дублів ACK: скорочуємо посередині
        rows = rows[: limit - 3] + ["…"] + rows[-2:]
    elif len(rows) > limit:
        rows = rows[:limit] + [f"… і ще {len(rows) - limit}"]
    for row in rows:
        if row.startswith("…"):
            print("  " + row)
            continue
        num, t, dt, sp, dp, info = row.split("\t", 5)
        # dt = пауза від попереднього кадру цього з'єднання: для RTO вона >= 0.2 с
        print(f"{num:>5} {float(t):7.3f}s (+{float(dt):.3f})  {sp:>5} → {dp:<5}  {info[:100]}")

print("\n--- Analyze → Expert Information (tshark -z expert): групи Warns і Notes ---")
dup_tail = 0  # Dup ACK #4, #5, ... зводимо в один рядок
for line in tshark("-q", "-z", "expert,note"):
    if line.startswith(("Warns", "Notes")):
        if dup_tail and line.startswith("Notes"):
            print(f"{dup_tail:>12}   Sequence                TCP  Duplicate ACK (#4 і далі, разом)")
        print(line)
    elif "Sequence" in line:
        count, summary = int(line.split()[0]), line
        num = summary.rsplit("(#", 1)[-1].rstrip(")") if "Duplicate ACK (#" in summary else ""
        if num.isdigit() and int(num) > 3:
            dup_tail += count
        else:
            print(line)
if dup_tail:
    print(f"{dup_tail:>12}   Sequence                TCP  Duplicate ACK (#4 і далі, разом)")
