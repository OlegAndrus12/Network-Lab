"""Знімає cwnd/ssthresh/rtt з `ss -tin` кожні ~20 мс і друкує чисту таблицю (тільки Linux).

Замінює `watch -n 0.2 "ss -ti '( sport = :9103 )'"`: той самий джерело даних, але з часом
і в рядок, щоб таблицю можна було записати й показати як запасний варіант.
"""
import argparse
import re
import subprocess
import sys
import time

if sys.platform != "linux":
    sys.exit("ss є лише в Linux. На macOS запускайте ./run_demo.sh (він використовує Docker)")

parser = argparse.ArgumentParser(description="Семплер cwnd з ss -tin")
parser.add_argument("--port", type=int, default=9103, help="порт сервера (відправника)")
parser.add_argument("--interval", type=float, default=0.02, help="період опитування, с")
parser.add_argument("--all", action="store_true", help="друкувати навіть рядки без змін")
parser.add_argument("--wait", type=float, default=60, help="скільки чекати на з'єднання, с")
args = parser.parse_args()

# сокет сервера: локальний порт = 9103 (sport), саме він відправляє дані;
# «connected» = усі стани, крім LISTEN: після close() сервер ще досилає дані у FIN-WAIT
CMD = ["ss", "-tinH", "state", "connected", f"( sport = :{args.port} )"]
FIELDS = {
    "cwnd": r"\bcwnd:(\d+)",
    "ssthresh": r"\bssthresh:(\d+)",
    "rtt": r"\brtt:([\d.]+)/",
    "mss": r"\bmss:(\d+)",
    "bytes_acked": r"\bbytes_acked:(\d+)",
    "unacked": r"\bunacked:(\d+)",
    "retrans": r"\bretrans:(\d+/\d+)",
}


def sample():
    out = subprocess.run(CMD, capture_output=True, text=True).stdout
    if "cwnd:" not in out:  # з'єднання ще/вже немає (або воно в SYN-RECV/TIME-WAIT)
        return None
    row = {}
    for name, rx in FIELDS.items():
        m = re.search(rx, out)
        row[name] = m.group(1) if m else None
    return row


def fmt(t, r, prev_cwnd):
    ss = r["ssthresh"]
    cwnd = int(r["cwnd"])
    # фаза: ssthresh з'являється лише після першого сигналу перевантаження
    if ss is None:
        phase = "slow start"
    elif r["retrans"] and not r["retrans"].startswith("0/"):
        phase = "втрата → повторна передача"  # є ще не підтверджені повтори
    elif cwnd < int(ss):
        phase = "slow start до ssthresh"
    else:
        phase = "уникнення перевантаження"
    grow = f"×{cwnd / prev_cwnd:.2f}" if prev_cwnd and cwnd != prev_cwnd else ""
    return (f"{t:7.0f} {cwnd:6d} {grow:>5} {ss or '—':>8} {float(r['rtt']):7.1f} "
            f"{int(r['bytes_acked'] or 0):12d} {r['unacked'] or '0':>7} {r['retrans'] or '0/0':>8}  {phase}")


print(f"Чекаю на з'єднання з портом {args.port} (ss -tin кожні {args.interval * 1000:.0f} мс)...", flush=True)
deadline = time.monotonic() + args.wait
while (r := sample()) is None:
    if time.monotonic() > deadline:
        sys.exit("З'єднання так і не з'явилося")
    time.sleep(0.005)

t0 = time.monotonic()
print(f"MSS = {r['mss']} байтів; cwnd рахується в сегментах (1 сегмент = MSS)")
print(f"{'t, мс':>7} {'cwnd':>6} {'ріст':>5} {'ssthresh':>8} {'rtt, мс':>7} {'bytes_acked':>12} "
      f"{'unacked':>7} {'retrans':>8}  фаза")
last_key, prev_cwnd, gone = None, None, 0
while True:
    t = (time.monotonic() - t0) * 1000
    if r is None:
        gone += 1
        if gone * args.interval > 0.5:  # з'єднання зникло: передачу завершено
            break
    else:
        gone = 0
        key = (r["cwnd"], r["ssthresh"], r["retrans"])
        if args.all or key != last_key:
            print(fmt(t, r, prev_cwnd), flush=True)
            prev_cwnd, last_key = int(r["cwnd"]), key
    time.sleep(args.interval)
    r = sample()
print("З'єднання закрито, семплер завершує роботу")
