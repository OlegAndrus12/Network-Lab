# Демо 3: Slow start наживо (cwnd 10 → 20 → 40 … ×2 за RTT) — до слайда «Керування швидкістю» (таблиця cwnd), Тема 4

## Слайд 1. Що робимо: дивимось на cwnd відправника наживо

**On-slide text**
- Сервер (порт 9103) віддає файл 3 МБ клієнту в Docker-контейнері
- `tc netem delay 100ms` на `lo` → RTT ≈ 200 мс: кожен крок видно
- `ss -tin` кожні 20 мс читає cwnd **з боку відправника**
- cwnd немає в жодному заголовку: його знає лише ядро відправника

**Image**: none (diagram slide).

**Simple diagram** (draw):
- Left box «Сервер (відправник), порт 9103» with a small inner label «ядро: cwnd, ssthresh».
- Right box «Клієнт (отримувач)».
- Top arrow left → right: «сегменти з даними (+100 мс netem)».
- Bottom arrow right → left: «ACK (+100 мс netem)».
- Bracket spanning both arrows: «RTT ≈ 200 мс».
- Dashed arrow from the inner «cwnd» label to a small terminal icon: «`ss -tin` кожні 20 мс».

**Speaker notes**
Відправник може тримати «в польоті» не більше ніж min(cwnd, rwnd). rwnd отримувач повідомляє у кожному сегменті, а cwnd — це власна оцінка відправника, скільки витримає мережа; в пакетах її немає, тому читаємо її з ядра сервера через `ss`. Затримку 100 мс додаємо штучно, і на loopback вона діє в обидва боки: і дані, і ACK проходять через `lo`, тому RTT ≈ 200 мс (клієнт так і пише: рукостискання зайняло 203 мс).

## Слайд 2. Що бачимо: cwnd подвоюється щоRTT

**On-slide text**
- Старт: cwnd = 10 сегментів (IW10, RFC 6928)
- Кожен рядок ≈ один RTT (~200 мс), ріст ×2.00
- 10 → 1280 за 7 RTT ≈ 1,4 с
- ssthresh «—», retrans 0/0: втрат немає, чистий slow start

**Image**: `img/01-cwnd-table.png` (hero). Emphasise the yellow cwnd column and green ×2.00 column; if cropping, keep the header row and all 8 data rows. Optional on the same or the next slide: `img/02-cwnd-chart.png` (left panel = exponential curve, right panel on a log₂ axis = straight line, i.e. constant ×2 per RTT).

**Speaker notes**
Правило slow start: за кожен підтверджений сегмент cwnd +1 сегмент; ціле вікно підтверджується за один RTT, тому cwnd подвоюється. Linux рахує підтверджені сегменти, а не ACK-пакети: ACK у захопленні було 380 на 2173 сегменти з даними, а подвоєння все одно точне. Останній рядок: unacked 903 < cwnd 1280 — це не TCP, просто файл у 3 МБ закінчився. «Повільний» він лише порівняно з TCP до 1988 року, який одразу слав усе вікно отримувача.

## Слайд 3. Що робить відправник за кожен RTT (+ перевірка «на дроті»)

**On-slide text**
- Надіслати cwnd сегментів пачкою
- Чекати ~1 RTT на ACK
- +1 до cwnd за кожен підтверджений сегмент → cwnd ×2
- У захопленні те саме: 10, 20, 40 … 640 сегментів кожні ~202 мс

**Image**: `img/03-pcap-bursts.png` (tcpdump-based summary from capture.pcap printed by run_demo.sh; highlight the yellow segment counts and the blue timestamps 0.202 s apart).

**Simple diagram** (draw, left of the image or above it): a vertical time-sequence diagram, «Сервер» line on the left, «Клієнт» line on the right. Four rounds stacked downward, each a bundle of parallel arrows server → client labelled «10 сегментів», «20», «40», «80», with the bundle visibly thicker each round; between rounds a thin return arrow client → server labelled «ACK». A brace on the right side of each round: «1 RTT ≈ 200 мс». Caption under the diagram: «cwnd: 10 → 20 → 40 → 80».

**Speaker notes**
Це «драбина», яку малює Wireshark → Statistics → TCP Stream Graphs → Stevens: кожна вертикальна сходинка — одне вікно сегментів, надіслане підряд, сходинки через ~200 мс і щоразу вдвічі вищі. Питання до аудиторії: скільки RTT до 1280? log₂(1280/10) = 7. На RTT 20 мс той самий файл забрав би ~0,14 с: для коротких передач важить RTT, а не пропускна здатність — тому існують CDN і повторне використання з'єднань у HTTP/2 і HTTP/3.

## Слайд 4 (необов'язковий). Після slow start: втрата, ssthresh, уникнення перевантаження

