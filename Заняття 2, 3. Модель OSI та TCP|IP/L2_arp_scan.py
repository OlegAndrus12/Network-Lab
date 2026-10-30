"""
Layer 2 - ARP: "Who has 192.168.0.7? Tell me your MAC address."

Broadcasts an ARP request for every address in your local /24 and lists who answers.
ARP never crosses a router - it only works inside the local network.

Needs root:  sudo .venv/bin/python L2_arp_scan.py
Only scan networks you are allowed to scan.
"""
from scapy.all import ARP, Ether, conf, srp

my_ip = conf.route.route("0.0.0.0")[1]  # look up the default route; [1] = our IP on that interface
network = my_ip.rsplit(".", 1)[0] + ".0/24"  # 192.168.0.155 -> 192.168.0.0/24 (256 addresses)

# "/" stacks layers: an Ethernet frame carrying an ARP packet.
# Broadcast MAC, because we don't know the target's MAC yet - that's what we're asking for.
# A whole network in pdst makes scapy generate one request per address.
request = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network)
answered, unanswered = srp(request, timeout=2, verbose=False)  # send/receive at Layer 2; returns (answered, unanswered)
print(unanswered)
print(f"Devices on {network}:")
for _, reply in answered:
    print(f"  {reply.psrc:<16} {reply.hwsrc}")  # psrc = sender's IP, hwsrc = sender's MAC
