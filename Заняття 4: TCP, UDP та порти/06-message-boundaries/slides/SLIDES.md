**Demo 6: межі повідомлень (UDP зберігає, TCP ні).** Attaches to the existing slides «UDP — відправив і забув» and the TCP slide's byte-stream point (TCP = потік байтів, не повідомлень).

---

## Slide 1. UDP: конверти. TCP: потік

**Title:** Три відправки — скільки прийомів?

**On-slide text:**
- UDP: 3 × `sendto()` по 100 байтів → 3 × `recvfrom()` по 100 байтів
- TCP: 3 × `send()` по 100 байтів → **1** × `recv()` на 300 байтів
- Однакова пауза приймача (0.5 с), різний результат: різниця в протоколі

**Image:** `img/01-udp-vs-tcp.png` (hero, full width). Two terminals side by side: left UDP, right TCP. Blue `100 байтів` ×3 versus red `300 байтів`. Don't crop: the sender lines at the top show that both sides sent the same thing.

**Speaker notes:** Перед запуском спитайте аудиторію: «Три send по 100 байтів. Скільки recv і якого розміру?» Більшість скаже 3 × 100. UDP так і робить: кожна дейтаграма приходить окремо й цілою. TCP віддав усі три повідомлення одним шматком на 300 байтів, від `<MSG-1` до `END-3>`. Пауза 0.5 с однакова для обох приймачів, тож справа в протоколі, а не в таймінгу.

---

## Slide 2. Межі зникають у буфері прийому, а не в мережі

**Title:** На дроті 3 сегменти, а `recv()` один

**On-slide text:**
- tcpdump: 3 окремі сегменти по `length 100`, кожен підтверджений ACK
- Ядро складає байти в буфер прийому одним суцільним рядком
- `recv()` повертає стільки, скільки вже лежить у буфері

**Image:** `img/03-wire-vs-recv.png`. Highlight the three `*` lines (blue `seq 1:101 / 101:201 / 201:301`) against the red `Разом recv(): 1, байтів: 300` at the bottom. This capture is from Linux in Docker (the macOS capture needs sudo).

**Optional diagram (left-to-right, 4 columns):**
`send(MSG-1)`, `send(MSG-2)`, `send(MSG-3)` (3 small boxes stacked) → arrow «на дроті» → 3 separate boxes `сегмент 1:101`, `сегмент 101:201`, `сегмент 201:301` → arrow → one long box «буфер прийому: [MSG-1][MSG-2][MSG-3], 300 байтів, меж немає» → arrow → `recv() → 300 байтів`.

**Speaker notes:** Де зникли межі: у мережі чи в приймачі? У мережі їх було три, кожен сегмент окремо, і ядро підтвердило кожен, поки застосунок ще спав. Злиття відбулося в буфері прийому: у TCP-заголовку немає поля «тут закінчилось повідомлення», є лише номери байтів. Зливати може й відправник: з алгоритмом Нейгла і затримкою 50 мс сегментів було 2, а не 3 (2-й і 3-й send злилися в `length 200`).

---

## Slide 3. Навпаки: один send → кілька recv

**Title:** 1 МБ одним `send()` приходить шматками

**On-slide text:**
- `sendall()` 1 000 000 байтів, приймач просить `recv(1000000)`
- Отримав 2 шматки: 48 996 + 951 004 байтів
- Розміри щоразу інші: залежать від того, скільки встигло прийти
- `data = sock.recv(4096); json.loads(data)` — баг, який «працює» на localhost

**Image:** `img/02-tcp-1mb-split.png`. Highlight the two orange chunk sizes and the annotations «початок без кінця» / «кінець без початку».

**Speaker notes:** Приймач просить мегабайт за раз, але `recv()` повертає те, що вже лежить у буфері, і не чекає решти. Перший шматок має початок повідомлення, але не має кінця, другий навпаки. На Linux у тому ж прогоні було 3 шматки (65 482 + 94 336 + 840 182), і за 20 запусків 1 МБ жодного разу не прийшов одним шматком. Тому код, який вважає «один recv = одне повідомлення», рано чи пізно ламається в продакшені.

---

## Slide 4. Висновок: застосунок сам робить кадри

**Title:** UDP — конверти, TCP — труба з байтами

**On-slide text:**
- UDP зберігає межі, але без гарантії доставки («відправив і забув»)
- TCP доставляє всі байти по порядку, але межі повідомлень губить
- Тож межі додає протокол застосунку: роздільник (`\r\n` у HTTP) або префікс довжини (`Content-Length`, 4 байти в демо)
- Демо: той самий злитий шматок на 312 байтів → рівно 3 повідомлення

**Image:** `img/04-framing.png` (tall; place on the right half). Green lines = recovered messages; orange = «кадр ще неповний», waiting for the next `recv()`. If space is tight, crop to the top part (scenario 4, down to «Після розбору кадрів: 3 повідомлення(нь)…»).

