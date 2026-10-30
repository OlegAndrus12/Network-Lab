"""Спільні дрібниці для демо «надійність поверх UDP» (сумісно з Python 3.9+)."""
import re
import struct

UDP_PORT = 9109
TCP_PORT = 9119
COUNT = 100     # скільки повідомлень у кожному сценарії
MSG_SIZE = 100  # кожне «повідомлення» рівно 100 байтів
RTO = 0.2       # таймер повтору, с (RTT у демо ≈ 50 мс: netem 25 мс в кожен бік)

# Наш власний мініпротокол: 1 байт типу + 4 байти номера, далі дані
HEADER = struct.Struct("!BI")
DATA, ACK, FIN = 1, 2, 3
NAMES = {DATA: "DATA", ACK: "ACK", FIN: "FIN"}


def make_message(i, size=MSG_SIZE):
    """Повідомлення з видимими межами: b'<MSG-1 ------ END-1>' довжиною size байтів."""
    head = "<MSG-{} ".format(i).encode()
    tail = " END-{}>".format(i).encode()
    return head + b"-" * (size - len(head) - len(tail)) + tail


def pack(kind, seq, payload=b""):
    return HEADER.pack(kind, seq) + payload


def unpack(datagram):
    """(тип, номер, дані). Одна дейтаграма = один пакет: межі зберігає сам UDP."""
    kind, seq = HEADER.unpack(datagram[:HEADER.size])
    return kind, seq, datagram[HEADER.size:]


def message_numbers(data):
    """Номери повідомлень у потоці байтів TCP, у порядку появи."""
    return [int(n) for n in re.findall(rb"<MSG-(\d+) ", data)]


def ranges(nums):
    """[1, 2, 3, 7, 9, 10] -> '1-3, 7, 9-10' (коротко для довгих списків)."""
    out = []
    for n in sorted(set(nums)):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else "{}-{}".format(a, b) for a, b in out) or "—"


def rows(nums, per_row=20, width=4):
    """Список номерів рядками по per_row, щоб 100 чисел влізли на екран."""
    for i in range(0, len(nums), per_row):
        yield "".join(str(n).rjust(width) for n in nums[i:i + per_row])
