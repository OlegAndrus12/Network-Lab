"""
Layer 3 - Network: ping built by hand.

ICMP Echo Request = [type 8][code 0][checksum 2][id 2][seq 2][payload]
The reply arrives inside an IPv4 header, which tells us the TTL and the addresses.

No root needed on macOS. On Linux, run with sudo if you get a permission error.
"""
import socket
import struct
import time

HOST = "8.8.8.8"


def checksum(data):
    # Internet checksum (RFC 1071), also used by IP, TCP and UDP:
    # add the data up as 16-bit numbers, fold any overflow back in, invert the bits.
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


# An ICMP socket: we write the ICMP message, the OS wraps it in an IP header (protocol 1).
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
sock.settimeout(2)

for seq in range(1, 4):
    payload = b"OSI lecture ping"
    # "!BBHHH" = 1-byte type, 1-byte code, 2-byte checksum, id, sequence number.
    # Build once with checksum 0, compute the checksum over that, then build again with it filled in.
    header = struct.pack("!BBHHH", 8, 0, 0, 0x1234, seq)
    packet = struct.pack("!BBHHH", 8, 0, checksum(header + payload), 0x1234, seq) + payload

    start = time.perf_counter()
    sock.sendto(packet, (HOST, 0))  # port 0: ICMP has no ports, that's a Layer 4 idea
    try:
        reply, _ = sock.recvfrom(1024)
    except socket.timeout:
        print(f"seq={seq} timeout")
        continue
    ms = (time.perf_counter() - start) * 1000

    if reply[0] >> 4 == 4:  # first 4 bits = IP version; macOS includes the IPv4 header, Linux doesn't
        # fixed positions in the IPv4 header: byte 8 TTL, byte 9 protocol, 12-15 source, 16-19 destination
        ttl, protocol = reply[8], reply[9]
        src, dst = socket.inet_ntoa(reply[12:16]), socket.inet_ntoa(reply[16:20])
        print(f"seq={seq} reply {src} -> {dst}  protocol={protocol} (ICMP)  ttl={ttl}  time={ms:.1f} ms")
    else:
        print(f"seq={seq} reply from {HOST}  time={ms:.1f} ms")
    time.sleep(1)
