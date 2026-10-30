"""Lag-per-tick chart from ticks.json (parsed from section 1 of ../../expected_output.txt)."""
import json, pathlib

HERE = pathlib.Path(__file__).parent
d = json.loads((HERE / "ticks.json").read_text())
udp = {int(k): v for k, v in d["udp"].items()}
tcp = {int(k): v for k, v in d["tcp"].items()}

W, H = 1200, 560
L, R, T, B = 80, 30, 92, 80
pw, ph = W - L - R, H - T - B
YMAX = 900
x = lambda i: L + i / 149 * pw
y = lambda v: T + ph - v / YMAX * ph

svg = []
for v in range(0, YMAX + 1, 100):
    svg.append(f'<line x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e6e4df" stroke-width="1"/>')
    svg.append(f'<text x="{L-10}" y="{y(v)+5:.1f}" text-anchor="end" class="ax">{v}</text>')
for i in range(0, 150, 10):
    svg.append(f'<text x="{x(i):.1f}" y="{T+ph+24}" text-anchor="middle" class="ax">#{i:03d}</text>')
svg.append(f'<line x1="{L}" x2="{W-R}" y1="{y(0)}" y2="{y(0)}" stroke="#9a978f" stroke-width="1"/>')
svg.append(f'<text x="{L+pw/2}" y="{H-18}" text-anchor="middle" class="lab">номер тіка (1 тік = 100 мс, 15 с)</text>')
svg.append(f'<text x="22" y="{T+ph/2}" text-anchor="middle" class="lab" transform="rotate(-90 22 {T+ph/2})">лаг, мс</text>')

# TCP: continuous line over all 150 ticks
pts = " ".join(f"{x(i):.1f},{y(tcp[i]):.1f}" for i in range(150))
svg.append(f'<polyline points="{pts}" fill="none" stroke="#2a78d6" stroke-width="2.2" stroke-linejoin="round"/>')

# UDP: line segments broken at lost ticks, lost ticks as markers under the axis
seg = []
def flush():
    if len(seg) >= 2:
        svg.append('<polyline points="' + " ".join(seg) + '" fill="none" stroke="#eb6834" stroke-width="2.2"/>')
    elif len(seg) == 1:
        cx, cy = seg[0].split(",")
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="#eb6834"/>')
    seg.clear()
for i in range(150):
    if i in udp:
        seg.append(f"{x(i):.1f},{y(udp[i]):.1f}")
    else:
        flush()
        svg.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(0)+3}" y2="{y(0)+11}" stroke="#eb6834" stroke-width="3" stroke-linecap="round"/>')
flush()

# annotations (values from the run's summary)
mx = max(tcp, key=tcp.get)
svg.append(f'<text x="{x(mx)+10:.1f}" y="{y(tcp[mx])+5:.1f}" class="ann">TCP: #{mx:03d} прийшов із лагом {tcp[mx]} мс</text>')
svg.append(f'<line x1="{x(12):.1f}" x2="{x(12):.1f}" y1="{y(400)+8:.1f}" y2="{y(51)-6:.1f}" stroke="#9a978f" stroke-width="1"/>')
svg.append(f'<text x="{x(12)-6:.1f}" y="{y(400):.1f}" class="ann">UDP: лаг ≈ 51 мс увесь час, макс {max(udp.values())} мс</text>')

legend = """
<div class="lg"><span><i style="background:#2a78d6"></i>TCP :9114 — усі 150 тіків, але 14 замерзань</span>
<span><i style="background:#eb6834"></i>UDP :9104 — 132 з 150</span>
<span><b class="tk"></b>втрачений UDP-тік (18)</span></div>"""

page = f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>Лаг кожного тіка</title>
<style>
html,body{{margin:0;background:#fcfcfb}}
body{{width:{W}px;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;color:#1d1f23}}
h1{{font-size:24px;margin:0;padding:22px 30px 4px;font-weight:650}}
.sub{{color:#5d6470;font-size:15px;padding:0 30px}}
.lg{{display:flex;gap:28px;padding:10px 30px 0;font-size:15px;color:#3a3f47}}
.lg i{{display:inline-block;width:22px;height:4px;border-radius:2px;vertical-align:middle;margin-right:8px}}
.tk{{display:inline-block;width:3px;height:10px;background:#eb6834;border-radius:2px;vertical-align:middle;margin-right:8px}}
svg{{display:block;margin-top:-62px}}
.ax{{font-size:13px;fill:#6b6f76;font-family:Menlo,monospace}}
.lab{{font-size:14px;fill:#5d6470}}
.ann{{font-size:15px;fill:#1d1f23;font-weight:600}}
</style></head><body>
<h1>Лаг кожного тіка: TCP «пилка» проти рівного UDP</h1>
<div class="sub">Реальний запуск ./run_demo.sh, netem: delay 50ms loss 10%, 150 тіків (expected_output.txt, розділ 1)</div>
{legend}
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{''.join(svg)}</svg>
</body></html>"""
(HERE / "03-lag-chart.html").write_text(page, encoding="utf-8")
print("max tcp", mx, tcp[mx])
