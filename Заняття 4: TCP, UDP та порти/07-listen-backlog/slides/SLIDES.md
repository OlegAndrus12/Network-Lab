**Demo 07: listen backlog (сервер, що не викликає accept())**. Attaches to the existing slide «Життєвий цикл TCP-сокета» and to exercise 8 (the note «Send-Q = backlog» for a listening socket).

---

## Slide 1. Сервер без accept(): хто робить рукостискання?

**On-slide text**
- Сервер викликав `listen(backlog=2)` і **ніколи** не викликає `accept()`
- 5 клієнтів підключаються одночасно
- Перші клієнти вже `ESTABLISHED` і надіслали 16 байтів, хоча програма їх не прийняла
- Решта «стукає» в `SYN_SENT`: місця в черзі немає

**Image**: `img/02-macos-netstat-queue.png` (macOS, the lecture laptop). Highlight `2/0/2` and the three red `SYN_SENT` lines. If space is short, crop to the part from `$ netstat -Lan -p tcp` down. The lines above it (the client report) can be cropped away.

**Speaker notes**
Програма лише викликала listen() і більше нічого не робить, проте два клієнти вже підключені й навіть надіслали дані: у сервера Recv-Q 16. Рукостискання зробило ядро, а не програма. `netstat -Lan` на macOS показує черга/напіввідкриті/ліміт = 2/0/2: черга заповнена рівно до backlog. Троє інших клієнтів у SYN_SENT: їхні SYN ядро мовчки відкидає.

---

## Slide 2. Linux: `ss -ltn` і вправа 8

**On-slide text**
- Для сокета в стані `LISTEN`: **Recv-Q** = скільки з'єднань чекає `accept()`, **Send-Q** = backlog
- `LISTEN 3 2`: у черзі 3 з'єднання, backlog 2 (Linux тримає backlog + 1)
- Для всіх інших станів Recv-Q/Send-Q означають байти в буферах
- Зайві SYN відкидаються мовчки: без RST і без SYN-ACK (`TcpExtListenOverflows`)

**Image**: `img/01-linux-ss-queue.png`. Main focus: the `LISTEN 3 2` line under `ss -ltn` (yellow). Secondary: the red `SYN-SENT` lines and `ESTAB 16`. If the image must be smaller, crop to the block from `$ ss -ltn` to the last `ESTAB` line and drop the nstat part.

**Speaker notes**
Це відповідь на примітку з вправи 8: у `ss` для слухаючого сокета колонки змінюють значення. Recv-Q показує довжину черги accept, Send-Q показує backlog, переданий у listen(). Чому 3, а не 2? Linux вважає чергу повною, коли її довжина > backlog, тому вміщує backlog + 1; macOS на попередньому слайді вмістив рівно 2. Двоє зайвих клієнтів у SYN-SENT: сервер нічого їм не відповідає, і лічильник ListenOverflows росте.

---

## Slide 3. Чому так: дві черги ядра

**On-slide text**
- `listen()`: ядро саме відповідає на SYN і завершує рукостискання
- Готові з'єднання стоять у **черзі accept**; `accept()` лише забирає наступне
- Черга повна → SYN відкидається, клієнт повторює той самий SYN
- Клієнт заходить із **наступним повтором** SYN після того, як `accept()` звільнить місце

**Diagram** (draw left to right):
- Left: box «Клієнт» with label `SYN`, arrow →
- Box 1: «Черга SYN (напіввідкриті, SYN-RECEIVED)»; arrow labelled «останній ACK рукостискання» →
- Box 2: «Черга accept (готові, ESTABLISHED)», drawn as a slot strip with 3 filled slots; small label under it: «ліміт ≈ backlog (Linux: backlog + 1, macOS: backlog)»; arrow labelled `accept()` →
- Right: box «Програма (новий дескриптор)»
- Above both queue boxes, a bracket: «ядро» (the program only touches the last arrow)
- A second client «Клієнт 4» below-left whose `SYN` arrow hits Box 2's full edge and bounces back as a dashed arrow labelled «відкинуто мовчки: ні SYN-ACK, ні RST → повтор SYN»

**Image** (optional, beside or under the diagram): `img/04-linux-tcpdump-syn-retransmit.png`. Highlight the four `[S]` lines with the same `seq 240545858`, then the green `[S.]` (SYN-ACK) right after the 4th.

**Speaker notes**
accept() не робить рукостискання: воно лише знімає готове з'єднання з черги й дає програмі новий дескриптор. Коли черга повна, ядро не відповідає ні SYN-ACK, ні RST, а просто відкидає SYN, і клієнт повторює той самий SYN (той самий seq) приблизно щосекунди. Відкинути краще, ніж відмовити: RST одразу зірвав би з'єднання, а повтор переживе коротке перевантаження. Сервер нікому не «передзвонює»: клієнт заходить лише з наступним повтором SYN.

---

## Slide 4. accept() починає працювати або запізнюється

**On-slide text**
- `accept()` почав працювати → черга порожніє (`LISTEN 0 2`), клієнти 4–5 зайшли через 3.1 с
- Дані, надіслані ще до `accept()`, не загубилися
- Запізно (macOS, loopback): 13 SYN за ~6 с → `ETIMEDOUT`
- Так зовні виглядає сервер, який повільно викликає `accept()`

