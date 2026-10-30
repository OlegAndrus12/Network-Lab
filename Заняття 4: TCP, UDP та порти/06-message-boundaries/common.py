"""Спільні дрібниці для демо меж повідомлень (сумісно з Python 3.9+)."""
import re
import struct

UDP_PORT = 9106
TCP_PORT = 9116
MSG_SIZE = 100  # кожне «повідомлення» рівно 100 байтів


def make_message(i, size=MSG_SIZE):
    """Повідомлення з видимими межами: b'<MSG-1 ------ END-1>' довжиною size байтів."""
    head = "<MSG-{} ".format(i).encode()
    tail = " END-{}>".format(i).encode()
    return head + b"-" * (size - len(head) - len(tail)) + tail


def short_repr(data, head=14, tail=8):
    """Короткий repr: початок і кінець шматка, середину ховаємо (там лише дефіси)."""
    if len(data) <= head + tail + 6:
        return repr(data)
    return "{} ... {}".format(repr(data[:head]), repr(data[-tail:]))


def markers(data):
    """Які повідомлення (повністю чи частково) потрапили в цей шматок."""
    starts = [m.decode() for m in re.findall(rb"<MSG-\d+", data)]
    ends = [m.decode() for m in re.findall(rb"END-\d+>", data)]
    return "початки: {}; кінці: {}".format(", ".join(starts) or "—", ", ".join(ends) or "—")


# Кадрування (framing) префіксом довжини: 4 байти, big-endian, потім саме повідомлення
HEADER = struct.Struct("!I")


def frame(payload):
    return HEADER.pack(len(payload)) + payload
