**Демо 2: ретрансляції TCP у Wireshark при 5% втрат (netem)**. Прикріплюється до слайда «Два способи помітити втрату» (Тема 4. TCP, UDP та порти) і до вправи 3.

---

## Слайд 1. Демо: ламаємо мережу на 5%

**Title:** Демо: 5% втрат, і що з цього бачить TCP

**On-slide text:**
- Docker-контейнер: `tc netem delay 5ms loss 5%` на `lo`
- curl завантажує 2 МБ, tcpdump пише `.pcap` для Wireshark
- Без втрат: 0,36 с. З 5% втрат: 5,4 с
- Ядро рахує обидва способи: швидкі повтори і RTO

**Image:** `img/01-run-counters.png`. Show whole. Highlights: `5.357760 с` (yellow) vs `0.361000 с` (green); `66` (red, спосіб 1) and `3` (violet, спосіб 2).

**Simple diagram (optional, left of the image):** one rounded box «Docker-контейнер (Linux)». Inside it, left to right: box «python3 http.server :9102» → arrow labelled «2 МБ» → box «curl». Between them, on the arrow, a small red box «netem: −5% пакетів, +5 мс». Below the arrow, a dashed tap line down to box «tcpdump → capture.pcap». Outside the container on the right: arrow from capture.pcap to box «Wireshark на Mac».

**Speaker notes:** Щоб побачити ретрансляції, нам потрібна погана мережа, тож ми штучно губимо 5% пакетів на loopback у контейнері. Той самий файл без втрат завантажується за 0,36 с, а з 5% втрат приблизно в 15 разів довше: кожна втрата змушує TCP зменшити вікно перевантаження. Ядро саме рахує, скільки разів воно помітило втрату через дубльовані ACK і скільки разів спрацював таймер RTO. Далі подивимося на ці події в Wireshark.

---

## Слайд 2. Спосіб 1: дубльовані ACK → швидкий повтор

**Title:** Спосіб 1: три дубльовані ACK

