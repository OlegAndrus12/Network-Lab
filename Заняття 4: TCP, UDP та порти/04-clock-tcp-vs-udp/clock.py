"""Годинник, що тікає по TCP і по UDP: що буде, коли мережа губить пакети.

Відправник кожні --interval секунд (типово 100 мс) надсилає «тік»: номер і поточний час.
Отримувач друкує: час відправлення, час отримання і лаг (отримання − відправлення).

Режими:
  python3 clock.py both                  # усе в одному процесі, дві колонки UDP | TCP
  python3 clock.py recv --proto udp      # окремий отримувач (термінал 1)
  python3 clock.py send --proto udp      # окремий відправник (термінал 2)
"""
import argparse
import queue
import socket
import sys
import threading
import time

UDP_PORT = 9104
TCP_PORT = 9114
COL = 40  # ширина однієї колонки у режимі both

# ---------- кольори (лише якщо вивід у термінал) ----------
USE_COLOR = sys.stdout.isatty()


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


GREEN, YELLOW, RED, CYAN, MAGENTA, DIM, BOLD = "32", "33", "1;31", "36", "1;35", "2", "1"


def plural_tick(n):
    """1 тік, 2 тіки, 5 тіків."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} тік"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} тіки"
    return f"{n} тіків"


def hms(ts):
    """Секунди з мілісекундами: 05.200 (хвилини опускаємо, щоб влізло в колонку)."""
    return time.strftime("%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"


def tick_line(seq, sent, recv):
    """Рядок одного тіку: номер, коли надіслано, коли отримано, лаг і смужка."""
    lag_ms = (recv - sent) * 1000
    bars = int(lag_ms // 50)
    bar = "■" * min(bars, 8) + ("»" if bars > 8 else "")
    text = f"#{seq:03d}  {hms(sent)}  {hms(recv)}  {lag_ms:4.0f}мс {bar}".rstrip()
    color = GREEN if lag_ms < 100 else YELLOW if lag_ms < 200 else RED
    return text, color


# ---------- логіка аналізу: однакова для both і recv ----------
class UdpTracker:
    """UDP: стежимо за номерами, щоб побачити дірки."""

    def __init__(self):
        self.expected = 0
        self.got = 0
        self.lost = 0
        self.max_lag = 0.0
        self.lags = []
        self.max_gap = 0

    def on_tick(self, seq, sent, recv):
        out = []  # список (текст, колір)
        if seq > self.expected:
            gap = seq - self.expected
            self.lost += gap
            self.max_gap = max(self.max_gap, gap)
            out.append((f"   ··· пропущено {plural_tick(gap)} ···", MAGENTA))
        elif seq < self.expected:
            out.append((f"   ··· тік #{seq:03d} прийшов не за порядком", MAGENTA))
            self.lost -= 1  # раніше рахували його втраченим
        self.expected = max(self.expected, seq + 1)
        self.got += 1
        lag = recv - sent
        self.lags.append(lag)
        self.max_lag = max(self.max_lag, lag)
        out.append(tick_line(seq, sent, recv))
        return out

    def summary(self, total):
        lost = total - self.got if total else self.lost
        lags = sorted(self.lags) or [0]
        return [
            f"UDP: отримано {self.got} з {total or self.expected}, "
            f"втрачено {lost} ({100 * lost / max(total or self.expected, 1):.0f}%)",
            f"     лаг: медіана {lags[len(lags) // 2] * 1000:.0f} мс, "
            f"макс {self.max_lag * 1000:.0f} мс",
            f"     найдовша дірка: {plural_tick(self.max_gap)}; годинник НЕ зупинявся",
        ]


class TcpTracker:
    """TCP: втрат не буває, але бувають зупинки (замерзання) і пачки."""

    def __init__(self, interval):
        self.interval = interval
        self.got = 0
        self.last_arrival = None
        self.max_lag = 0.0
        self.lags = []
        self.stalls = 0
        self.max_stall = 0.0
        self.bursts = 0
        self.in_burst = 0

    def on_tick(self, seq, sent, recv, same_read):
        out = []
        if self.last_arrival is not None:
            pause = recv - self.last_arrival
            # пауза помітно довша за інтервал: дані застрягли в ядрі
            if pause > 2 * self.interval:
                self.stalls += 1
                self.max_stall = max(self.max_stall, pause)
                out.append((f"   ‖ ЗАМЕРЗЛО на {pause * 1000:.0f} мс", RED))
        if same_read:  # прийшов разом із попереднім тіком
            if self.in_burst == 0:
                self.bursts += 1
            self.in_burst += 1
        else:
            self.in_burst = 0
        self.last_arrival = recv
        self.got += 1
        lag = recv - sent
        self.lags.append(lag)
        self.max_lag = max(self.max_lag, lag)
        text, color = tick_line(seq, sent, recv)
        if same_read:
            text += "  ← пачка"
            color = CYAN if lag < 0.1 else color
        out.append((text, color))
        return out

    def summary(self, total):
        lags = sorted(self.lags) or [0]
        return [
            f"TCP: отримано {self.got} з {total or self.got}, втрачено 0 (TCP перепосилає)",
            f"     лаг: медіана {lags[len(lags) // 2] * 1000:.0f} мс, "
            f"макс {self.max_lag * 1000:.0f} мс",
            f"     зупинок (замерзань): {self.stalls}, найдовша "
            f"{self.max_stall * 1000:.0f} мс; пачок: {self.bursts}",
        ]


# ---------- мережа ----------
def send_udp(host, port, interval, count, start):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for seq in range(count):
            time.sleep(max(0, start + seq * interval - time.time()))
            # кожен тік: окрема датаграма, вона або дійде цілою, або загубиться
            s.sendto(f"{seq} {time.time():.6f}\n".encode(), (host, port))


def send_tcp(host, port, interval, count, start):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # без Нейгла: кожен тік одразу йде окремим сегментом
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((host, port))
        for seq in range(count):
            time.sleep(max(0, start + seq * interval - time.time()))
            # TCP: потік байтів, тому межі тіків позначаємо символом \n
            s.sendall(f"{seq} {time.time():.6f}\n".encode())


def recv_udp(port, emit, stop):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("0.0.0.0", port))
        s.settimeout(0.2)
        while not stop.is_set():
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                continue
            now = time.time()
            seq, sent = data.decode().split()
            emit(int(seq), float(sent), now, False)


def recv_tcp(port, emit, ready=None):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(1)
        if ready:
            ready.set()
        conn, _ = srv.accept()
        with conn:
            buf = b""
            while True:
                data = conn.recv(4096)  # тут ядро тримає нас, поки не закриється дірка
                if not data:
                    break
                now = time.time()
                buf += data
                *lines, buf = buf.split(b"\n")
                # усі тіки з одного recv() прийшли в ту саму мить
                for i, line in enumerate(lines):
                    seq, sent = line.decode().split()
                    emit(int(seq), float(sent), now, i > 0)


# ---------- режими ----------
def mode_both(args):
    q = queue.Queue()
    udp, tcp = UdpTracker(), TcpTracker(args.interval)
    stop_udp = threading.Event()
    tcp_ready = threading.Event()

    def on_udp(seq, sent, now, _):
        for line in udp.on_tick(seq, sent, now):
            q.put(("L", line))

    def on_tcp(seq, sent, now, same):
        for line in tcp.on_tick(seq, sent, now, same):
            q.put(("R", line))

    t_udp = threading.Thread(target=recv_udp, args=(UDP_PORT, on_udp, stop_udp), daemon=True)
    t_tcp = threading.Thread(target=recv_tcp, args=(TCP_PORT, on_tcp, tcp_ready), daemon=True)
    t_udp.start()
    t_tcp.start()
    tcp_ready.wait()

    count = int(args.duration / args.interval)
    start = time.time() + 0.5
    s_udp = threading.Thread(target=send_udp, args=("127.0.0.1", UDP_PORT, args.interval, count, start))
    s_tcp = threading.Thread(target=send_tcp, args=("127.0.0.1", TCP_PORT, args.interval, count, start))

    hdr = "  №    надісл.  отрим.   лаг"
    print(c(f"{'UDP :' + str(UDP_PORT):<{COL}} │ TCP :{TCP_PORT}", BOLD))
    print(c(f"{hdr:<{COL}} │ {hdr}", DIM))
    print("─" * COL + "─┼─" + "─" * COL)
    s_udp.start()
    s_tcp.start()

    # Рядок екрана = один інтервал часу. Усе, що прийшло за інтервал, друкуємо поруч:
    # UDP ліворуч, TCP праворуч. Тож «тиша» праворуч і є замерзання TCP.
    # Межу інтервалу ставимо посередині між очікуваними приходами тіків.
    phase = (args.expect_delay_ms / 1000 + args.interval / 2) % args.interval
    slot = [0]

    def flush_slot():
        left, right = [], []
        while True:
            try:
                side, line = q.get_nowait()
            except queue.Empty:
                break
            (left if side == "L" else right).append(line)
        for i in range(max(len(left), len(right))):
            lt, lc = left[i] if i < len(left) else ("", "0")
            cell_l = c(f"{lt:<{COL}}", lc)
            if i < len(right):
                rt, rc = right[i]
                print(f"{cell_l} │ {c(rt.rstrip(), rc)}", flush=True)
            else:
                print(f"{cell_l} │", flush=True)

    def drain(until):
        while time.time() < until:
            slot[0] += 1
            boundary = start + slot[0] * args.interval + phase
            time.sleep(max(0, boundary - time.time()))
            flush_slot()

    slot[0] = -1
    # друкуємо, поки відправники працюють, потім даємо TCP дослати хвіст
    while s_udp.is_alive() or s_tcp.is_alive():
        drain(time.time() + 0.1)
    deadline = time.time() + 5
    while t_tcp.is_alive() and time.time() < deadline:
        drain(time.time() + 0.1)
    drain(time.time() + 0.3)
    stop_udp.set()

    print("─" * COL + "─┴─" + "─" * COL)
    print(c(f"Підсумок ({count} тіків по {args.interval * 1000:.0f} мс):", BOLD))
    for line in udp.summary(count):
        print(c(line, YELLOW))
    for line in tcp.summary(count):
        print(c(line, CYAN))


def mode_recv(args):
    if args.proto == "udp":
        tr = UdpTracker()
        port = args.port or UDP_PORT
    else:
        tr = TcpTracker(args.interval)
        port = args.port or TCP_PORT
    print(c(f"Отримувач {args.proto.upper()} слухає порт {port} (Ctrl+C: підсумок)", BOLD))
    print(c("  №    надісл.  отрим.   лаг", DIM))

    def emit(seq, sent, now, same):
        lines = tr.on_tick(seq, sent, now) if args.proto == "udp" else tr.on_tick(seq, sent, now, same)
        for text, color in lines:
            print(c(text, color), flush=True)

    try:
        if args.proto == "udp":
            recv_udp(port, emit, threading.Event())
        else:
            recv_tcp(port, emit)
            print(c("Відправник закрив з'єднання", DIM))
    except KeyboardInterrupt:
        print()
    for line in tr.summary(0):
        print(c(line, BOLD))


def mode_send(args):
    port = args.port or (UDP_PORT if args.proto == "udp" else TCP_PORT)
    count = int(args.duration / args.interval)
    print(f"Надсилаю {count} тіків по {args.proto.upper()} на {args.host}:{port} "
          f"кожні {args.interval * 1000:.0f} мс")
    fn = send_udp if args.proto == "udp" else send_tcp
    try:
        fn(args.host, port, args.interval, count, time.time())
    except ConnectionRefusedError:
        print(f"Порт {port} закритий: спочатку запустіть отримувача")
        raise SystemExit(1)
    print("Готово")


def main():
    p = argparse.ArgumentParser(description="Годинник по TCP і UDP під втратами")
    sub = p.add_subparsers(dest="mode")
    for name in ("both", "recv", "send"):
        sp = sub.add_parser(name)
        sp.add_argument("--interval", type=float, default=0.1, help="період тіків, с")
        sp.add_argument("--duration", type=float, default=15, help="скільки секунд тікати")
        if name == "both":
            sp.add_argument("--expect-delay-ms", type=float, default=0,
                            help="очікувана затримка мережі (netem), лише для вирівнювання рядків")
        if name != "both":
            sp.add_argument("--proto", choices=["udp", "tcp"], required=True)
            sp.add_argument("--port", type=int, default=0)
        if name == "send":
            sp.add_argument("--host", default="127.0.0.1")
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("both", "recv", "send", "-h", "--help"):
        argv = ["both"] + argv  # режим за замовчуванням
    args = p.parse_args(argv)
    {"both": mode_both, "recv": mode_recv, "send": mode_send}[args.mode](args)


if __name__ == "__main__":
    main()
