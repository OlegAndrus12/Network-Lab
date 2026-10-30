#!/usr/bin/env python3
"""Generate slide-image HTML from REAL demo data (expected_output.txt + tshark on sample_*.pcap).
Run from anywhere: python3 slides/src/gen.py. Nothing here is typed by hand except annotations."""
import html, re, subprocess, pathlib

HERE = pathlib.Path(__file__).resolve().parent
DEMO = HERE.parent.parent
TSHARK = "/Applications/Wireshark.app/Contents/MacOS/tshark"
OUT = (DEMO / "expected_output.txt").read_text().splitlines()
E = html.escape

CSS = """
*{box-sizing:border-box} html,body{margin:0;background:#1e1e1e}
body{font:16px/1.5 Menlo,"DejaVu Sans Mono",monospace;color:#d4d4d4;display:inline-block}
.win{background:#1e1e1e;border-radius:10px;overflow:hidden;display:inline-block}
.bar{background:#323233;padding:9px 14px;display:flex;align-items:center;gap:8px;color:#9d9d9d;font-size:13px}
.d{width:12px;height:12px;border-radius:50%;display:inline-block}
.t{margin-left:10px}
pre{margin:0;padding:24px;font:inherit;white-space:pre}
.p{color:#6a9955}.c{color:#dcdcaa}.h{color:#569cd6}.g{color:#6fd28e;font-weight:bold}
.r{color:#ff6b6b;font-weight:bold}.y{color:#e8b64a;font-weight:bold}.v{color:#d39af0;font-weight:bold}
.a{color:#8a8a8a}.cut{color:#6a6a6a}
table{border-collapse:collapse;margin:0 24px 24px;font-size:15px}
th{background:#e8e8e8;color:#222;text-align:left;font-weight:normal;padding:4px 10px;border-right:1px solid #c8c8c8}
td{padding:2px 10px;white-space:nowrap}
tr.n td{background:#e7e6ff;color:#12272e}
tr.b td{background:#12272e;background:#000;color:#ff5f5f}
tr.k td{background:#1e1e1e;color:#6a6a6a;text-align:left}
td.note{background:#1e1e1e!important;color:#9a9a9a!important;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;font-size:15px}
td.num{text-align:right}
.cap{padding:14px 24px 10px;color:#9a9a9a;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;font-size:15px}
.hl{background:#5a1a1a;color:#fff;border-radius:3px;padding:0 3px;font-weight:bold}
.hlg{background:#1d4a2a;color:#fff;border-radius:3px;padding:0 3px;font-weight:bold}
"""

