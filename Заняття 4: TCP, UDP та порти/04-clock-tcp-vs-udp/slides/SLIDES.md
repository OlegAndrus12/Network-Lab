# Demo 04 «Годинник: TCP vs UDP при 10% втрат», attaches to: «Застарілі дані гірші за втрачені», вправа 5, слайд порівняння TCP vs UDP

---

## Slide 1. Що робимо

**Title:** Годинник через TCP і UDP: 10% втрат

**On-slide text:**
- Відправник «тікає» кожні 100 мс: той самий тік іде UDP-датаграмою на :9104 і TCP-сегментом на :9114
- netem у Docker-контейнері: `delay 50ms loss 10%`
- Отримувач друкує обидва потоки поруч: № тіка, час надсилання, час отримання, лаг
- Питання до аудиторії: який годинник виглядатиме краще?

**Image:** none (or a small crop of the header rows of `img/01-two-clocks.png`: the prompt line, `=== Docker (Linux), netem на lo: delay 50ms loss 10% ===` and the column headers).

**Diagram:** left box «Відправник (clock.py send)», right box «Отримувач (clock.py recv)». Between them two parallel arrows: the upper one, orange, labelled «UDP :9104 — датаграма на кожен тік»; the lower one, blue, labelled «TCP :9114 — потік байтів, `\n` між тіками». A cloud over both arrows labelled «netem: +50 мс, губить 10% пакетів (і ACK теж)». Under the boxes, a dashed frame around everything labelled «Docker-контейнер, інтерфейс lo».

**Speaker notes:** Кожні 100 мс відправник надсилає номер тіка й поточний час двома шляхами: окремою UDP-датаграмою і по одному TCP-з'єднанню. Втрати й затримку додає netem, а він є лише в Linux, тому все працює в Docker-контейнері й не зачіпає мережу ноутбука. Перш ніж запускати, спитайте: «При 10% втрат який годинник буде кращим?». Більшість відповідає «TCP, бо він надійний».

---

## Slide 2. Що бачимо (hero)

**Title:** UDP пропускає тіки, TCP замерзає

**On-slide text:**
- UDP: «пропущено 1 тік» і далі вчасно, лаг ≈ 51 мс
- TCP: нічого не губить, але «ЗАМЕРЗЛО на 906 мс», потім пачка старих тіків
- Тік #071 по TCP прийшов із лагом 857 мс