**On-slide text:**
- Сегмент загубився, наступні дійшли: отримувач повторює той самий `Ack=207`
- Третій дубль = сигнал втрати, відправник не чекає таймера
- TCP Fast Retransmission приблизно через 1 RTT (тут 6 мс після Dup ACK #3)
- SACK (`SLE/SRE`) додатково каже, які байти після діри вже є

**Image:** `img/02-fast-retransmit.png` (tshark text output from `sample_sack.pcap`, coloured like Wireshark's default "Bad TCP" rule). Show whole. Draw attention to rows 15–17 (Dup ACK #1–#3) and row 26 (Fast Retransmission). If cropping, keep rows 14–26 and the right-hand annotations.

**Simple diagram (optional):** classic two-column sequence diagram. Left vertical line «відправник», right «отримувач». Arrows left→right: «seq 1», «seq 2» (crossed out with ✕, label «втрачено»), «seq 3», «seq 4», «seq 5». Arrows right→left: «ACK 2» ×3, labelled «#1», «#2», «#3» in amber. Then a thick red arrow left→right «швидкий повтор seq 2», and a green arrow back «ACK 6». A bracket on the side: «≈ 1 RTT».

**Speaker notes:** Підтвердження в TCP накопичувальні: «маю все до байта N». Коли сегмент губиться, кожен наступний сегмент викликає той самий ACK, і це дублікати. Три дублікати класично вважаються доказом втрати, а не перестановки, тож відправник повторює сегмент одразу, без таймера, і зменшує вікно вдвічі. Застереження: сучасний Linux із SACK і RACK не рахує буквально до трьох, тож у Wireshark повтор може з'явитися і після Dup ACK #2, і після #18; правило «3 дублікати» для лекції правильне.

---

## Слайд 3. Спосіб 2: тиша → таймер RTO

**Title:** Спосіб 2: таймер RTO

**On-slide text:**
- Якщо дублікатів немає, відправник чекає таймер RTO
- У Linux мінімум 200 мс, тут пауза 0,244 с і 0,288 с
- Після RTO: cwnd = 1 сегмент, RTO подвоюється
- Швидкий повтор: 6 мс. RTO: 244 мс

**Image:** `img/03-rto.png` (tshark text, `sample_sack.pcap`, frames 102–111). Highlight the Δt cells `0.244` and `0.288` (already boxed in dark red). Optionally place `img/05-time-gap.png` (light bar chart: 6 мс vs 244 мс vs 288 мс) below or on the next build step; it is the visual punchline of the central contrast.

**Speaker notes:** Дублікати допомагають, лише якщо після втрати ще йдуть дані і доходять ACK. Тут сегменти 103 і 104 дійшли, але обидва ACK загубились, тож відправник нічого не чув 0,244 с, і спрацював таймер. Наступний ACK несе D-SACK, «це в мене вже є»: тобто цей RTO був зайвим, винні втрачені ACK. RTO у 40 разів повільніший за швидкий повтор і скидає вікно до одного сегмента, тому він так дорого коштує.

---

## Слайд 4. Що змінює SACK + вправа 3

**Title:** SACK: менше дублікатів, менше таймаутів

**On-slide text:**
- Без SACK відправник дізнається про одну діру за RTT
- З SACK: усі діри одразу, тож рідше доходить до RTO
- Один запуск кожного: RTO 3 проти 12, дублікатів 183 проти 367
- Вправа 3: знайдіть ці числа у `sample_sack.pcap` фільтрами Wireshark

**Image:** `img/04-sack-vs-nosack.png` (light bar chart, four small panels, each with its own scale). Show whole; do not merge panels onto one axis.

**Simple diagram (optional, for the exercise):** a small 3-row table: «Дубльовані ACK» → `tcp.analysis.duplicate_ack`; «Швидкі повтори» → `tcp.analysis.fast_retransmission`; «RTO» → `tcp.analysis.retransmission && !tcp.analysis.fast_retransmission && tcp.time_delta >= 0.2`. Answers (183 / 34 / 3) only on a hidden/next slide.

**Speaker notes:** SACK повідомляє, які діапазони після діри вже дійшли, тож відправник може залатати кілька дір за один RTT. Без SACK друга втрата в тому самому вікні часто закінчується таймаутом, і в нашому запуску RTO стало 12 замість 3. Це один випадковий запуск, а не бенчмарк: з SACK за кілька тестових запусків RTO було від 0 до 6. Для вправи 3 зверніть увагу: не кожне «TCP Retransmission» у Wireshark є RTO; справжній таймаут видно за паузою від 0,2 с.

---

## Design notes (for the design agent)

- Images are 2× renders. Place them unscaled or scaled down only, never upscaled; keep monospace text crisp. Do not retype terminal/tshark output; use the images.
- Images 02 and 03 are **tshark text output** rendered as a Wireshark-like table, not Wireshark screenshots. The caption inside says so. Win/TSval/TSecr fields were removed for width; everything else is verbatim.
- Colour meaning in terminal/tshark images: black row + red text = Wireshark "Bad TCP" (loss events); lavender row = normal TCP; red number = method 1 (fast retransmit); violet number = method 2 (RTO); yellow = time with loss; green = time without loss; grey `← …` = annotations; `…` = cut lines. In charts: blue = SACK on / fast retransmit; orange = SACK off; violet = RTO.
- Must not change: any number, frame number, command, filter string, or field name (`Ack=207`, `SLE/SRE`, `TcpExtTCPTimeouts`, etc.).
- Do not put the kernel's `TcpExtTCPFastRetrans 66` next to Wireshark's `34 Fast Retransmission` as if they should match: nstat counts both ends together and Wireshark labels are heuristics.
- If the lecturer wants real Wireshark screenshots: open `sample_sack.pcap`, Analyze → Enabled Protocols → uncheck HTTP; filter `frame.number <= 27` (slide 2), `frame.number >= 102 && frame.number <= 111` with column `tcp.time_delta` (slide 3, enable TCP pref "Calculate conversation timestamps"), Analyze → Expert Information (slide 4 totals).
- Sources: HTML in `slides/src/` (`gen.py` builds 01–03 from `expected_output.txt` and live tshark; 04/05 are hand-written HTML with the data in a comment at the top).

## Facts (only use these numbers)

| Fact | Value | Source |
|---|---|---|
| Netem settings | delay 5ms loss 5%, MTU 1500, file 2048 КБ (2097152 байтів), port 9102 | expected_output.txt §A |
| Download time, 5% loss, SACK on | 5.357760 с | expected_output.txt §A |
| Download time, SACK off | 6.700190 с | expected_output.txt §C |
| Download time, no loss | 0.361000 с (≈15× faster) | expected_output.txt §G |
| Frames in sample_sack.pcap / sample_nosack.pcap | 1959 / 2409 | §A / §C |
| Kernel, SACK on: TcpExtTCPFastRetrans / TcpExtTCPTimeouts / TcpRetransSegs / TcpExtTCPSackRecovery / TcpExtTCPLossProbes | 66 / 3 / 70 / 55 / 9 | §A |
| Kernel, SACK off: TcpExtTCPFastRetrans / TcpExtTCPTimeouts / TcpRetransSegs / TcpExtTCPRenoRecovery | 48 / 12 / 83 / 38 | §C |
| Wireshark, SACK on: Dup ACK / Dup ACK #3 / Fast Retransmission / RTO (≥0.2 s) / ACKs with SACK | 183 / 39 / 34 / 3 / 223 | §A, §B (same in tshark 4.4.19 and 4.6.9) |
| Wireshark, SACK off: Dup ACK / Fast Retransmission / RTO (≥0.2 s) / ACKs with SACK | 367 / 39 / 10 / 0 | §C |
| First loss: hole at Seq=1655 (frame 7), Dup ACK 14#1–#7 with Ack=207, Fast Retransmission Seq=207 at frame 26 | 0.026988 s (Dup ACK #3, frame 17) → 0.032940 s (frame 26) = 6 мс | tshark 4.6.9 on sample_sack.pcap |
| RTO examples | frame 105 Δt 0.244 s (Seq=79847), frame 110 Δt 0.288 s (Seq=82743), frame 645 +0.217 s; frame 106/111 D-SACK | tshark on sample_sack.pcap; §A |
| RTT in demo | ≈ 12 мс (SYN-ACK 6.1 мс after SYN) | explanation.html §2.1 |
| Linux minimum RTO | 200 мс (RFC 6298 recommends 1 s) | explanation.html §2.4 |
| Variability | RTO with SACK ranged 0–6 across ~12 test runs at 5% loss | explanation.html §2.5 |
