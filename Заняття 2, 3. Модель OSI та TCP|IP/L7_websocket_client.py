"""
Layer 7 - WebSocket client from scratch. Start L7_websocket_server.py first.

Shows the HTTP Upgrade handshake, then sends masked frames and prints the replies.
"""
import base64
import hashlib
import os
import socket

HOST, PORT = "127.0.0.1", 8765
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # fixed value from RFC 6455

sock = socket.create_connection((HOST, PORT))
stream = sock.makefile("rb")  # file-like view: readline() and read(exactly n bytes)

key = base64.b64encode(os.urandom(16)).decode()  # random key; the server must transform it to prove it understood
request = (f"GET / HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n"
           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
sock.sendall(request.encode())
print(request)

response = b""
while (line := stream.readline()) != b"\r\n":  # read response headers until the empty line
    response += line
print(response.decode())
expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
print("Sec-WebSocket-Accept is correct:", expected in response.decode(), "\n")


def send_text(text):
    data = text.encode()
    mask = os.urandom(4)  # clients must mask every frame (stops old proxies from misreading it as HTTP)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
    frame = bytes([0x81, 0x80 | len(data)]) + mask + masked  # 0x81 = FIN + text; 0x80 = MASK bit, plus length (< 126)
    print(f"sending {text!r} as {frame.hex(' ')}")
    sock.sendall(frame)


def read_text():
    _, second = stream.read(2)
    length = second & 0x7F  # low 7 bits = payload length
    if length == 126:  # 126 = "the real length is in the next 2 bytes"
        length = int.from_bytes(stream.read(2))
    return stream.read(length).decode()  # server frames are not masked


for text in ["hello", "OSI layer 7"]:
    send_text(text)
    print("received:", read_text())

sock.sendall(bytes([0x88, 0x80]) + os.urandom(4))  # 0x88 = FIN + opcode 8 (close), masked, empty payload