**Image:** `img/01-two-clocks.png` (real output, two short stretches of one run joined with `…`). Highlight: the two red `‖ ЗАМЕРЗЛО на … мс` lines and the run of red `← пачка` on the right; the amber `··· пропущено 1 тік ···` lines on the left. If space is tight, crop to the lower stretch (from `··· пропущено 1 тік ···` above #075 down to #081): that alone shows the 906 ms stall.

**Speaker notes:** Ліворуч UDP: тік загубився, програма це бачить лише тому, що ми самі нумеруємо тіки, і просто показує наступний вчасно. Праворуч TCP: втратився один сегмент, і майже секунду годинник стоїть на #070, хоча новіші тіки вже лежать у ядрі отримувача. Потім усе приходить пачкою з однаковим часом отримання і лагом 857, 756, 657… мс. Покажіть: TCP доставив усе, але що варте показання годинника, якому вже 857 мс?

---

## Slide 3. Цифри: медіана та сама, хвіст ні

**Title:** Надійність коштує затримки в хвості

**On-slide text:**
- UDP: втрачено 18 з 150 (12%), макс лаг 69 мс, годинник не зупинявся
- TCP: втрачено 0, але 14 замерзань, найдовше 906 мс, макс лаг 857 мс
- Медіана в обох 51 мс: різниця лише в «хвості»

**Image:** `img/03-lag-chart.png` as the main visual (light chart, lag per tick from the same run). Optionally `img/02-summary.png` beside or below it (the real summary text). Highlight in the chart: the blue sawtooth peaks vs the flat orange line near 51 ms; the orange tick marks under the x-axis are the 18 lost UDP ticks.

**Speaker notes:** Це той самий 15-секундний запуск, кожна точка це один тік. Синя «пилка»: кожен зубець — замерзання, після якого лаг падає кроками по 100 мс, бо пачка тіків приходить разом. Помаранчева лінія майже рівна на 51 мс (50 мс netem плюс трохи), з дірками там, де UDP-тік загубився. Середні однакові, а найгірший випадок у TCP у 12 разів гірший: для годинника, гри чи голосу застарілі дані гірші за втрачені. Числа в кожному запуску інші, бо втрати випадкові.

---

## Slide 4. Чому: блокування на початку черги (head-of-line blocking)

**Title:** Чому TCP замерзає: один загублений сегмент тримає всі наступні

**On-slide text:**
- TCP віддає програмі байти лише по порядку: `recv()` не може перестрибнути дірку
- Новіші сегменти чекають у буфері ядра, поки повтор не закриє дірку
- Повтор зазвичай швидкий (дубль ACK + SACK), довші паузи — таймер RTO
- Тому VoIP, ігри, DNS — на UDP; QUIC (HTTP/3) теж поверх UDP

**Image:** `img/04-tcpdump.png` (real tcpdump text from a separate run, see caveats). Highlight: the amber dup-ACK line `ack 537`, the red retransmission `seq 537:558`, the green `ack 621` (hole closed, #026–#029 released at once).

**Diagram (head-of-line blocking):** a horizontal row of five boxes labelled «Буфер отримувача (ядро)»: `#025` (green, label «віддано програмі»), `#026` drawn as an empty dashed box with a red ✗ and label «дірка: загублено», then `#027`, `#028`, `#029` (grey, label «вже прийшли, але чекають»). Above the row, a red barrier/wall between the dashed box and the program, labelled «recv() не може пропустити дірку». Above-right, a box «Програма: годинник стоїть». Below, a curved arrow from a box «Відправник» to the dashed box labelled «повтор #026 (після дубль ACK + SACK)». Then a second small state: all four boxes `#026–#029` with one arrow to «Програма» labelled «пачка: усе разом».

**Speaker notes:** Коли сегмент загубився, а наступні дійшли, ядро отримувача тримає їх у черзі «не за порядком» і не віддає програмі. У tcpdump видно дубль ACK 537: «досі чекаю байт 537», а в SACK відправник бачить, що новіші байти вже є, і одразу повторює 537:558. Важливо: більшість замерзань у цьому демо — це не тайм-аут RTO, а швидкий повтор після SACK, і тому пауза ≈ 300 мс (інтервал тіка 100 + RTT 100 + ще 50 мс). Довгі замерзання на 600–900 мс з'являються, коли губиться і повтор або ACK, і тоді рятує лише RTO з подвоєнням.

---

## Design notes (for the design agent)

- Use the PNGs as images. Do not retype terminal output or chart values; keep them crisp (rendered at 2x, do not upscale beyond native size; downscaling is fine).
- Terminal colours: amber = UDP and lost UDP ticks (`пропущено`); blue = TCP label; red = TCP stall (`ЗАМЕРЗЛО`), burst (`← пачка`), bad numbers; green = good outcome / ACK that closes the hole; grey italic `← …` = annotations added for the slide (not program output); `…` = lines cut.
- Chart colours: blue `#2a78d6` = TCP, orange `#eb6834` = UDP. Keep the same mapping in any diagrams you draw (TCP blue, UDP orange/amber).
- Never change numbers, commands (`./run_demo.sh`, `netem delay 50ms loss 10%`), port numbers (9104/UDP, 9114/TCP), or terms (SACK, RTO, ACK, QUIC, netem).
- `img/04-tcpdump.png` is tcpdump text (trimmed: `win 512` and `ack 1` fields removed, as in the lecturer notes); there's no Wireshark screenshot. Optional: the lecturer can capture `tcp port 9114` in Wireshark and screenshot the «TCP Dup ACK» / «TCP Retransmission» rows (black-and-red colouring) to replace it.
- Caveats that limit claims: numbers differ in every run (random loss); the 906 ms stall's cause (lost retransmission/ACK → RTO) is inferred from timing, not captured; the tcpdump excerpt comes from a separate run from the hero/summary screenshots.

## Facts (all from `04-clock-tcp-vs-udp/expected_output.txt`, section 1 unless noted)

- Setup: Docker (Linux 6.12.76-linuxkit), `netem delay 50ms loss 10%`, 150 ticks × 100 ms (15 s); UDP :9104, TCP :9114.
- UDP: отримано 132 з 150, втрачено 18 (12%); лаг медіана 51 мс, макс 69 мс; найдовша дірка 3 тіки; годинник не зупинявся.
- TCP: отримано 150 з 150, втрачено 0; лаг медіана 51 мс, макс 857 мс; замерзань 14, найдовше 906 мс; пачок 16.
- First stall: `ЗАМЕРЗЛО на 299 мс`, #001 lag 252 мс, then #002 152 мс, #003 52 мс (пачка).
- Longest stall: `ЗАМЕРЗЛО на 906 мс`, #071 lag 857 мс, burst #071–#080 (lags 857 → 59 мс).
- Section 4 (tcpdump, separate run): lost segment `537:558` (тік #026), dup ACK `ack 537` at 02.851, retransmission at 02.902, `ack 621` at 02.952; that stall was 401 мс.
- Explanation (explanation.html): typical stall ≈ 300 мс = 100 (tick) + 100 (RTT) + 50 (one way); most stalls are SACK/RACK fast retransmit, not RTO; Linux RTO floor 200 мс.
- Other runs (explanation.html): 16 lost / 19 stalls / max lag 2416 мс; with `DELAY=0ms` (section 2): 10 lost / 5 stalls / max 441 мс stall, max lag 341 мс.
- Chart data: `slides/src/ticks.json`, parsed from section 1 lines 10–214 of expected_output.txt (counts verified against the summary: 132 UDP, 150 TCP, maxima 69 / 857 мс).