def page(title, body):
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="win"><div class="bar"><span class="d" style="background:#ff5f56"></span><span class="d" style="background:#ffbd2e"></span><span class="d" style="background:#27c93f"></span><span class="t">{E(title)}</span></div>{body}</div><script>var r=document.querySelector('.win').getBoundingClientRect();document.title=Math.ceil(r.width)+'x'+Math.ceil(r.height)</script></body></html>"""

def L(n):  # line n (1-based) of expected_output.txt, tabs expanded
    return OUT[n - 1].expandtabs(8)

# ---------- 01: run_demo.sh output, kernel counters ----------
def ann(s, a, cls=None):
    return f"{s}  <span class='a'>← {E(a)}</span>"
def line_for(prefix, start=1, end=len(OUT)):
    for i in range(start, end + 1):
        if OUT[i - 1].strip().startswith(prefix):
            return i
    raise SystemExit("not found: " + prefix)

g = line_for("# G.")
rows = [
    "<span class='p'>$</span> <span class='c'>PCAP=sample_sack.pcap ./run_demo.sh</span>   <span class='a'># 5% втрат, 5 мс, MTU 1500, SACK</span>",
    f"<span class='h'>{E(L(11))}</span>",
    "<span class='cut'>…</span>",
    f"<span class='h'>{E(L(15))}</span>",
    ann(E(L(16)).replace("5.357760 с", "<span class='y'>5.357760 с</span>"), "з 5% втрат"),
    ann(E(L(17)), "кадри, які побачить Wireshark"),
    "",
    f"<span class='h'>{E(L(20))}</span>",
    ann(E(L(21)).replace("66", "<span class='r'>66</span>", 1), "спосіб 1: дубльовані ACK"),
    E(L(22)),
    E(L(24)),
    ann(E(L(26)).replace("3", "<span class='v'>3</span>", 1), "спосіб 2: таймер RTO"),
    E(L(27)),
    "",
    "<span class='p'>$</span> <span class='c'>LOSS=0% ./run_demo.sh</span>   <span class='a'># те саме, але без втрат</span>",
]
gl = [line_for("отримано", g)]
rows.append(ann(E(L(gl[0])).replace("0.361000 с", "<span class='g'>0.361000 с</span>"), "у ~15 разів швидше"))
rows.append(E(L(line_for("TcpRetransSegs", g))))
(HERE / "01-run-counters.html").write_text(page("./run_demo.sh  (Docker, Linux 6.12, tc netem)", "<pre>" + "\n".join(rows) + "</pre>"))

# ---------- tshark helper ----------
def tshark(pcap, flt):
    out = subprocess.run([TSHARK, "-r", str(DEMO / pcap), "--disable-protocol", "http", "-o", "tcp.calculate_timestamps:TRUE",
                          "-Y", flt, "-T", "fields", "-E", "separator=|", "-e", "frame.number", "-e", "frame.time_relative",
                          "-e", "tcp.time_delta", "-e", "_ws.col.Info"], capture_output=True, text=True).stdout
    res = []
    for ln in out.splitlines():
        no, t, dt, info = ln.split("|", 3)
        info = re.sub(r" (Win|TSval|TSecr)=\d+", "", info)  # trimmed for width (noted on the slide)
        res.append((int(no), float(t), float(dt), info))
    return res

def table(rows, notes, gap_rows=(), hl_dt=(), show_dt=True):
    h = ["<table><tr><th>No.</th><th>Time</th>" + ("<th>Δt</th>" if show_dt else "") + "<th>Info</th><th style='background:#1e1e1e;border:0'></th></tr>"]
    prev = None
    for no, t, dt, info in rows:
        if prev is not None and no != prev + 1:
            h.append("<tr class='k'><td>…</td>" + "<td></td>" * (3 if show_dt else 2) + "<td class='note'></td></tr>")
        prev = no
        cls = "b" if info.startswith("[TCP ") else "n"
        dts = f"{dt:.3f}"
        if no in hl_dt:
            dts = f"<span class='hl'>{dts}</span>"
        h.append(f"<tr class='{cls}'><td class='num'>{no}</td><td>{t:.6f}</td>{f"<td class='num'>{dts}</td>" if show_dt else ""}<td>{E(info)}</td>"
                 f"<td class='note'>{('← ' + E(notes[no])) if no in notes else ''}</td></tr>")
    h.append("</table>")
    return "".join(h)

CAP = "tshark 4.6.9, текстовий вивід; кольори як у Wireshark (правило «Bad TCP»). Поля Win/TSval/TSecr прибрано для ширини."

# ---------- 02: first loss -> dup ACKs -> fast retransmission ----------
r = tshark("sample_sack.pcap", "frame.number in {7, 12, 14, 15, 16, 17, 18, 21, 26}")
notes = {7: "діра: байти 207–1654 загубились", 12: "друга діра",
         14: "«чекаю байт 207»", 15: "той самий Ack=207 + SACK", 17: "третій дубль",
         21: "SACK: 2 блоки = 2 діри", 26: "повтор через 6 мс після Dup ACK #3"}
cmd = "$ tshark -r sample_sack.pcap --disable-protocol http -Y 'frame.number <= 27'   (вибрані рядки)"
(HERE / "02-fast-retransmit.html").write_text(page(cmd, f"<div class='cap'>{CAP}</div>" + table(r, notes, show_dt=False)))

# ---------- 03: RTO after 0.244 s / 0.288 s silence ----------
r = tshark("sample_sack.pcap", "frame.number >= 102 && frame.number <= 111 && !(frame.number in {107, 108})")
notes = {102: "останній ACK перед паузою", 103: "дані дійшли…", 104: "…але їхні ACK загубились",
         105: "тиша 0.244 с → спрацював RTO", 106: "D-SACK: «це в мене вже є»",
         109: "швидкий повтор (Wireshark: Out-Of-Order)", 110: "його ACK теж загубився: +0.288 с, знову RTO"}
cmd = "$ tshark -r sample_sack.pcap --disable-protocol http -o tcp.calculate_timestamps:TRUE -Y 'frame.number >= 102 && frame.number <= 111'"
(HERE / "03-rto.html").write_text(page(cmd, f"<div class='cap'>{CAP} Δt = tcp.time_delta, пауза від попереднього кадру з'єднання.</div>" + table(r, notes, hl_dt={105, 110})))
print("ok")