**Diagram (left half), two rows:**
- Row «UDP»: three separate envelope icons labelled `MSG-1`, `MSG-2`, `MSG-3`, each with its own arrow from «відправник» to «приймач». Caption: «кожен конверт окремо; загубився — ніхто не скаже».
- Row «TCP»: one pipe from «відправник» to «приймач» filled with a continuous strip of bytes `…MSG-1MSG-2MSG-3…` with no gaps. Caption: «труба з байтами: межі не видно».
- Row «TCP + кадри»: the same pipe, but the strip is `[100]MSG-1[100]MSG-2[100]MSG-3`, with the `[100]` blocks in a different colour, labelled «префікс довжини, 4 байти». Caption: «межі несе сам застосунок».

**Speaker notes:** Якщо TCP не зберігає межі, їх має закодувати протокол застосунку. HTTP/1.1 закінчує кожен рядок заголовків `\r\n`, а довжину тіла передає в `Content-Length`; HTTP/2, TLS, WebSocket теж мають у кадрі поле довжини. У демо приймач отримав той самий злитий шматок на 312 байтів, але завдяки 4-байтовому префіксу довжини розібрав рівно 3 повідомлення, а 1 МБ зібрав із трьох шматків. Чому б тоді не все через UDP? Бо межі там коштують гарантії доставки: відправник без приймача теж пише «Готово», дейтаграми просто зникають.

---

## Design notes (for the design agent)

- The PNGs are rendered at 2× scale. Place them unscaled or scaled down only; never upscale. Keep them crisp: no blur, shadows over the text, or recompression.
- Do not retype terminal output into text boxes. Use the image. If a crop is needed, crop at line boundaries.
- Highlight colours in the screenshots: **blue** = what was sent / key wire facts (sizes, seq ranges); **red** = boundaries lost (merged 300/312-byte chunk, «кінці: —»); **orange** = fragment / incomplete frame; **green** = boundaries kept or recovered; **grey italic `← …`** = lecturer annotations added for the slide (not printed by the scripts); `…` = lines cut. Reuse the same colour meaning in diagrams (e.g. red for the merged buffer, green for framed messages).
- The grey lines `… рукостискання SYN / SYN-ACK / ACK …` and `… закриття FIN …` in 03 are cut markers summarising omitted real lines, not output.
- Don't change numbers, commands, flags, or the output text (including `TCP_NODELAY`, `recv()`, `sendto()`, `Content-Length`, `\r\n`).
- Image 01 is macOS; 03 is Linux (Docker). If a slide says which OS, keep that.

## Facts (all from `06-message-boundaries/expected_output.txt`, recorded 22.10.2026)

| Fact | Value | Section of expected_output.txt |
|---|---|---|
| UDP: sends / receives | 3 × `sendto()` 100 B → `Разом recvfrom(): 3` | A, scenario 1 (macOS) |
| UDP with no receiver | prints «Готово…», «(жодної помилки: дейтаграми просто зникли)» | A, scenario 1б |
| TCP merge | 3 × `send()` 100 B → `recv #1: 300 байтів`, `Разом recv(): 1` (receiver `--delay 0.5`) | A, scenario 2 |
| Merge stability | 300 in 20/20 runs with 0.5 s pause (10 macOS + 10 Linux) | E |
| Without pause | macOS usually 100+200 (9/10, once 100+100+100); Linux 300 (10/10) | E |
| TCP split, macOS | 1 000 000 B one `sendall()` → 48 996 + 951 004 (2 recv) | A, scenario 3 |
| TCP split, Linux | 65 482 + 94 336 + 840 182 (3 recv) | B, scenario 3 |
| Split stability | 1 MB was split in 20/20 runs; sizes vary every run | E |
| On the wire | 3 data segments `seq 1:101`, `101:201`, `201:301`, each `length 100`, then 1 recv of 300 B | C, A (Linux, tcpdump on lo) |
| Nagle + 50 ms netem | 2 data segments: `length 100` + `length 200` (`[FP.]`), still 1 recv of 300 B | D, B |
| Framing | `send()` 104 B (4 B length + 100) ×3 → `recv #1: 312 байтів` → 3 повідомлення, залишок 0 | A, scenario 4 |
| Framing + 1 MB | recv #4–#6: 48 996 + 605 168 + 345 840 → повідомлення 4: 1 000 000 байтів; total 6 recv, 1 000 316 B, 4 messages | A, scenario 4б |
| Bytes waiting in kernel | macOS `netstat` Recv-Q = 300 while receiver sleeps (Linux `ss` shows 301, likely counting FIN; unverified) | F |
| Ports | 9106/udp, 9116/tcp | run_demo.sh |

Caveats to keep the slides honest:
- The 0.5 s receiver pause picks one ordinary timing on purpose; without it the merge may be partial (100+200). Any split is legal TCP, so the claim is «межі не гарантовані», not «TCP завжди зливає».
- Nagle coalescing was **not** observed on plain loopback (ACK returns too fast); it shows only with the 50 ms netem delay.
- macOS 4б happened to deliver the three small frames in separate recv() calls (104 each), unlike scenario 4; the framing code handles both.
