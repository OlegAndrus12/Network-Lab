"""
Layers 5/6 - TLS: what HTTPS actually puts on the wire.

The TLS engine runs on memory buffers (MemoryBIO), so we see every byte before it
goes to the TCP socket. TLS data travels in records with a 5-byte header:
[type 1][version 2][length 2]   type 22 = Handshake, 23 = ApplicationData (encrypted)
"""
import socket
import ssl

HOST = "example.com"
RECORD_TYPES = {20: "ChangeCipherSpec", 21: "Alert", 22: "Handshake (plaintext)", 23: "ApplicationData (encrypted)"}

unparsed = {"→": b"", "←": b""}  # leftover bytes of an incomplete record, per direction


def show_records(direction, data):
    # one TCP read can hold several records, or only part of one
    buffer = unparsed[direction] + data
    # buffer[3:5] = the record's length field; only print records that have fully arrived
    while len(buffer) >= 5 and len(buffer) >= 5 + int.from_bytes(buffer[3:5]):
        length = int.from_bytes(buffer[3:5])
        print(f"  {direction} {RECORD_TYPES.get(buffer[0], buffer[0]):<28} {length:>5} bytes")
        buffer = buffer[5 + length:]
    unparsed[direction] = buffer


sock = socket.create_connection((HOST, 443))  # plain TCP; TLS runs on top of it
# Instead of letting ssl talk to the socket directly, it reads from `incoming` and writes to
# `outgoing`. We move the bytes between these buffers and the socket ourselves, so we can print them.
incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
# server_hostname: sent to the server as SNI, and checked against the certificate
tls = ssl.create_default_context().wrap_bio(incoming, outgoing, server_hostname=HOST)


def send():
    data = outgoing.read()  # whatever TLS wants to send (already encrypted, except the hellos)
    show_records("→", data)
    if data[:1] == b"\x16" and HOST.encode() in data:  # 0x16 = 22 = Handshake record
        print(f"    ^ '{HOST}' is readable in plaintext in the ClientHello (SNI)")
    sock.sendall(data)


def receive():
    data = sock.recv(65536)
    show_records("←", data)
    incoming.write(data)  # hand the server's bytes to TLS


print("Handshake:")
while True:
    try:
        tls.do_handshake()  # advances the handshake as far as it can with the data it has
        send()
        break
    except ssl.SSLWantReadError:  # "I need the server's answer before I can continue"
        send()
        receive()

cert = tls.getpeercert()
# the certificate's subject/issuer come as nested tuples, e.g. ((('commonName', 'example.com'),),)
subject, issuer = dict(x[0] for x in cert["subject"]), dict(x[0] for x in cert["issuer"])
print(f"\n{tls.version()}, cipher {tls.cipher()[0]}")
print(f"Certificate for {subject.get('commonName')}, issued by {issuer.get('organizationName')}")

request = f"GET / HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode()
tls.write(request)  # plaintext in...
encrypted = outgoing.read()  # ...encrypted record out
print(f"\nApp writes:  {request[:40]!r}...")
print(f"Wire gets:   {encrypted[:40].hex(' ')}...")  # starts with 17 03 03 = ApplicationData record
sock.sendall(encrypted)

response = b""
while not response:
    try:
        response = tls.read(1024)  # decrypts whatever has arrived
    except ssl.SSLWantReadError:  # nothing decryptable yet - read more from the socket
        receive()
status_line = response.split(b"\r\n")[0]
print(f"Decrypted response: {status_line!r}")
