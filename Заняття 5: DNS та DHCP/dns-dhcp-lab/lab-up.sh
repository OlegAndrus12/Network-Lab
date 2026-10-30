#!/usr/bin/env bash
# «Міні-інтернет у ноутбуці»: лабораторія DHCP + DNS на Linux network namespaces.
# Потрібно: Linux (або VM / контейнер з --privileged), root, пакети:
#   iproute2 dnsmasq-base isc-dhcp-client bind9 unbound dnsutils tcpdump python3 curl iputils-ping
# Запуск:  sudo bash lab-up.sh      Прибрати: sudo bash lab-down.sh
set -euo pipefail
LAB=/tmp/netlab
rm -rf "$LAB"; mkdir -p "$LAB"

# ---------- 1. «Комутатор» і «кабелі» ----------
ip link add br-lab type bridge
ip link set br-lab up

add_host () {            # add_host <ім'я> <IP/маска або dhcp> <MAC>
  local ns=$1 addr=$2 mac=$3
  ip netns add "$ns"
  ip link add "v-$ns" type veth peer name eth0 netns "$ns"
  ip link set "v-$ns" master br-lab up
  ip -n "$ns" link set lo up
  ip -n "$ns" link set eth0 address "$mac"
  ip -n "$ns" link set eth0 up
  [ "$addr" != dhcp ] && ip -n "$ns" addr add "$addr" dev eth0
  mkdir -p "/etc/netns/$ns"
  # власні resolv.conf і hosts для кожного «комп’ютера» (ip netns exec підставляє їх замість /etc/...)
  touch "/etc/netns/$ns/resolv.conf"
  printf '127.0.0.1 localhost\n' > "/etc/netns/$ns/hosts"
  return 0
}

add_host router   10.10.0.1/24  02:00:00:00:00:01   # шлюз + DHCP-сервер
add_host resolver 10.10.0.53/24 02:00:00:00:00:53   # рекурсивний резолвер
add_host root     10.10.0.11/24 02:00:00:00:00:11   # кореневий сервер «.»
add_host tld      10.10.0.12/24 02:00:00:00:00:12   # TLD-сервер «lab.»
add_host auth     10.10.0.13/24 02:00:00:00:00:13   # authoritative для neoversity.lab
add_host web      10.10.0.80/24 02:00:00:00:00:80   # вебсервер www
add_host api1     10.10.0.81/24 02:00:00:00:00:81
add_host api2     10.10.0.82/24 02:00:00:00:00:82
add_host api3     10.10.0.83/24 02:00:00:00:00:83
add_host laptop   dhcp          02:00:00:00:00:aa   # клієнт: адреси ще немає
add_host printer  dhcp          02:00:00:00:00:50   # клієнт із резервацією

# ---------- 2. DHCP-сервер (dnsmasq) на router ----------
cat > $LAB/dnsmasq.conf <<'EOF'
port=0                                  # тільки DHCP, без DNS
interface=eth0
bind-interfaces
dhcp-range=10.10.0.100,10.10.0.150,255.255.255.0,2m   # пул і оренда 2 хв
dhcp-option=option:router,10.10.0.1                   # шлюз
dhcp-option=option:dns-server,10.10.0.53              # DNS-резолвер
dhcp-option=option:domain-name,neoversity.lab
dhcp-host=02:00:00:00:00:50,10.10.0.50,printer        # резервація за MAC
dhcp-leasefile=/tmp/netlab/dnsmasq.leases
log-dhcp
EOF
ip netns exec router dnsmasq -C $LAB/dnsmasq.conf --log-facility=$LAB/dhcp.log --pid-file=$LAB/dnsmasq.pid

