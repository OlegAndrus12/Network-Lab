# Demo 01 «zero window» (лінивий сервер): attaches to the «win» slide and the section «Керування швидкістю»

All screenshots are real output of `./docker_demo.sh` (Linux in Docker, port 9101, run of 22.10.2026, block 1 of `expected_output.txt`), except the macOS `netstat` part of image 02 (block 5).

---

## Slide 1. Сервер не читає, і клієнт «замерзає»

**On-slide text**
- Сервер робить `accept()`, але не викликає `recv()`
- Клієнт шле в циклі `send()`: прогрес зупиняється через 0,25 с
- `send()` повернувся ≠ дані доставлено
- 1,77 МБ із 1,9 МБ досі лежать у буфері **клієнта**

**Image:** `img/01-send-freezes.png`. Draw attention to the red `win 0` in the `[tcpdump]` line and the three yellow numbers (1 900 544 / 1 773 376 / 127 168). Optionally crop the top 4 setup lines if space is tight; keep the 4 «send() чекає вже …» lines at the bottom (they show the freeze).

**Simple diagram** (left to right, 5 boxes joined by arrows):
`Додаток клієнта (send())` → `Буфер відправлення клієнта (Send-Q: 1 773 376 Б)` → `Мережа (сегменти, обмежені вікном)` → `Буфер прийому сервера (Recv-Q: 127 168 Б, ПОВНИЙ)` → `Додаток сервера (recv() не викликає, «спить»)`.
Draw the server receive buffer box with a red border; above the arrow between network and server buffer, a red label `win 0`. Under the last box: «спить 10 с».

**Speaker notes:** Сервер прийняв з'єднання, але 10 секунд нічого не читає. Клієнт за чверть секунди заповнив буфер прийому сервера (127 168 байтів), і сервер оголосив вікно 0. Далі дані накопичуються в буфері відправлення клієнта, а коли і він заповнився, `send()` блокується: програма «зависла» з чисто мережевої причини. Питання до аудиторії: «Де зараз ці 1,9 МБ?» Відповідь: 93 % досі на машині клієнта.

---

## Slide 2. Погляд ядра: Recv-Q і Send-Q

**On-slide text**
- `ss -tn` (Linux) / `netstat -an -p tcp` (macOS)
- Recv-Q сервера: отримано і підтверджено, але додаток не прочитав
- Send-Q клієнта: передано в `send()`, але ще не підтверджено
- Ті самі числа, що надрукував клієнт

**Image:** `img/02-recvq-sendq.png`. Highlight red = Recv-Q of the server socket, yellow = Send-Q of the client socket. The macOS half can be dropped if the slide is Linux-only; keep it if you want the «інші числа, та сама картина» point.

**Speaker notes:** Це знімок через 4 секунди, поки клієнт стоїть. У сокета сервера Recv-Q 127 168: ці байти ядро вже прийняло й підтвердило, просто додаток їх не забрав. У сокета клієнта Send-Q 1 773 376: ці байти ще навіть не відправлені, бо вікно сервера 0. На macOS числа більші (автопідбір буферів), але розподіл той самий.

---

## Slide 3. win 0 і zero-window probes

**On-slide text**
- Сервер: `ack 127169, win 0`: «усе до байта 127 168 маю, більше не шли»
- Клієнт періодично шле пробу (persist timer), щоб дізнатися поточне вікно
- Інтервал проб подвоюється: 0,208 → 0,416 → 0,848 → 1,664 → 3,328 с
- «Нерівні» відповіді сервера: Linux обмежує частоту таких ACK (`tcp_invalid_ratelimit`)

