**Demo 08 «Порти вашого браузера просто зараз»**: attaches to the existing lecture slides «Порт — номер процесу на хості» and the QUIC / 443/udp point (Тема 4. TCP, UDP та порти).

---

## Slide 1. Один браузер, багато з'єднань до :443

**On-slide text**
- Сервер завжди слухає **:443**, а в клієнта кожне з'єднання має **свій локальний (ефемерний) порт**.
- 4 TCP-з'єднання до *того самого* сервера й порту, але з різних локальних портів: 57765, 52910, 63385, 54477.
- Ядро розрізняє сокети за п'ятіркою: протокол, локальна IP:порт, віддалена IP:порт.
- Команда (macOS): `lsof +c 0 -i -P -n | grep -iE 'chrome|safari'`

**Image**: `img/01-lsof-chrome.png`. Show whole. Emphasis is already baked in: the three shaded rows (same server 203.0.113.3, different green local ports). Caption under the image: «IP-адреси анонімізовано (203.0.113.x, 192.168.0.10); порти, PID і протоколи справжні».

**Simple diagram** (optional, to the right of or below the screenshot):
- Left: one big box «Ваш комп'ютер 192.168.0.10». Inside it, a smaller box «процес Chrome (PID 745)» with three small port tags stacked: `:52910`, `:63385`, `:54477` (green).
- Right: one box «Сервер 203.0.113.3» with a single port tag `:443` (yellow).
- Three arrows, one from each green tag to the same `:443` tag, each labelled «TCP».
- Under the arrows, one label: «сокет = (локальна IP:порт ↔ віддалена IP:порт)».
- Small grey note at the bottom of the computer box: «ефемерні порти 49152–65535 (macOS)».

**Speaker notes**
IP-адреса доставляє пакет до хоста, а порт доставляє його до конкретного сокета, тобто до процесу. Подивіться на три виділені рядки: той самий сервер, той самий порт 443, але локальні порти різні. Саме тому браузер може тримати десятки з'єднань з одним сервером і ядро їх не плутає. На macOS обов'язково додайте `+c 0`: без нього lsof обрізає назву процесу до «Google», і grep не знаходить нічого (0 рядків).

---

## Slide 2. QUIC = HTTP/3 поверх UDP :443

**On-slide text**
- Той самий номер порту 443, але інший протокол: **UDP**, а не TCP.
- Це QUIC, транспорт під HTTP/3: надійність і шифрування реалізовано в самому браузері.
- 3 400 838 байтів отримано через **один** UDP-сокет :443: це відеопотік, а не DNS.

**Image**: `img/04-quic-bytes.png`. Show whole; the shaded row with the yellow `3400838` is the focus. Optionally reuse `img/01-lsof-chrome.png` cropped to its first visible data line (`UDP 192.168.0.10:52189->203.0.113.1:443 ← QUIC = HTTP/3`) as a small inset; do not crop it anywhere else. Caption: «IP-адреси анонімізовано».

**Simple diagram** (optional): two horizontal stacks side by side.
- Left stack, labelled «HTTP/2», boxes top to bottom: «HTTP/2» → «TLS» → «TCP» → «IP», with the tag «tcp/443».
- Right stack, labelled «HTTP/3», boxes: «HTTP/3» → «QUIC (надійність + TLS 1.3)» → «UDP» → «IP», with the tag «udp/443».
- The QUIC box carries a small note «у браузері, не в ядрі».

**Speaker notes**
Chrome відкриває до тих самих серверів не лише TCP :443, а й UDP :443: це QUIC, на якому працює HTTP/3. UDP тут лише «конверт», який пропускають майже всі NAT і файрволи, а гарантії доставки, порядок і шифрування QUIC робить сам, у браузері. Подивіться на кількість байтів: понад 3 МБ через один UDP-сокет, тож це справжній потік даних. Якщо UDP :443 у вас немає, це нормально: браузер просто залишився на TCP (HTTP/2).

---

## Slide 3. Ефемерні порти: звідки беруться номери клієнта