# ---------- 3. Ієрархія DNS (BIND) ----------
mk_named () {   # mk_named <ns> <ім'я зони> <файл зони> [ще зона файл]
  local ns=$1; shift
  local d=$LAB/$ns; mkdir -p $d
  {
    echo "options { directory \"$d\"; listen-on { any; }; listen-on-v6 { none; };"
    echo "  recursion no; dnssec-validation no; pid-file \"$d/named.pid\"; };"
    while [ $# -gt 0 ]; do echo "zone \"$1\" { type primary; file \"$2\"; };"; shift 2; done
    echo "controls { inet 127.0.0.1 port 953 allow { 127.0.0.1; } keys { k; }; };"
    echo "key k { algorithm hmac-sha256; secret \"bGFiLWxhYi1sYWItbGFiLWxhYi1sYWItbGFiLWxhYg==\"; };"
  } > $d/named.conf
}

# --- корінь «.» ---
mkdir -p $LAB/root
cat > $LAB/root/root.zone <<'EOF'
$TTL 86400
.                  IN SOA a.root-servers.lab. admin.lab. 1 1800 900 604800 86400
.                  IN NS  a.root-servers.lab.
a.root-servers.lab. IN A  10.10.0.11
; делегування зони lab. на TLD-сервер (NS + «клейовий» A-запис)
lab.               IN NS  ns.nic.lab.
ns.nic.lab.        IN A   10.10.0.12
; зворотна зона для PTR
0.10.10.in-addr.arpa. IN NS ns1.neoversity.lab.
ns1.neoversity.lab.   IN A  10.10.0.13
EOF
mk_named root . root.zone

# --- TLD «lab.» ---
mkdir -p $LAB/tld
cat > $LAB/tld/lab.zone <<'EOF'
$TTL 86400
lab.               IN SOA ns.nic.lab. admin.nic.lab. 1 1800 900 604800 86400
lab.               IN NS  ns.nic.lab.
ns.nic.lab.        IN A   10.10.0.12
a.root-servers.lab. IN A  10.10.0.11
; делегування neoversity.lab на сервер власника домену
neoversity.lab.    IN NS  ns1.neoversity.lab.
ns1.neoversity.lab. IN A  10.10.0.13
EOF
mk_named tld lab. lab.zone

# --- authoritative для neoversity.lab ---
mkdir -p $LAB/auth
cat > $LAB/auth/neoversity.lab.zone <<'EOF'
$TTL 3600
@        IN SOA  ns1.neoversity.lab. admin.neoversity.lab. ( 2026102701 3600 900 604800 300 )
@        IN NS   ns1
ns1      IN A    10.10.0.13
@        IN A    10.10.0.80
www  60  IN A    10.10.0.80
www      IN AAAA fd00:10::80
shop     IN CNAME www
api  30  IN A    10.10.0.81
api  30  IN A    10.10.0.82
api  30  IN A    10.10.0.83
@        IN MX   10 mail
@        IN MX   20 backup-mail
mail     IN A    10.10.0.25
backup-mail IN A 10.10.0.26
@        IN TXT  "v=spf1 mx -all"
@        IN TXT  "neo-site-verification=8f3k2l9q"
_dmarc   IN TXT  "v=DMARC1; p=reject; rua=mailto:dmarc@neoversity.lab"
_http._tcp.api IN SRV 10 5 80 api
@        IN CAA  0 issue "letsencrypt.org"
EOF
# навмисно великий TXT (~1,5 КБ) — щоб побачити повтор запиту по TCP
python3 -c "print('big IN TXT ' + ' '.join('\"k=%02d-%s\"' % (i, 'x'*90) for i in range(16)))" >> $LAB/auth/neoversity.lab.zone
cat > $LAB/auth/rev.zone <<'EOF'
$TTL 3600
@   IN SOA ns1.neoversity.lab. admin.neoversity.lab. 1 3600 900 604800 300
@   IN NS  ns1.neoversity.lab.
80  IN PTR www.neoversity.lab.
25  IN PTR mail.neoversity.lab.
EOF
mk_named auth neoversity.lab. neoversity.lab.zone 0.10.10.in-addr.arpa. rev.zone

for ns in root tld auth; do ip netns exec $ns named -c $LAB/$ns/named.conf -u root; done

# ---------- 4. Рекурсивний резолвер (Unbound) ----------
cat > $LAB/root.hints <<'EOF'
.                   3600000 NS a.root-servers.lab.
a.root-servers.lab. 3600000 A  10.10.0.11
EOF
cat > $LAB/unbound.conf <<EOF
server:
  interface: 0.0.0.0
  access-control: 10.10.0.0/24 allow
  do-ip6: no
  username: ""
  chroot: ""
  directory: "$LAB"
  pidfile: "$LAB/unbound.pid"
  root-hints: "$LAB/root.hints"
  module-config: "iterator"
  harden-referral-path: no
  qname-minimisation: no
  rrset-roundrobin: yes
  local-zone: "10.in-addr.arpa." nodefault
  domain-insecure: "."
  do-not-query-localhost: no
  logfile: "$LAB/unbound.log"
  log-queries: yes
remote-control:
  control-enable: yes
  control-interface: 127.0.0.1
  control-use-cert: no
EOF
ip netns exec resolver unbound -c $LAB/unbound.conf

# ---------- 5. Вебсервери ----------
mkdir -p $LAB/www && echo "Привіт з www.neoversity.lab (10.10.0.80)" > $LAB/www/index.html
ip netns exec web python3 -m http.server 80 --directory $LAB/www >/dev/null 2>&1 &
for i in 1 2 3; do
  mkdir -p $LAB/api$i && echo "відповідає api$i (10.10.0.8$i)" > $LAB/api$i/index.html
  ip netns exec api$i python3 -m http.server 80 --directory $LAB/api$i >/dev/null 2>&1 &
done
sleep 1
echo "Лабораторію запущено. Клієнти laptop і printer поки без адрес."
