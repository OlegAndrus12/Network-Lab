#!/usr/bin/env python3
"""Генерує HTML-«термінали» для слайдів демо 07 з реального виводу (expected_output.txt).
Розмітка в рядках: {k:..} жовтий (ключове число), {g:..} зелений, {r:..} червоний,
{c:..} команда (блакитний), {a:..} анотація (приглушений), {m:..} приглушений текст."""
import html, re, sys, pathlib

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#1e1e1e}
.win{background:#1e1e1e;color:#d4d4d4;font:16px/1.5 Menlo,Monaco,'DejaVu Sans Mono',monospace;}
.bar{background:#2d2d2d;padding:10px 16px;display:flex;align-items:center;gap:8px;color:#9d9d9d;font-size:14px}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block}
.t{margin-left:12px;white-space:pre}
pre{padding:20px 24px 24px;white-space:pre;font:inherit}
.k{color:#1e1e1e;background:#ffd75f;border-radius:2px;box-shadow:0 0 0 2px #ffd75f;font-weight:bold}
.g{color:#7ee787}.r{color:#ff7b72}.c{color:#79c0ff}.a{color:#8b949e;font-style:italic}.m{color:#6e7681}
"""
TOK = re.compile(r"\{([kgrcam]):((?:[^{}])*)\}")

def render(line):
    out, pos = [], 0
    for m in TOK.finditer(line):
        out.append(html.escape(line[pos:m.start()]))
        out.append(f'<span class="{m.group(1)}">{html.escape(m.group(2))}</span>')
        pos = m.end()
    out.append(html.escape(line[pos:]))
    return "".join(out)

def page(title, body, font=16):
    lines = "\n".join(render(l) for l in body.strip("\n").split("\n"))
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{CSS} .win{{font-size:{font}px}}</style></head><body><div class="win">
<div class="bar"><span class="dot" style="background:#ff5f56"></span><span class="dot" style="background:#ffbd2e"></span><span class="dot" style="background:#27c93f"></span><span class="t">{html.escape(title)}</span></div>
<pre>{lines}</pre></div></body></html>"""

if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1]).read_text()
    title, font, body = src.split("\n", 2)
    pathlib.Path(sys.argv[2]).write_text(page(title, body, int(font)))
