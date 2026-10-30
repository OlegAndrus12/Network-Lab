"""
All layers - encapsulation: one DNS question wrapped layer by layer, like the OS does it.

Each layer puts its own header in front of the data from the layer above.
Saves encapsulation.pcap - open it in Wireshark to see the same layers dissected.
"""
import socket
import struct
import time


def checksum(data):
    # Internet checksum: sum of 16-bit words, overflow folded back in, bits inverted
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


# L7 - DNS: "what is the IP address of example.com?" (same bytes L7_dns_raw.py builds)
dns = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)

# L4 - UDP: source port, destination port 53 (DNS), length, checksum (0 = not used, allowed in IPv4)
udp_header = struct.pack("!HHHH", 54321, 53, 8 + len(dns), 0)

# L3 - IPv4: 0x45 = version 4 + header length 5x4 = 20 bytes; total length; ID and fragment
# fields (unused here); TTL 64; protocol 17 = UDP; checksum (0 for now); source and destination IP
ip_header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + 8 + len(dns), 0, 0, 64, 17, 0,
                        socket.inet_aton("192.168.0.10"), socket.inet_aton("8.8.8.8"))
ip_header = ip_header[:10] + struct.pack("!H", checksum(ip_header)) + ip_header[12:]  # checksum goes in bytes 10-11

# L2 - Ethernet: destination MAC (your router, not 8.8.8.8!), source MAC, EtherType 0x0800 = IPv4
ethernet_header = bytes.fromhex("020000bbbbbb") + bytes.fromhex("020000aaaaaa") + b"\x08\x00"

frame = ethernet_header + ip_header + udp_header + dns

for name, part in [("L2 Ethernet header", ethernet_header), ("L3 IPv4 header", ip_header),
                   ("L4 UDP header", udp_header), ("L7 DNS message", dns)]:
    print(f"{name:<20} {len(part):>2} bytes  {part.hex(' ')}")
print(f"\nFrame: {len(frame)} bytes, of which {len(dns)} are the actual question.")

with open("encapsulation.pcap", "wb") as f:
    # pcap file header: magic number, format version 2.4, timezone, accuracy, max length, link type 1 = Ethernet
    f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
    # per-packet header: timestamp (seconds, microseconds), captured length, original length
    f.write(struct.pack("<IIII", int(time.time()), 0, len(frame), len(frame)) + frame)
print("Saved encapsulation.pcap - open it in Wireshark.")
