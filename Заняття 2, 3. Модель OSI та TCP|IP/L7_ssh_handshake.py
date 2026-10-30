"""
Layer 7 - SSH: the part of the handshake you can still read.

1. Both sides exchange a text version line: "SSH-2.0-..."
2. Both send KEXINIT: lists of the algorithms they support
3. Key exchange -> from here on, everything is encrypted (even the username)

We do steps 1-2 and hang up. No login is attempted.
"""
import socket
import struct

HOST = "github.com"
LISTS = ["key exchange", "host key", "encryption c->s", "encryption s->c",
         "MAC c->s", "MAC s->c", "compression c->s", "compression s->c"]

sock = socket.create_connection((HOST, 22))  # SSH = TCP port 22
stream = sock.makefile("rb")  # file-like view of the socket: readline() and read(exactly n bytes)

print("server says:", stream.readline())  # the server speaks first, in plain text
sock.sendall(b"SSH-2.0-OSI_Lecture\r\n")  # our version line; any name after "SSH-2.0-" works

# From now on, binary packets: [length 4][padding length 1][payload][random padding]
length, padding = struct.unpack("!IB", stream.read(5))
payload = stream.read(length - 1)[:length - 1 - padding]  # read the rest, drop the padding at the end
print(f"next packet: {length} bytes, message type {payload[0]} (20 = KEXINIT)\n")

pos = 17  # skip message type (1 byte) + random cookie (16 bytes)
for name in LISTS:
    # each list = 4-byte length + comma-separated algorithm names, in order of preference
    size = struct.unpack("!I", payload[pos:pos + 4])[0]
    print(f"{name}:\n    {payload[pos + 4:pos + 4 + size].decode().replace(',', ', ')}")
    pos += 4 + size