**Image:** `img/03-zero-window-probes.png` (tcpdump text, explained by the demo's `annotate.py`). Draw attention to the red `win 0` and to the yellow `+0.208 с … +3.328 с` column. Optional companion image: `img/05-probe-timeline.png` (light-background timeline built from the same timestamps); it shows the doubling at a glance and the missing reply to probe №2 (dashed hollow circle). Use either one, or both side by side / as a build.

**Speaker notes:** Якщо оновлення вікна загубиться, обидві сторони чекатимуть вічно, бо чисті ACK ніхто не перепосилає. Тому відправник запускає persist timer і шле zero-window probe; сервер відповідає ACK з поточним вікном, поки що з `win 0`. Інтервал проб клієнта подвоюється дуже рівно, починаючи з мінімального RTO 200 мс. Інтервали відповідей сервера (0,208, 1,264, 1,664, 3,328 с) нерівні лише тому, що на пробу №2 сервер не відповів: Linux обмежує ACK на сегменти поза вікном одним на 500 мс; з `tcp_invalid_ratelimit = 0` відповіді йдуть на кожну пробу. З'єднання не розривається, бо сервер на проби відповідає: він живий, просто повільний.

---

## Slide 4. Оновлення вікна: сервер прочитав, клієнт поїхав далі

**On-slide text**
- Сервер почав `recv()`: місце в буфері звільнилось
- Window update: той самий `ack 127169`, але `win 523` (523 × 128 = 66 944 байти)
- `send()` знову працює, передано всі 8 000 000 байтів
- Керування потоком (rwnd) ≠ керування перевантаженням (cwnd)

**Image:** `img/04-window-update.png`. Draw attention to the green `win 523` against the red `win 0` on the line above, and to the bold line «>>> send() знову працює після 9.5 с».

**Speaker notes:** Щойно додаток сервера почав читати, ядро сервера надсилає оновлення вікна: номер ack не змінився, нових даних немає, змінилось лише вікно. Клієнт одразу відновлює передачу. Висновок: TCP пригальмовує швидкого відправника до швидкості найповільнішого *додатка*, а не лише найповільнішого каналу. Це керування потоком (вікно отримувача, rwnd), а не керування перевантаженням (cwnd).

---

## Design notes (for the design agent)

- Use the PNGs as images; do **not** retype terminal output. They are rendered at 2× device scale; scale down only, never up, and keep them crisp (no blur, no recolouring).
- Terminal images (01–04) have a dark background; 05 is a light chart.
- Highlight colours: **red** = window is zero / full buffer (`win 0`, Recv-Q of server); **yellow** = key byte counts and probe intervals; **green** = window reopened (`win 523`); grey italic `← …` = lecturer annotations added for the slides (not program output). `…` marks trimmed lines.
- In image 03 the column padding of `annotate.py` output was narrowed (whitespace only) to fit the width; no numbers or text were changed.
- Image 03 and 05 are tcpdump-based text/timeline, not Wireshark. If the lecturer wants a real Wireshark screenshot: open `capture.pcap`, display filter `tcp.analysis.zero_window || tcp.analysis.zero_window_probe || tcp.analysis.keep_alive || tcp.analysis.window_update`. Caveat: Wireshark labels the Linux probes «TCP Keep-Alive» (same packet shape: 0 bytes, old seq); they are zero-window probes.
- Do not change numbers, commands, flags or tcpdump fields. Keep `win`, `ack`, `Send-Q`, `Recv-Q`, `send()`, `recv()`, `rwnd`, `cwnd` in Latin as is.
- If a slide shows the run command: Linux behaviour (matches the slide) is `./docker_demo.sh`; natively on macOS it is `./run_demo.sh`, but macOS behaves differently (see Facts), so don't put macOS timings on the slide.

## Facts (all from `01-zero-window/expected_output.txt`, block 1 unless noted; same run as `capture.txt` / `capture.pcap`)

- Port 9101; `SO_RCVBUF` 131 072 B (server), `SO_SNDBUF` 2 626 560 B (client).
- `win 0` first at 0.249 s: `ack 127169, win 0`. Server buffer held 127 168 B unread.
- Window shrink before that: `win 737` (737 × 128 = 94 336 B free) → `win 113` (14 464 B) → `win 0`; wscale 7 (× 128) from the handshake.
- At the freeze: passed to `send()` 1 900 544 B; still in client send buffer (Send-Q) 1 773 376 B (≈ 93 %); reached server 127 168 B.
- `ss -tn` at 4 s: client Send-Q 1773376, server Recv-Q 127168.
- Client probes at 0.457, 0.873, 1.721, 3.385, 6.713 s; intervals 0.208, 0.416, 0.848, 1.664, 3.328 s (5 probes).
- Server `win 0` replies: 5, intervals 0.208, 1.264, 1.664, 3.328 s; no reply to probe №2 (`net.ipv4.tcp_invalid_ratelimit` = 500 ms). Verified in block 4: with ratelimit 0 the server answered all probes (6 replies).
- Window update at 10.105 s: `ack 127169, win 523` = 66 944 B free. Client: «send() знову працює після 9.5 с». Total 8 000 000 B sent and read.
- macOS (block 5, `./run_demo.sh`): `netstat` server Recv-Q 393216, client Send-Q 187740. macOS differs: `win 0` appears only after ~5 s (sender silly-window avoidance + 5-s persist minimum), probes are 1 byte and ≥ 5 s apart. Linux/Docker is the version that matches the lecture slide.
- Numbers vary slightly between runs (kernel, sysctl); the shape is stable. Don't promise students exact figures.
