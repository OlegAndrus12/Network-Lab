# Лабораторія «Міні-інтернет»: команди до слайдів

Запуск (Linux або Linux-VM, від root):

```bash
sudo bash lab-up.sh
```

Скорочення: `L="sudo ip netns exec laptop"`, `R="sudo ip netns exec router"`.

## Частина A — DHCP

| Крок | Команда | Що побачите |
|---|---|---|
| 1. Ноутбук без адреси | `$L ip -4 addr show eth0` · `$L ip route` · `$L ping -c1 10.10.0.53` | порожньо · порожньо · `Network is unreachable` |
| 1. Слухаємо DHCP на сервері (2-й термінал) | `$R tcpdump -n -i eth0 'port 67 or port 68'` | |
| 2. DORA | `$L dhclient -v eth0` | DISCOVER → OFFER → REQUEST → ACK, `bound to 10.10.0.110` |
| 2. Детально (опції) | `$R tcpdump -n -vv -i eth0 'port 67 or port 68'` | Lease-Time 120, RN 60, RB 105, маска, DNS, шлюз |
| 3. Результат | `$L ip -4 addr show eth0` · `$L ip route` · `$L cat /etc/resolv.conf` | `10.10.0.110/24 dynamic`, `default via 10.10.0.1`, `nameserver 10.10.0.53` |
| 4. Оренда на сервері | `cat /tmp/netlab/dnsmasq.leases` · `date -u -d @<число>` | |
| 4. Оренда на клієнті | `cat /tmp/netlab/laptop.leases` (якщо запускали з `-lf`) або `/var/lib/dhcp/dhclient.leases` | renew / rebind / expire |
| 4. Резервація | `sudo ip netns exec printer dhclient -v eth0` | `bound to 10.10.0.50` |
| 5. Продовження | зачекати ~50 с після кроку 2, дивитися tcpdump | unicast Request від 10.10.0.110 і ACK |
| 5. Звільнення | `$L dhclient -r -v eth0` | `DHCPRELEASE of 10.10.0.110` |

## Частина B — DNS (після `$L dhclient eth0`)

| Крок | Команда |
|---|---|
| 1. Відповідь dig | `$L dig www.neoversity.lab` |
| 2. Ієрархія | `$L dig +trace www.neoversity.lab` |
| 3. Рекурсія та ітерації | спершу `sudo ip netns exec resolver unbound-control -c /tmp/netlab/unbound.conf reload`, потім `sudo ip netns exec resolver tcpdump -n -i eth0 'udp port 53'` і `$L dig mail.neoversity.lab` |
| Кеш | `$L dig www.neoversity.lab` двічі — TTL і Query time |
| authoritative | `$L dig @10.10.0.13 www.neoversity.lab +norec` (прапорець `aa`) |
| UDP → TCP | `$L dig big.neoversity.lab TXT +bufsize=512` |
| Записи | `$L dig shop.neoversity.lab` · `dig neoversity.lab MX` · `TXT` · `NS` · `SOA` · `CAA` · `dig _http._tcp.api.neoversity.lab SRV` · `dig -x 10.10.0.80` |
| nslookup | `$L nslookup shop.neoversity.lab` · `$L nslookup -type=mx neoversity.lab` |
| NXDOMAIN | `$L dig nope.neoversity.lab` |
| hosts | `echo '10.10.0.81 www.neoversity.lab' \| sudo tee -a /etc/netns/laptop/hosts`, потім `$L getent ahostsv4 www.neoversity.lab`, `$L dig +short www.neoversity.lab`, `$L curl http://www.neoversity.lab` |
| Round Robin | `$L dig +short api.neoversity.lab` кілька разів; `for i in 1 2 3 4 5 6; do $L curl -s http://api.neoversity.lab; done` |
| Поширення змін (TTL) | у `/tmp/netlab/auth/neoversity.lab.zone` змінити `www 60 IN A` на `10.10.0.90` і збільшити serial; перезапустити authoritative: `sudo kill $(cat /tmp/netlab/auth/named.pid); sudo ip netns exec auth named -c /tmp/netlab/auth/named.conf -u root`; порівняти `$L dig @10.10.0.13 www.neoversity.lab` і `$L dig www.neoversity.lab` |
| Від імені до сторінки | `$L curl http://shop.neoversity.lab` |

## Запис для Wireshark

```bash
sudo tcpdump -i br-lab -w my-lab.pcap 'port 67 or port 68 or port 53 or port 80'
```

Фільтри: `dhcp`, `dhcp.option.dhcp == 2`, `dns`, `dns.flags.response == 0`, `dns.flags.truncated == 1`, `tcp.port == 53`, `dns.qry.name == "shop.neoversity.lab"`, `http`.

Прибрати все: `sudo bash lab-down.sh`
