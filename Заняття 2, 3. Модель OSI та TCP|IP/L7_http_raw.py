"""
Layer 7 - HTTP/1.1 by hand: it's just text over a TCP connection.

Anyone on the path (Wi-Fi, ISP, proxy) can read and change this.
Compare with L6_tls_https.py, which sends the same text encrypted.
"""
import socket

HOST = "example.com"

request = (
    "GET / HTTP/1.1\r\n"  # method, path, version; HTTP requires \r\n line endings
    f"Host: {HOST}\r\n"  # mandatory: one IP address can host many websites
    "Connection: close\r\n"  # ask the server to close the connection when done, so we know where the end is
    "\r\n"  # empty line = end of headers
)

sock = socket.create_connection((HOST, 80))  # port 80 = plain HTTP
sock.sendall(request.encode())

response = b""
while chunk := sock.recv(4096):  # recv() returns b"" when the server closes the connection
    response += chunk
headers, _, body = response.partition(b"\r\n\r\n")  # headers and body are separated by an empty line

print("=== REQUEST ===")
print(request)
print("=== RESPONSE HEADERS ===")
print(headers.decode())
# With "Transfer-Encoding: chunked" the body starts with the chunk size in hex (e.g. "241" = 577 bytes)
print(f"\n=== BODY ({len(body)} bytes) ===")
print(body[:300].decode(errors="replace"), "...")