**On-slide text**
- До 1280 — так само ×2
- Втрата → ssthresh задано (1477, потім 1034), повторна передача
- Далі уникнення перевантаження: ≈ +1% за RTT замість ×2
- Втрати тут — переповнення черги прийому `lo`, а не випадкові втрати netem

**Image**: `img/04-loss-run.png`. Highlight the orange ssthresh column, the red retrans/«втрата» rows, and the two equal 247 counters at the bottom.

**Speaker notes**
Запуск `./run_demo.sh --loss` передає 24 МБ: наступне подвоєння вже не вміщується в чергу прийому loopback (backlog ~1000 пакетів), пакети відкидаються — це схоже на переповнення буфера маршрутизатора, тобто справжнє перевантаження, а не штучна випадкова втрата. CUBIC (типовий у Linux) ставить ssthresh ≈ 0,7 × cwnd (у Reno — половина), під час відновлення cwnd тимчасово знижується (205), а потім стає рівним ssthresh = 1034 — рядок ×5.04 це завершення відновлення, а не slow start. Значення ssthresh і момент втрати змінюються від запуску до запуску, однакова лише частина до 1280.

---

## Design notes (for the design agent)

- All four PNGs are rendered at 2× device scale. Place them unscaled or scaled down only; never upscale. Do not retype, re-draw or "clean up" the terminal output: use the image.
- Highlight colours in terminal images: **yellow** = cwnd (segments), **green** = ×2.00 growth, **blue** = RTT / timestamps / netem delay, **orange** = ssthresh, **red** = retransmissions and loss phase, **grey italic** `← …` / `# …` = lecturer annotations, not program output. `…` marks lines that were cut.
- `02-cwnd-chart.png` is a light-background chart generated directly from `recorded/cwnd_table_default.txt` (generator: `slides/src/make_chart.py`). If you restyle it, regenerate from that file; do not hand-enter points.
- Must not change: any number, the commands (`./run_demo.sh`, `./run_demo.sh --loss`, `ss -tin`, `tc netem delay 100ms`), port 9103, terms cwnd / ssthresh / RTT / ACK / SYN / MSS / IW10 / CUBIC.
- Slide 4 is optional. If used, keep the caveat that the loss comes from receive-backlog overflow on loopback, NOT from netem random loss.
- Wireshark was not installed on the test machine; image 03 is tcpdump-derived text. For a real Stevens graph the lecturer can open `recorded/capture_default.pcap` in Wireshark → Statistics → TCP Stream Graphs → Stevens (click a 1448-byte data packet from port 9103 first; press "Switch Direction" if flat).

## Facts (real, recorded 22.10.2026, Docker on macOS 15.7, kernel 6.12.76-linuxkit)

| Fact | Value | Source |
|---|---|---|
| Netem delay / measured RTT | 100 ms / 201.8–202.5 ms | `recorded/cwnd_table_default.txt`, `expected_output.txt` §1 |
| Handshake time (client) | 203 ms | `expected_output.txt` §1 |
| MSS | 1448 bytes | `recorded/cwnd_table_default.txt` |
| cwnd sequence (default run) | 10, 20, 40, 80, 160, 320, 640, 1280 at t = 0, 215, 428, 617, 831, 1013, 1216, 1433 ms | `recorded/cwnd_table_default.txt` |
| Growth per row | ×2.00 every row; ssthresh «—»; retrans 0/0 | same |
| Last row unacked | 903 (file ran out, cwnd 1280) | same |
| Transfer | 3.0 MB in 1.62 s, 15.5 Mbit/s average | `expected_output.txt` §1 |
| pcap bursts | 10, 20, 40, 80, 160, 320, 640, 903 segments at t = 0.000 … 1.415 s (≈0.202 s apart); 2555 packets | `expected_output.txt` §1 |
| Data segments vs ACKs in capture | 2173 vs 380 | `explanation.html` §2 |
| Congestion control / tcp_rmem | cubic / 4096 4194304 6291456 (container only) | `expected_output.txt` §1 |
| --loss run: first ssthresh | 1477, later 1034 | `recorded/cwnd_table_loss.txt` |
| --loss run: deepest cwnd in recovery | 205 | same |
| --loss run: CA growth | 1034 → 1061 → 1078 … → 1175 (×1.00–×1.03) | same |
| --loss run: TcpRetransSegs / backlog drops | 247 / 247; HyStart 0/0 | `expected_output.txt` §2 |
| Other runs' ssthresh | 1737, 2293, 2907; varies per run | `expected_output.txt` §2 header |
| Mac host without delay | 200 MB in 0.04 s (slow start invisible) | `expected_output.txt` §6 |
