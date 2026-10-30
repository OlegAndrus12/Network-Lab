"""
Layer 7 - WebSocket server from scratch: a tiny chat room.

Run it, then open http://localhost:8765 in two browser tabs (or run L7_websocket_client.py).

1. The browser sends a normal HTTP request with "Upgrade: websocket"
2. The server answers "101 Switching Protocols"
3. The same TCP connection now carries frames, in both directions, at any time:
   [FIN + opcode][MASK + length][mask key 4][masked payload]
"""
import base64
import hashlib
import pathlib
import socket
import threading
import time

PORT = 8765
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # fixed value from RFC 6455, same for every server
PAGE = (pathlib.Path(__file__).parent / "websocket_chat.html").read_bytes()
clients = []


def send_frame(conn, text):
    data = text.encode()
    # length: up to 125 fits in one byte; longer = the value 126 followed by a 2-byte length
    length = bytes([len(data)]) if len(data) < 126 else bytes([126]) + len(data).to_bytes(2)
    conn.sendall(bytes([0x81]) + length + data)  # 0x81 = FIN (last fragment) + opcode 1 (text); server frames are not masked


def broadcast(text):
    for conn in clients:
        try:
            send_frame(conn, text)
        except OSError:  # that client already disconnected
            pass


def read_frame(stream):
    first, second = stream.read(2)
    opcode, length = first & 0x0F, second & 0x7F  # low 4 bits = opcode; low 7 bits = length (top bit = MASK flag)
    if length == 126:
        length = int.from_bytes(stream.read(2))
    mask = stream.read(4)  # browsers must mask every frame they send
    masked = stream.read(length)
    payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(masked))  # XOR with the 4-byte key, repeating
    print(f"  frame: opcode={opcode} length={length} mask={mask.hex()} wire={masked[:12].hex(' ')} -> {payload!r}")
    return opcode, payload


def handle(conn, address):
    stream = conn.makefile("rb")
    lines = []
    while (line := stream.readline()) not in (b"\r\n", b""):  # read HTTP request lines until the empty line
        lines.append(line.decode().strip())
    headers = {k.lower(): v for k, _, v in (line.partition(": ") for line in lines[1:])}  # "Name: value" -> dict

    if headers.get("upgrade", "").lower() != "websocket":  # plain HTTP: serve the chat page
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n"
                     b"Content-Length: %d\r\n\r\n" % len(PAGE) + PAGE)
        conn.close()
        return

    # Proof the server really speaks WebSocket: hash the client's random key with the GUID
    accept = base64.b64encode(hashlib.sha1((headers["sec-websocket-key"] + GUID).encode()).digest()).decode()
    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 b"Sec-WebSocket-Accept: " + accept.encode() + b"\r\n\r\n")
    print(f"{address} {lines[0]} -> 101 Switching Protocols")  # from here on: frames, not HTTP
    clients.append(conn)
    try:
        while True:
            opcode, payload = read_frame(stream)
            if opcode == 8:  # close
                break
            if opcode == 1:  # text
                broadcast(f"{address[1]}: {payload.decode()}")
    except (OSError, ValueError):  # connection dropped mid-frame
        pass
    clients.remove(conn)
    conn.close()


def push_time():
    while True:  # the server can talk without being asked - plain HTTP can't do this
        time.sleep(15)
        broadcast(f"[server push] it's {time.strftime('%H:%M:%S')}")


server = socket.create_server(("127.0.0.1", PORT))
threading.Thread(target=push_time, daemon=True).start()
print(f"Open http://localhost:{PORT}")
try:
    while True:
        conn, address = server.accept()
        threading.Thread(target=handle, args=(conn, address), daemon=True).start()  # one thread per client
except KeyboardInterrupt:
    pass
