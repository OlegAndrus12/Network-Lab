# OSI model: live demos in Python

One small script per idea, ordered bottom-up through the OSI layers. No command-line
arguments: run a script, and to change its target edit the constant at the top
(e.g. `HOST = "example.com"`).

```bash
uv sync                      # once: creates .venv (scapy, for the two root-only scripts)
uv run L1_line_coding.py
```

| Layer | Script | Idea |
|---|---|---|
| 1 Physical | `L1_line_coding.py` | Bits → NRZ vs Manchester signal; why edges matter for the clock |
| 2 Data link | `L2_ethernet_frame.py` | Ethernet frame by hand; CRC catches a flipped bit |
| 2 Data link | `L2_arp_scan.py` | Broadcast "who has this IP?" to the local network (**sudo**) |
| 3 Network | `L3_ping.py` | ICMP echo by hand; TTL and addresses from the IP header |
| 3 Network | `L3_traceroute.py` | TTL = 1, 2, 3... reveals every router on the path |
| 4 Transport | `L4_tcp_vs_udp.py` | TCP stream merges messages, UDP keeps them separate; RST vs silence |
| 5/6 Session/Presentation | `L6_tls_https.py` | TLS records on the wire; hostname visible, everything else encrypted |
| 7 Application | `L7_http_raw.py` | HTTP is plain text over TCP |
| 7 Application | `L7_dns_raw.py` | DNS query/response by hand over UDP |
| 7 Application | `L7_ssh_handshake.py` | SSH version exchange + algorithm negotiation, before encryption starts |
| 7 Application | `L7_websocket_server.py` | HTTP Upgrade → WebSocket frames; chat at http://localhost:8765 |
| 7 Application | `L7_websocket_client.py` | Handshake check + masked frames (start the server first) |
| All | `ALL_encapsulation.py` | One DNS packet wrapped L7 → L4 → L3 → L2; saves a `.pcap` for Wireshark |
| All | `ALL_sniffer.py` | Live capture, each packet printed layer by layer (**sudo**) |

## Root-only scripts

`sudo` won't find `uv`, so call the venv's Python directly:

```bash
sudo .venv/bin/python L2_arp_scan.py
sudo .venv/bin/python ALL_sniffer.py     # set FILTER / INTERFACE at the top of the file
```

Run the sniffer in a second terminal next to another demo, e.g. `FILTER = "udp port 53"`
with `L7_dns_raw.py`, or `FILTER = "tcp port 8765"` + `INTERFACE = "lo0"` with the WebSocket chat.

## Notes

- Tested on macOS. On Linux, ping and traceroute may need `sudo`.
- Most demos need internet access; venue Wi-Fi sometimes blocks ICMP or port 22, so keep a phone hotspot as backup.
- Only run the ARP scan and the sniffer on networks you are allowed to scan.
