# Builds 02-cwnd-chart.html from the REAL recorded sampler table (no numbers typed by hand).
import re, math, sys
src = sys.argv[1]
rows = []
for line in open(src, encoding="utf-8"):
    m = re.match(r"\s*(\d+)\s+(\d+)\s+(?:×[\d.]+\s+)?(\S+)\s+([\d.]+)", line)
    if m: rows.append((int(t := m.group(1)), int(m.group(2))))
W, H, L, R, T, B = 560, 400, 64, 24, 48, 56
tmax = 1600
def panel(ox, title, ylab, yfun, yticks, ytl, labels=True):
    x = lambda t: ox + L + (W - L - R) * t / tmax
    o = [f'<text x="{ox+L}" y="28" class="pt">{title}</text>']
    for v, lab in zip(yticks, ytl):
        yy = yfun(v)
        o.append(f'<line x1="{ox+L}" x2="{ox+W-R}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid"/>')
        o.append(f'<text x="{ox+L-8}" y="{yy+5:.1f}" class="tick" text-anchor="end">{lab}</text>')
    for t in range(0, 1601, 400):
        o.append(f'<text x="{x(t):.1f}" y="{H-B+22}" class="tick" text-anchor="middle">{t}</text>')
    o.append(f'<line x1="{ox+L}" x2="{ox+W-R}" y1="{H-B}" y2="{H-B}" class="axis"/>')
    o.append(f'<text x="{ox+(L+W-R)/2}" y="{H-12}" class="al" text-anchor="middle">t, мс</text>')
    o.append(f'<text x="{ox+16}" y="{(T+H-B)/2}" class="al" text-anchor="middle" transform="rotate(-90 {ox+16} {(T+H-B)/2})">{ylab}</text>')
    pts = " ".join(f"{x(t):.1f},{yfun(c):.1f}" for t, c in rows)
    o.append(f'<polyline points="{pts}" class="line"/>')
    for t, c in rows:
        o.append(f'<circle cx="{x(t):.1f}" cy="{yfun(c):.1f}" r="5" class="pt0"/>')
        if labels: o.append(f'<text x="{x(t)-8:.1f}" y="{yfun(c)-10:.1f}" class="lab" text-anchor="end">{c}</text>')
    return "\n".join(o)
top = 1400
lin = lambda c: (H - B) - (H - B - T) * c / top
lo, hi = math.log2(8), math.log2(2048)
lg = lambda c: (H - B) - (H - B - T) * (math.log2(c) - lo) / (hi - lo)
svg = [panel(0, "Звичайна шкала: експонента", "cwnd, сегментів", lin, [0, 400, 800, 1200], ["0", "400", "800", "1200"]),
       panel(W + 20, "Шкала log₂: рівні сходинки ×2", "cwnd, сегментів (log₂)", lg,
             [10, 20, 40, 80, 160, 320, 640, 1280], ["10", "20", "40", "80", "160", "320", "640", "1280"], labels=False)]
html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#ffffff}}
.wrap{{padding:20px 24px 12px;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;color:#1f2328}}
h1{{font-size:20px;margin:0 0 2px;font-weight:600}} .sub{{font-size:14px;color:#5b636e;margin:0 0 6px}}
.pt{{font-size:16px;font-weight:600;fill:#1f2328}} .tick{{font-size:13px;fill:#5b636e}} .al{{font-size:13px;fill:#5b636e}}
.grid{{stroke:#e6e8eb}} .axis{{stroke:#8c959f}} .line{{fill:none;stroke:#d97706;stroke-width:3}}
.pt0{{fill:#d97706;stroke:#fff;stroke-width:2}} .lab{{font-size:13px;font-weight:600;fill:#9a5200}}
</style></head><body><div class="wrap">
<h1>cwnd відправника (сервер, порт 9103), реальні вибірки ss -tin</h1>
<p class="sub">./run_demo.sh, netem delay 100 мс (RTT ≈ 202 мс), 3 МБ; дані: recorded/cwnd_table_default.txt</p>
<svg width="{2*W+20}" height="{H}" viewBox="0 0 {2*W+20} {H}">{"".join(svg)}</svg></div></body></html>'''
open("02-cwnd-chart.html", "w", encoding="utf-8").write(html)
print(rows)
