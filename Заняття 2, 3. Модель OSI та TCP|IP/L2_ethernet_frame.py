"""
Layer 2 - Data Link: an Ethernet frame built by hand.

[dst MAC 6][src MAC 6][EtherType 2][payload 46..1500][FCS 4]

The FCS is a CRC-32 of the whole frame. The receiving network card recomputes it
and silently drops the frame if even one bit changed. Ethernet detects errors,
it doesn't fix them - resending is TCP's job (Layer 4).
"""
import struct
import zlib

dst_mac = bytes.fromhex("ffffffffffff")  # broadcast: every device on the LAN (normally: your router's MAC)
src_mac = bytes.fromhex("020000aaaaaa")  # 02 in the first byte = made-up ("locally administered") address
ethertype = 0x0800  # what's inside: 0x0800 IPv4, 0x0806 ARP, 0x86DD IPv6
payload = b"Hello, Layer 2!".ljust(46, b"\x00")  # Ethernet needs at least 46 bytes, so pad with zeros

header = dst_mac + src_mac + struct.pack("!H", ethertype)  # "!H" = 2-byte number, big-endian (network order)
fcs = struct.pack("<I", zlib.crc32(header + payload))  # CRC-32, sent little-endian ("<I")
frame = header + payload + fcs  # 14 + 46 + 4 = 64 bytes, the smallest legal Ethernet frame


def receive(frame):
    # fields sit at fixed positions: [0:6] dst, [6:12] src, [12:14] type, [14:-4] payload, [-4:] FCS
    text = frame[14:-4].rstrip(b"\x00")
    print(f"  dst={frame[0:6].hex(':')}  src={frame[6:12].hex(':')}  type=0x{frame[12:14].hex()}  payload={text!r}")
    # recompute the CRC over everything except the FCS and compare with the one that arrived
    if struct.unpack("<I", frame[-4:])[0] == zlib.crc32(frame[:-4]):
        print("  FCS OK -> frame accepted")
    else:
        print("  FCS MISMATCH -> frame dropped")


print("Frame on the wire:", frame.hex(" "))
receive(frame)

print("\nSame frame with one bit flipped in transit:")
damaged = bytearray(frame)
damaged[16] ^= 0b00000001  # XOR flips the lowest bit of byte 16 ("l" -> "m"), like electrical noise would
receive(bytes(damaged))
