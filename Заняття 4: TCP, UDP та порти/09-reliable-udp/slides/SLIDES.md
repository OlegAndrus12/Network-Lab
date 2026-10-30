**Demo 9: надійність поверх UDP (маленький TCP власноруч).** Attaches to the existing slides «UDP — відправив і забув» and the TCP slide's list (номери, ACK, повтори, порядок).

---

## Slide 1. Сирий UDP у поганій мережі

**Title:** 100 відправлено — що дійшло?

**On-slide text:**
- netem: затримка 25 мс, 10% втрат, 5% дублікатів, 25% перестановок
- Прийшло 97 дейтаграм: 10 загублено, 7 дублікатів, 31 не по порядку
- `sendto()` 100 разів повернув успіх: помилок ОС — жодної

**Image:** `img/01-naive-udp.png` (hero, full width). Red = lost/duplicates, orange `<` = out of order. Keep the bottom line «помилок ОС — жодної» visible.

**Speaker notes:** Спершу спитайте: «10% втрат. Скільки зі 100 дійде і чи скаже `sendto()` про помилку?» Подивіться на перший рядок: 3 немає, 10 прийшов двічі, 1 — після 2. Відправник нічого з цього не знає, ОС теж не скаржиться. Усе, що буде далі, — це те, що TCP робить за нас, тільки власноруч.

---

## Slide 2. Stop-and-wait: номер + ACK + таймер

**Title:** Надійно, але повільно: 8.65 с

**On-slide text:**
- Кожен пакет має номер; приймач відповідає ACK
- Немає ACK за 200 мс → повтор
- ACK шлемо навіть на дублікат: попередній ACK міг загубитися
- 100 з 100 по порядку, але ≤ 1 повідомлення за RTT

**Image:** `img/02-stop-and-wait.png`. Left: sender retransmits (orange) and the red `8.65 с`. Right: receiver duplicates, green `100 з 100 … ✓`.

**Optional diagram:** the timeline from `explanation_uk.html`, section 2 (DATA #7 lost → 200 мс RTO → повтор → ACK #7).

**Speaker notes:** Відправник не може відрізнити, що загубилося: DATA чи ACK — для нього це просто тиша. Тому приймач підтверджує й дублікати: дублікат зазвичай означає «мій ACK загубився». (Частину дублікатів дає й сам netem, тож лічильники 24 і 21 не віднімайте один від одного.) Час: 100 × 50 мс RTT = 5 с плюс таймаути ≈ 8–9 с. Так працює TFTP.

---

## Slide 3. Ковзне вікно

**Title:** 16 пакетів у польоті: 1.67 с

**On-slide text:**
- До 16 непідтверджених пакетів одночасно, у кожного свій таймер
- Приймач тримає «пакети з майбутнього» в буфері, поки не закриється дірка
- ~5× швидше за stop-and-wait, усе ще 100 з 100 по порядку

**Image:** `img/03-window.png`. Highlight `вікно стоїть на #9` (left) and blue `прийшов раніше за #9` / `чекали в буфері: 75` (right).

**Speaker notes:** Чому не в 16 разів швидше? Кожна втрата все одно коштує 200 мс таймера, а вікно не може проїхати повз дірку: #10–#13 прийшли, але застосунок їх не отримає, доки не прийде повтор #9. Саме проти цього TCP має fast retransmit і SACK.

---

## Slide 4. Те саме через TCP

**Title:** Ядро робить усе це за вас

**On-slide text:**
- Сирий UDP: 10 загублено · stop-and-wait: 8.65 с · вікно: 1.67 с · TCP: 0.10 с
- TCP: великі сегменти (~14 повідомлень в одному), fast retransmit + SACK, адаптивний RTO
- Чого нема в нашій іграшці: керування перевантаженням і потоком — тому QUIC реалізує їх поверх UDP

**Image:** `img/04-summary.png` (left half). Red 8.65, orange 1.67, blue 0.10.

**Table (right half):**

| | сирий UDP | stop-and-wait | вікно | TCP |
|---|---|---|---|---|
| усе дійшло | ✗ | ✓ | ✓ | ✓ |
| по порядку | ✗ | ✓ | ✓ | ✓ |
| без дублікатів | ✗ | ✓ | ✓ | ✓ |
| швидко | — | ✗ | ~ | ✓ |
| керування перевантаженням | ✗ | ✗ | ✗ | ✓ |

**Speaker notes:** TCP виграв, бо пакує байти у великі сегменти й помічає втрату за дубльованими ACK, а не за таймером. Але TCP не завжди 0.1 с: у 2 з 5 запусків загубився SYN, і це коштувало 1 с початкового RTO. Хто робить надійність поверх UDP у житті: QUIC/HTTP/3 (усе + керування перевантаженням), DNS (лише повтор), ігри й VoIP (номери без повторів — демо 04).

---

## Design notes (for the design agent)

- The PNGs are rendered at 2× scale. Place them unscaled or scaled down only, never upscale.
- Don't retype terminal output into text boxes; use the images. Crop only at line boundaries.
- Colours in the screenshots: **red** = loss / slow; **orange** = retransmits, out-of-order, in-between result; **blue** = key facts (sent, buffered, TCP time); **green** = delivered correctly; **grey italic `← …`** = lecturer annotations, not script output; `…` = lines cut.
- Don't change numbers, commands or output text.

## Facts (all from `09-reliable-udp/expected_output.txt`, recorded 23.10.2026, Docker on Linux 6.12.76-linuxkit)

| Fact | Value | Where |
|---|---|---|
| netem | `delay 25ms loss 10% duplicate 5% reorder 25%`, lo MTU 1500 (RTT ≈ 50 мс) | run_demo.sh |
| Raw UDP | 97 datagrams for 100 sent: 10 lost, 7 duplicates, 31 out of order | A, scenario 1 |
| Stop-and-wait | 8.65 с, 124 DATA (24 retransmits), 121 ACK, 21 duplicates dropped, 100/100 in order | A, scenario 2 |
| Window 16 | 1.67 с, 125 DATA (25 retransmits), 19 duplicates dropped, 75 buffered, 100/100 in order | A, scenario 3 |
| TCP | 0.10 с, 100/100 in order | A, scenario 4 |
| Spread over runs | saw 7.5–8.7 с; window 1.5–1.9 с; TCP 0.10–1.18 с (≈1.15 с when SYN lost) | header |
| macOS, no netem | saw 0.02 с, window 0.00 с, 0 retransmits | B |
| Ports | 9109/udp, 9119/tcp | run_demo.sh |