**Images**: two side by side, or two consecutive slides if too dense:
- `img/03-linux-accept-drains.png`: highlight `чекав 3.1 с` and `LISTEN 0 2`.
- `img/05-macos-accept-too-late.png`: highlight the three red `ETIMEDOUT` lines and `SYN x13, дані x0`.

**Speaker notes**
Щойно сервер почав викликати accept(), черга спорожніла, і кожен клієнт отримав повідомлення, яке надіслав ще до accept(). Клієнти 4 і 5 зайшли не миттєво, а з наступним повтором SYN, звідси затримки «рівно 1 с / 3 с» на перевантажених серверах. Якщо accept() запізнюється, на macOS через loopback клієнт здається після 13 SYN приблизно за 6 секунд з ETIMEDOUT; у реальній мережі ті самі повтори тривали б значно довше, а Linux у наших прогонах ще через 19 с повторював SYN. Тому backlog і `somaxconn` налаштовують: Nginx і Node.js на Linux за замовчуванням ставлять 511.

---

## Design notes (for the design agent)

- The PNGs are real terminal output, rendered at 2x. Place them unscaled or downscaled only, never upscaled. Don't retype, re-wrap or re-colour the output. Use the image. Crop only at whole lines.
- Highlight colours inside the images: **yellow box** = the key number for the slide; **green** = connected / ESTABLISHED / SYN-ACK; **red** = waiting / SYN-SENT / dropped / ETIMEDOUT; **blue** = commands; **grey italic `← …`** = lecturer annotations (not program output); `…` = trimmed lines.
- Must not change: `listen(backlog=2)`, `LISTEN 3 2`, `LISTEN 0 2`, `2/0/2`, `16`, `чекав 3.1 с`, `SYN x13`, `seq 240545858`, and commands exactly as shown (`ss -ltn`, `ss -tan`, `netstat -Lan -p tcp`, `nstat -az …`, `./run_demo.sh`, `./run_docker.sh`).
- "Send-Q = backlog" is true **only for a LISTEN socket on Linux (`ss`)**. Don't write it as a general rule. On macOS the queue is read from `netstat -Lan`; `netstat -an` shows 0 0 for LISTEN.
- Linux = backlog + 1 (3), macOS = exactly backlog (2). Keep both, don't "fix" one to match the other.
- Keep terms as is: SYN, SYN-ACK, ACK, RST, `SYN-SENT`/`SYN_SENT` (Linux uses a hyphen, macOS an underscore), `ESTABLISHED`/`ESTAB`, `accept()`, `listen()`, backlog.
- Diagram: kernel side vs program side should be visually distinct. The program owns only the `accept()` arrow.

## Facts (all from `expected_output.txt`, real runs 22–23.10.2026; macOS 15 / Darwin 24.6, Linux 6.12.76-linuxkit in Docker)

| Fact | Value | Source (expected_output.txt) |
|---|---|---|
| Server | `127.0.0.1:9107`, `listen(backlog=2)`, 5 clients | sections A, B |
| macOS queue while no accept() | `2/0/2` (qlen/incqlen/maxqlen) | A, step 2 |
| macOS: connected / waiting | 2 / 3 | A, step 1 |
| macOS queue after accept() | `0/0/2` | A, step 4 |
| macOS waiting clients got in after | 3.9–4.0 s, 12 SYNs each | A, steps 3 and 6 |
| Linux `ss -ltn` LISTEN, no accept() | Recv-Q 3, Send-Q 2 | B, step 2 |
| Linux: connected / waiting | 3 / 2 | B, step 1 |
| Unread bytes per queued connection (server side) | Recv-Q 16 | A and B, step 2 |
| Linux `TcpExtListenOverflows` / `ListenDrops` before accept() | 4 / 4 | B, step 2 |
| Linux after accept() | `LISTEN 0 2`; clients 4–5 `чекав 3.1 с` | B, steps 3–4 |
| Linux SYN retransmits of client 53446 | 4 SYNs (same seq 240545858), ~1 s apart; 4th got SYN-ACK | C |
| macOS accept() too late (`ACCEPT_DELAY=8`) | 3 clients `ETIMEDOUT`, `SYN x13, дані x0` each, ~6 s | D |
| macOS SYN retransmit timing on loopback | ~30 ms at first, then doubling | C, D |
| Rare Linux race | once `Recv-Q 4` with backlog 2 (5 simultaneous nc); 9 other runs gave 3 | G |
| Nginx/Node.js default backlog on Linux; macOS `kern.ipc.somaxconn` | 511; 128 | explanation.html (not in expected_output.txt) |

Caveats worth keeping if the slide text touches them: the macOS 6-second give-up is a loopback effect (tiny RTO); on a real network the same 12 retransmits take much longer. The "13 SYN / 12 retransmits" reading is the authors' interpretation and was not checked in XNU source. The SYN-cookie case (all 5 clients "connected" but only 3 in the queue, runs E/F) is advanced material and is intentionally not on these slides.