**On-slide text**
- Локальний порт клієнта ОС вибирає сама з діапазону ефемерних портів.
- macOS / Windows / IANA: **49152–65535**; Linux: **32768–60999**.
- Chrome на macOS: порти 52189–63385, усі **12 з 12** у діапазоні ОС.

**Images**: `img/02-summary.png` (main, show whole: green = ports the browser uses, yellow = OS range) and `img/03-ephemeral-ranges.png` (secondary, smaller, or on a click/build: macOS vs Linux range side by side). Caption: «IP-адреси анонімізовано; Linux: контейнер Docker, 1.1.1.1 — публічний DNS Cloudflare».

**Try-it-yourself box** (small, bottom-right of the slide), title «Спробуйте самі»:
```
macOS:    lsof +c 0 -i -P -n | grep -iE 'chrome|safari'
Linux:    ss -tunp | grep ':443'
Windows:  netstat -ano | findstr :443      (не перевірено)
```

**Speaker notes**
Порт сервера ми знаємо заздалегідь (443), а порт клієнта ОС вибирає автоматично в момент connect() із діапазону ефемерних портів. На macOS це 49152–65535, і всі 12 портів Chrome у цей діапазон потрапили. У Linux діапазон за замовчуванням інший, 32768–60999, що видно з `ip_local_port_range` у контейнері. Відкрийте YouTube і запустіть команду зі «Спробуйте самі» на своєму ноутбуці: побачите те саме.

---

## Design notes (for the design agent)

- The four PNGs are real terminal output rendered at 2x. Place them unscaled or scaled down only; never upscale, never re-colour, never retype the output as text. Crop only where stated above.
- Highlight colour meaning (keep consistent in any diagram you draw): **yellow box** = remote port `443`; **green** = local ephemeral port; **blue** `TCP`; **orange** `UDP`; **yellow number** = key figure; **grey italic** `← …` = annotation (not part of the output); dark-blue shaded row = the row to talk about.
- Lines marked `…` are cuts; the comment lines `# …` in the images state which columns were dropped.
- Commands must stay exactly as written, including `+c 0` (without it the command finds 0 lines on macOS). Never use `lsof -i -P -n | grep -iE 'chrome|safari'` without `+c 0`.
- All addresses are anonymised (203.0.113.x, 192.168.0.10); each slide with a screenshot needs the small caption saying so. Do not invent other IPs, hostnames or user names.
- Keep commands, flags, `QUIC`, `HTTP/3`, `TCP`, `UDP` in Latin script; all other slide text in Ukrainian.
- Windows command is untested; keep the «(не перевірено)» mark.

## Facts (do not change; source in parentheses)

All from `08-browser-ports/expected_output.txt` (macOS 15, Chrome, 22.10.2026) unless noted.
- Slide command without `+c 0`: **0** lines found; with `+c 0` and the full browser pattern: **21** lines.
- Chrome network process «Google Chrome Helper (Aperitif)», PID **745**: **18** sockets; TCP → :443: **5**; UDP → :443 (QUIC): **3**; TCP → :80: **0**; TCP → :5228: **1**; UDP listening :5353 (mDNS): **9**.
- Second Chrome instance (Playwright), PID 46391: 3 sockets (1 UDP → :443, 1 TCP → :80, 1 TCP → :5228).
- Browser's local ephemeral ports: **52189–63385**; in OS range: **12 of 12**.
- macOS range (`sysctl net.inet.ip.portrange.first/last`): **49152–65535** (16384 ports).
- Linux in Docker (`/proc/sys/net/ipv4/ip_local_port_range`): **32768–60999** (28232 ports).
- IANA and Windows default: 49152–65535 (Windows not tested; `explanation.html`).
- Largest QUIC socket (netstat, PID 745, local port 58109): rxbytes **3 400 838**, txbytes 157 763.
- Same server 203.0.113.3:443 reached from 4 local TCP ports: 57765, 52910, 63385, 54477 (slide 1 image highlights the last 3).
- YouTube was not open during capture, so students will usually see more sockets.
