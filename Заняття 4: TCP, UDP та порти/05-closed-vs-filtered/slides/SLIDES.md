# Демо 05: open vs closed vs filtered (секундомір, DROP vs REJECT, UDP). Додається до слайда «Чому TCP сканувати легко…» (Тема 4: TCP, UDP та порти)

---

## Слайд 1. Три відповіді на один SYN

**Текст на слайді:**
- open: SYN-ACK, рукостискання за 0.17 мс
- closed: RST за 0.10 мс, миттєве «ні»
- filtered: тиша, чекаємо весь тайм-аут (5.00 с)
- Сканер розрізняє стани просто за часом

**Зображення:** `img/01-probe-table.png`. Головне: таблиця внизу (три рядки зелений / помаранчевий / фіолетовий). Якщо місця мало, можна обрізати до таблиці (від рядка `ціль | результат …` донизу), але тоді на слайді має лишитися команда `time nc -vz -G 5 …` у тексті або в нотатках.

**Нотатки лектора:**
Спершу питаю аудиторію: що відповість швидше, закритий порт чи порт за фаєрволом? Відкритий і закритий порти відповідають за один обмін сегментами, тому це частки мілісекунди; закритий порт так само швидкий, просто відповідь «ні» (RST). Відфільтрований порт мовчить, і connect() чекає весь наш тайм-аут, 5 с. Час nc (8–19 мс) здебільшого витрачається на запуск процесу; probe.py міряє лише connect(), звідси 0.1 мс. На macOS тайм-аут підключення задає `-G 5`, а не `-w 5`: з `-w 5` nc чекав 1 хв 15 с.

---

## Слайд 2. Що видно в tcpdump: RST проти повторних SYN

**Текст на слайді:**
- closed: SYN → RST,ACK через 13 мкс
- filtered: той самий SYN (той самий seq) повторюється, відповіді немає
- Паузи між повторами: 1 с ×5, потім 2, 4, 8 с

**Зображення:** `img/02-tcpdump-rst-vs-silence.png`. Підсвітити `[R.]` (помаранчевий) у верхньому блоці та стовпець часу 0, 1, 2, 3, 4, 5, 7, 11, 19 (фіолетовий) у нижньому.

**Проста схема (опційно), часова шкала:** горизонтальна вісь «секунди від першого SYN» від 0 до 20. Над віссю фіолетові вертикальні засічки на 0, 1, 2, 3, 4, 5, 7, 11, 19 з підписом «SYN». Під проміжками 5→7, 7→11, 11→19 дужки з підписами «2 с», «4 с», «8 с». Праворуч підпис «відповіді немає».

**Нотатки лектора:**
Закритий порт: ядро одразу відповідає RST, ack = seq + 1, бо так велить RFC 9293 для сегмента на порт без сокета. Відфільтрований: TCP не відрізняє «пакет загубився» від «там нікого немає», тому повторює той самий SYN з тим самим seq: це та сама спроба підключення, не нова. Підручникове «1, 2, 4 с» — класична схема; сучасні macOS і Linux спершу роблять кілька повторів через 1 с, а вже потім подвоюють паузу. Без тайм-ауту застосунку macOS здається через 75 с. Перший SYN має прапорці `[SEW]` (запит ECN), повтори — звичайні `[S]`.

---

## Слайд 3. Адміністратор вибирає, що бачить сканер: DROP vs REJECT

**Текст на слайді:**
- `-j DROP`: тиша → filtered, навіть якщо сервіс працює
- `-j REJECT --reject-with tcp-reset`: підроблений RST → closed
- RST фаєрвола не відрізнити від RST ядра
- Сканер знає лише те, що повернулося

**Зображення:** `img/03-docker-drop-vs-reject.png`. Підсвітити два рядки `127.0.0.1:9115/tcp`: у DROP-блоці `filtered` (фіолетовий), у REJECT-блоці `closed` (помаранчевий). Обидва рази на 9115 працює open_server.py.

**Нотатки лектора:**
Це детермінована Linux-лабораторія в Docker (`./run_demo.sh docker`), тут filtered не залежить від мережі аудиторії. З DROP навіть працюючий сервіс на 9115 виглядає filtered, а з REJECT tcp-reset — closed: на дроті той самий `[R.]`, seq 0, ack = seq + 1. Тому на периметрі часто ставлять DROP: closed-порт доводить, що хост живий і досяжний. tcpdump бачить відкинуті SYN, бо захоплює до ланцюжка INPUT: filtered означає «ніхто не відповів», а не «пакет не дійшов».

---

## Слайд 4. Чому UDP сканувати важко

**Текст на слайді:**
- closed: ICMP port unreachable, миттєво (0.30 мс)
- open і filtered: однакова тиша → open|filtered
- Кожен «тихий» порт коштує повного тайм-ауту
- `nc -vzu` на macOS каже «succeeded!» навіть для закритого порту

**Зображення:** `img/04-udp-ambiguity.png`. Підсвітити два рядки `open|filtered` (відкритий 9115 і 9105 за DROP дають однаковий результат) і `succeeded!` для закритого 9105.

