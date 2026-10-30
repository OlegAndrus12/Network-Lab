"""Малює cwnd(t) і ssthresh(t) з таблиці sampler.py як inline SVG (для explanation.html).

Використання:  python3 plot_cwnd.py recorded/cwnd_table_loss.txt > chart.svg
               python3 plot_cwnd.py --log2 recorded/cwnd_table_default.txt > chart_log.svg
               (--log2: логарифмічна вісь, подвоєння стає рівними сходинками)
Кольори задаються класами (.cw, .st, .ax ...), тож світлу/темну тему визначає CSS сторінки.
"""
import math
import re
import sys

LOG = "--log2" in sys.argv
path = [a for a in sys.argv[1:] if a != "--log2"][0]

rows = []
for line in open(path, encoding="utf-8"):
    m = re.match(r"\s*(\d+)\s+(\d+)\s+(?:×[\d.]+\s+)?(\S+)\s+([\d.]+)", line)
    if m:
        t, cwnd, ss, rtt = m.groups()
        rows.append((int(t), int(cwnd), None if ss == "—" else int(ss), float(rtt)))

W, H, L, R, T, B = 720, 360, 56, 24, 20, 44
tmax = max(r[0] for r in rows) + 100
top = max(max(r[1], r[2] or 0) for r in rows)
x = lambda t: L + (W - L - R) * t / tmax
if LOG:  # вісь 8 ... 2048: кожна лінія сітки = ×2
    lo, hi = 3, math.ceil(math.log2(top))
    y = lambda v: T + (H - T - B) * (1 - (math.log2(v) - lo) / (hi - lo))
    yticks, ybase = [2 ** k for k in range(lo, hi + 1)], 2 ** lo
else:
    ymax = math.ceil(top * 1.1 / 500) * 500
    y = lambda v: T + (H - T - B) * (1 - v / ymax)
    yticks, ybase = list(range(0, ymax + 1, 500)), 0

out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="ct cd" class="chart">',
       '<title id="ct">cwnd over time, real samples</title>',
       f'<desc id="cd">Step chart of cwnd from {rows[0][1]} to {max(r[1] for r in rows)} segments '
       f'over {tmax / 1000:.1f} s; ssthresh appears after the first loss.</desc>']
for v in yticks:  # горизонтальна сітка
    out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
    out.append(f'<text class="tick" x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
for t in range(0, tmax, 500):
    out.append(f'<text class="tick" x="{x(t):.1f}" y="{H - B + 18}" text-anchor="middle">{t / 1000:g}</text>')
out.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{y(ybase):.1f}" y2="{y(ybase):.1f}"/>')
out.append(f'<text class="tick" x="{(L + W - R) / 2}" y="{H - 6}" text-anchor="middle">time since connect, s</text>')
out.append(f'<text class="tick" x="14" y="{(T + H - B) / 2}" text-anchor="middle" '
           f'transform="rotate(-90 14 {(T + H - B) / 2})">cwnd, segments{" (log scale)" if LOG else ""}</text>')


def steps(points):
    d = f"M{x(points[0][0]):.1f},{y(points[0][1]):.1f}"
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        d += f" H{x(t1):.1f} V{y(v1):.1f}"
    return d + f" H{x(tmax - 60):.1f}"


ss_pts = [(r[0], r[2]) for r in rows if r[2] is not None]
if ss_pts:
    out.append(f'<path class="st" d="{steps(ss_pts)}"/>')
out.append(f'<path class="cw" d="{steps([(r[0], r[1]) for r in rows])}"/>')
for t, cwnd, ss, rtt in rows:  # точки з підказками (нативний tooltip браузера)
    out.append(f'<circle class="pt" cx="{x(t):.1f}" cy="{y(cwnd):.1f}" r="4">'
               f'<title>t={t} ms  cwnd={cwnd}  ssthresh={ss or "—"}  rtt={rtt} ms</title></circle>')
out.append("</svg>")
print("\n".join(out))
