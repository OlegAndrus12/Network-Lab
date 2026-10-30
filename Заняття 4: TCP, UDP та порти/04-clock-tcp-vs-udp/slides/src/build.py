"""Builds terminal-style HTML pages from REAL lines of ../../expected_output.txt.
Lines are copied verbatim by line number; only colour spans and muted annotations are added."""
import html, re, pathlib

HERE = pathlib.Path(__file__).parent
SRC = (HERE / "../../expected_output.txt").resolve().read_text(encoding="utf-8").splitlines()

def L(n):  # 1-based line number in expected_output.txt
    return SRC[n - 1]

CSS = """
*{box-sizing:border-box}html,body{margin:0;background:#1e1e1e}
.win{background:#1e1e1e;color:#d4d4d4;font:16px/1.45 Menlo,"SF Mono",monospace;display:inline-block;min-width:100%}
.bar{background:#2d2d2d;padding:10px 16px;display:flex;align-items:center;gap:8px;color:#9a9a9a;font-size:14px}
.d{width:12px;height:12px;border-radius:50%;display:inline-block}
.t{margin-left:14px}
pre{margin:0;padding:20px 24px 24px;font:inherit;white-space:pre}
.p{color:#6a9955}.cmd{color:#ffffff;font-weight:bold}
.udp{color:#e2b155}.tcp{color:#4fc1ff}
.freeze{color:#ff6b6b;font-weight:bold}.burst{color:#ff6b6b}
.skip{color:#e2b155;font-weight:bold}
.ok{color:#89d185}.hl{color:#ffffff;font-weight:bold}
.note{color:#8a8f98;font-style:italic}.cut{color:#6b6b6b}
.lost{color:#ff6b6b;font-weight:bold}.retx{color:#ff6b6b;font-weight:bold}.dup{color:#e2b155;font-weight:bold}
"""

def colour(s):
    s = html.escape(s)
    s = re.sub(r"(‖ ЗАМЕРЗЛО на \d+ мс)", r'<span class="freeze">\1</span>', s)
    s = s.replace("← пачка", '<span class="burst">← пачка</span>')
    s = re.sub(r"(··· пропущено \d+ ті\w+ ···)", r'<span class="skip">\1</span>', s)
    s = s.replace("UDP :9104", '<span class="udp">UDP :9104</span>')
    s = s.replace("TCP :9114", '<span class="tcp">TCP :9114</span>')
    return s

def page(title, body, width):
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS} body{{width:{width}px}}</style></head><body><div class="win">
<div class="bar"><span class="d" style="background:#ff5f57"></span><span class="d" style="background:#febc2e"></span><span class="d" style="background:#28c840"></span><span class="t">{html.escape(title)}</span></div>
<pre>{body}</pre></div></body></html>"""

PROMPT = '<span class="p">$</span> <span class="cmd">{}</span>'
CUT = '<span class="cut">…</span>'

def note(text):
    return f'<span class="note">{html.escape(text)}</span>'

# ---------- 01: hero, two columns ----------
rows = [PROMPT.format("./run_demo.sh")]
rows += [colour(L(n)) for n in (6, 7, 8, 9)]
for n in range(10, 17):
    s = colour(L(n))
    if n == 12:
        s += "  " + note("← TCP мовчить")
    rows.append(s)
rows.append(CUT)
for n in range(105, 122):
    s = colour(L(n))
    if n == 110:
        s += "  " + note("← UDP іде далі")
    rows.append(s)
rows.append(CUT)
(HERE / "01-two-clocks.html").write_text(page("./run_demo.sh — netem: delay 50ms loss 10%", "\n".join(rows), 920), encoding="utf-8")

# ---------- 02: summary ----------
def summ(n):
    s = html.escape(L(n))
    s = s.replace("UDP:", '<span class="udp">UDP:</span>').replace("TCP:", '<span class="tcp">TCP:</span>')
    s = s.replace("втрачено 18 (12%)", '<span class="skip">втрачено 18 (12%)</span>')
    for k in ("макс 69 мс", "годинник НЕ зупинявся"):
        s = s.replace(k, f'<span class="ok">{k}</span>')
    for k in ("втрачено 0", "макс 857 мс", "зупинок (замерзань): 14", "найдовша 906 мс"):
        s = s.replace(k, f'<span class="freeze">{k}</span>')
    s = s.replace("медіана 51 мс", '<span class="hl">медіана 51 мс</span>')
    return s
rows = [PROMPT.format("./run_demo.sh"), CUT]
rows += [summ(n) for n in range(215, 223)]
rows[-6] += "   " + note("← дірки, але без зупинок")
rows[-3] += "   " + note("← медіана та сама, хвіст — ні")
(HERE / "02-summary.html").write_text(page("./run_demo.sh — підсумок того ж запуску", "\n".join(rows), 880), encoding="utf-8")

# ---------- 04: tcpdump under the hood ----------
def dump(n, cls, ann):
    raw = L(n).strip()
    raw = raw.replace(", ack 1, win 512", "").replace(", win 512", "")  # trim noise fields only
    s = html.escape(raw)
    if cls:
        s = f'<span class="{cls}">{s}</span>'
    return s + ("  " + note(ann) if ann else "")
rows = [CUT]
rows += [
    dump(413, "", "← ACK тіка #025"),
    dump(414, "", "← #027; #026 (537:558) загублено"),
    dump(415, "", "← #028"),
    dump(416, "dup", "← дубль ACK: «досі чекаю 537»"),
    dump(417, "", "← #029"),
    dump(418, "retx", "← повтор #026"),
    dump(419, "", "← ще один дубль ACK 537"),
    dump(420, "ok", "← дірку закрито: #026–#029 разом"),
]
(HERE / "04-tcpdump.html").write_text(page("tcpdump на lo у контейнері (окремий запуск, пакети вже після netem)", "\n".join(rows), 1030), encoding="utf-8")
print("ok")
