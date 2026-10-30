"""
Layer 7 - DNS over UDP, built by hand.

Query = [12-byte header][question]
The name is written as length-prefixed labels: example.com -> 07 example 03 com 00
One UDP datagram goes out, one comes back. No connection, no encryption.
"""
import random
import socket
import struct

NAME = "example.com"
DNS_SERVER = "8.8.8.8"

# Header: 6 two-byte fields - random ID (to match the reply), flags, and how many
# questions / answers / authority / additional records follow.
# Flags 0x0100 = "recursion desired": please find the answer for me.
header = struct.pack("!HHHHHH", random.randint(0, 0xFFFF), 0x0100, 1, 0, 0, 0)
# "example.com" -> b"\x07example\x03com\x00": each label prefixed by its length, 0 = end
qname = b"".join(bytes([len(label)]) + label.encode() for label in NAME.split(".")) + b"\x00"
query = header + qname + struct.pack("!HH", 1, 1)  # type 1 = A (IPv4 address), class 1 = IN (internet)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)
sock.sendto(query, (DNS_SERVER, 53))  # DNS = UDP port 53
response, _ = sock.recvfrom(512)  # classic DNS over UDP is limited to 512 bytes

print(f"Query    ({len(query)} bytes): {query.hex(' ')}")
print(f"Response ({len(response)} bytes): {response.hex(' ')}\n")


def skip_name(pos):
    while response[pos] != 0:
        # Compression: a byte starting with bits 11 (>= 0xC0) is a 2-byte pointer
        # to a name written earlier in the message (here: c0 0c = "the name at offset 12")
        if response[pos] >= 0xC0:
            return pos + 2
        pos += 1 + response[pos]
    return pos + 1


answer_count = struct.unpack("!H", response[6:8])[0]  # bytes 6-7 of the header = number of answers
pos = len(query)  # the response starts with a copy of our question; answers follow it
for _ in range(answer_count):
    pos = skip_name(pos)
    # each answer: name, then type (2), class (2), TTL (4), data length (2), data
    record_type, _, ttl, length = struct.unpack("!HHIH", response[pos:pos + 10])
    data = response[pos + 10:pos + 10 + length]
    if record_type == 1:
        print(f"{NAME} -> {socket.inet_ntoa(data)}  (may be cached for {ttl} s)")
    elif record_type == 5:
        print(f"{NAME} is an alias (CNAME), more records follow")
    pos += 10 + length
