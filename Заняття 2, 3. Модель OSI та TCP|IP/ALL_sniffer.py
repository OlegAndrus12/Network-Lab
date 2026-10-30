"""
All layers - live sniffer: prints every captured packet layer by layer.

Run it as root in a second terminal while another demo is running:
    sudo .venv/bin/python ALL_sniffer.py
"""
from scapy.all import sniff

# BPF filter, same syntax as tcpdump/Wireshark: "icmp", "arp", "tcp port 443", "tcp port 22", "tcp port 8765"
FILTER = "udp port 53"
INTERFACE = None  # None = default network; "lo0" (macOS) or "lo" (Linux) for localhost demos

# scapy layer name -> OSI layer; anything not listed (DNS, Raw data, ...) is treated as application data
OSI_LAYER = {"Ethernet": "L2", "Loopback": "L2", "ARP": "L2", "Padding": "L2",
             "IP": "L3", "IPv6": "L3", "ICMP": "L3", "TCP": "L4", "UDP": "L4"}


def show(packet):
    print()
    layer = packet
    while layer:  # each layer's payload is the next layer up: Ethernet -> IP -> UDP -> DNS
        print(f"  {OSI_LAYER.get(layer.name, 'L7')}  {layer.name:<10} {layer.mysummary()}")  # mysummary = this layer only
        layer = layer.payload


print(f"Sniffing '{FILTER}' - Ctrl+C to stop")
sniff(filter=FILTER, iface=INTERFACE, prn=show, store=False)  # prn = called for every packet; store=False = don't keep them in memory
