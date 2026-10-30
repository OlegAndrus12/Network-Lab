"""
Layer 1 - Physical: how bits become a signal on the wire.

NRZ:        1 = high, 0 = low. A long run of equal bits has no edges,
            so the receiver can't tell where one bit ends and the next begins.
Manchester: every bit has an edge in the middle (0 = high->low, 1 = low->high),
            so the receiver recovers the clock from the signal. Used by 10 Mbit Ethernet.
"""

DATA = b"\x00\xa5"  # try b"Hi"

bits = "".join(f"{byte:08b}" for byte in DATA)  # each byte as 8 binary digits, e.g. 0xa5 -> "10100101"

# Each bit is drawn as two half-bit samples (1 = high, 0 = low).
nrz = [int(bit) for bit in bits for _ in range(2)]  # level stays the same for the whole bit
manchester = [level for bit in bits for level in ((0, 1) if bit == "1" else (1, 0))]  # level flips mid-bit


def draw(levels):
    return "".join("‾‾" if level else "__" for level in levels)


print("bits       ", "".join(f"{bit:^4}" for bit in bits))
print("NRZ        ", draw(nrz))
print("Manchester ", draw(manchester))
