"""
Layer 4 - Transport: TCP vs UDP on localhost.

TCP is a connection that carries a byte STREAM: message boundaries disappear.
UDP sends independent DATAGRAMS: no connection, but each message arrives whole.
"""
import socket
import time

MESSAGES = [b"HELLO", b"OSI", b"LAYER-4"]

print("TCP")
server = socket.create_server(("127.0.0.1", 0))  # port 0 = let the OS pick a free port
client = socket.create_connection(server.getsockname())  # 3-way handshake (SYN, SYN-ACK, ACK) happens here
conn, client_address = server.accept()  # the kernel already finished the handshake; accept() just picks it up
print(f"  connected {client_address} -> {server.getsockname()}  (client port picked by the OS)")
for message in MESSAGES:
    client.sendall(message)  # three separate sends...
time.sleep(0.1)  # let all bytes arrive before reading
print(f"  sent {len(MESSAGES)} messages, one recv() got: {conn.recv(1024)!r}")  # ...one read gets all of them

print("\nUDP")
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM = UDP, SOCK_STREAM = TCP
server.bind(("127.0.0.1", 0))
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for message in MESSAGES:
    client.sendto(message, server.getsockname())  # no connect(): every datagram carries its own address
for _ in MESSAGES:
    print(f"  recvfrom() got: {server.recvfrom(1024)[0]!r}")  # one datagram per read, never merged

print("\nNobody listening on the port")
CLOSED_PORT = 9  # "discard" port - nothing listens on it on a normal machine
try:
    socket.create_connection(("127.0.0.1", CLOSED_PORT))
except ConnectionRefusedError:
    print("  TCP: connection refused - the OS answered our SYN with a RST")
client.sendto(b"anyone there?", ("127.0.0.1", CLOSED_PORT))
print("  UDP: sendto() succeeded - UDP never knows whether anyone received it")