**Проста схема: три колонки** (заголовки: «відкритий», «закритий», «відфільтрований»). У кожній колонці зліва прямокутник «Сканер», справа прямокутник «Порт».
- відкритий: стрілка «UDP-датаграма» →; зворотної стрілки немає; підпис «застосунок мовчить» → результат «тиша».
- закритий: стрілка «UDP-датаграма» →; зворотна стрілка ← «ICMP port unreachable» (помаранчева) → результат «closed, миттєво».
- відфільтрований: стрілка «UDP-датаграма» → обривається на значку стіни «фаєрвол (DROP)»; зворотної стрілки немає → результат «тиша».
Під колонками «відкритий» і «відфільтрований» одна спільна фіолетова дужка з підписом «open|filtered: не розрізнити».
(Опційно поруч мініверсія для TCP: SYN-ACK / RST / тиша — три різні відповіді.)

**Нотатки лектора:**
У UDP немає рукостискання. Закритий порт ядро позначає ICMP-помилкою, а відкритий порт зазвичай мовчить, бо застосунок не розуміє порожньої датаграми, тож відкритий і відфільтрований виглядають однаково. Тому nmap пише open|filtered і чекає тайм-аут на кожному такому порту; щоб розговорити сервіс, він надсилає справжній запит протоколу (наприклад, DNS-запит на 53). «succeeded» від `nc -vzu` означає лише «помилки не прийшло»: на macOS він збрехав навіть про закритий порт, хоча tcpdump бачив ICMP. Підсумок: TCP завжди відповідає (SYN-ACK або RST), якщо пакет ніхто не відкинув; UDP відповідає лише тоді, коли порт закритий.

---

## Design notes (for the design agent)

- The four PNGs are 2x renders of real terminal output. Place them unscaled or scaled down only; never upscale, never re-typeset or retype the output. Crop only along whole lines.
- Colour meaning (keep consistent across slides and diagrams): green `#4ec96b` = open, orange `#f0a35a` = closed / RST / ICMP unreachable, purple `#c4a5ff` = filtered / silence / open|filtered. Light-blue = section headers, grey italic = our annotations (`← …`), white bold = commands and flags.
- Must not change: any number, timestamp, port (9105 closed, 9115 open, 10.255.255.1:80 filtered), and the commands. The macOS command is `nc -vz -G 5 …` (NOT `-w 5`, which hangs ~75 s on macOS). Linux/Docker uses `nc -vz -w 5`.
- Keep terms as is: SYN, SYN-ACK, RST, ACK, ICMP, open / closed / filtered / open|filtered (nmap terms), DROP / REJECT, tcpdump flags `[S]`, `[R.]`, `[SEW]`.
- Image 02 ends with the `nc … Operation timed out` line; in the raw log it was printed above the capture (captured separately). The line is real, only moved to the end for reading order.
- Sources: HTML in `slides/src/`, re-render with `slides/src/render.sh <name> <W> <H>`.

## Facts (all from `05-closed-vs-filtered/expected_output.txt`, real runs on 22.10.2026)

| Fact | Value | Section |
|---|---|---|
| probe.py, macOS: open 127.0.0.1:9115 | SYN-ACK, 0.17 мс, open | A |
| probe.py, macOS: closed 127.0.0.1:9105 | RST, 0.10 мс, closed | A |
| probe.py, macOS: filtered 10.255.255.1:80 | тиша, 5.00 с, filtered | A |
| `time nc -vz -G 5` open / closed / filtered (macOS) | 0.019 s / 0.008 s / 5.010 s | A |
| RST after SYN on lo0 (macOS) | 00:00:00.017497 → 00:00:00.017510 (13 µs) | A |
| SYN retries, macOS, `nc -vz -G 20 10.255.255.1 80` | at 0, 1, 2, 3, 4, 5, 7, 11, 19 s; no reply | B |
| `nc -vz -w 5 10.255.255.1 80` on macOS | 1:15.01 total (‑w does not bound connect) | C |
| `nc -vz -G 5 10.255.255.1 80` on macOS | 5.033 total | C |
| UDP macOS: closed 9105 / open 9115 | ICMP port unreachable 0.30 мс closed / тиша 2.00 с open\|filtered | D |
| `nc -vzu 127.0.0.1 9105` on macOS (port closed) | "succeeded!", exit 0 | D |
| Docker kernel | Linux 6.12.76-linuxkit, tcp_syn_retries=6, tcp_syn_linear_timeouts=4 | E |
| Docker DROP: `time nc -vz -w 8 127.0.0.1 9105` | timed out, real 8.017 s, 7 SYNs (0 … 7.179351 s) | E.2 |
| Docker DROP probe.py (timeout 3) | 9115: 3.01 с filtered (listener running); 9105: 3.00 с filtered | E.2 |
| Docker REJECT tcp-reset | RST after 9 µs; probe.py 9115: 0.28 мс closed (listener running), 9105: 0.19 мс closed | E.3 |
| Docker UDP | closed 9105: ICMP 0.54 мс; open 9115: 2.00 с open\|filtered; 9105 + DROP: 2.00 с open\|filtered | E.4 |
| Docker classic backoff (CLASSIC_BACKOFF=1) | SYNs at 0, 1.04, 3.09, 7.12 s (gaps 1, 2, 4 s) | F |
