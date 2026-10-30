"""
Layer 3 - Network: traceroute built by hand.

Every router decrements the TTL field of the IP header. When it hits 0, the router
drops the packet and sends back ICMP "Time Exceeded" from its own IP address.
Sending pings with TTL = 1, 2, 3... reveals every router on the path.

No root needed on macOS. On Linux, run with sudo if you get a permission error.
"""
import socket
import struct

HOST = "8.8.8.8"
MAX_HOPS = 20


def checksum(data):
    # Internet checksum: sum of 16-bit words, overflow folded back in, bits inverted
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
sock.settimeout(2)

for ttl in range(1, MAX_HOPS + 1):
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)  # set the TTL field of the IP header we send
    # ICMP echo request (type 8), same as in L3_ping.py, with the TTL as sequence number
    header = struct.pack("!BBHHH", 8, 0, 0, 0x1234, ttl)
    sock.sendto(struct.pack("!BBHHH", 8, 0, checksum(header), 0x1234, ttl), (HOST, 0))
    try:
        _, (router, _) = sock.recvfrom(1024)  # we only need the sender's address: the router where TTL hit 0
    except socket.timeout:
        print(f"{ttl:>2}  *  (router didn't answer)")
        continue
    print(f"{ttl:>2}  {router}")
    if router == HOST:  # the destination itself answered with an echo reply: we've arrived
        break
