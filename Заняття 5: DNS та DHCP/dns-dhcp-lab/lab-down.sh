#!/usr/bin/env bash
# Прибирає лабораторію «міні-інтернет»
for p in /tmp/netlab/*/named.pid /tmp/netlab/unbound.pid /tmp/netlab/dnsmasq.pid /tmp/netlab/dhclient-*.pid; do
  [ -f "$p" ] && kill "$(cat "$p")" 2>/dev/null
done
pkill -f "http.server 80" 2>/dev/null
pkill dhclient 2>/dev/null
for ns in router resolver root tld auth web api1 api2 api3 laptop printer rogue; do
  ip netns del $ns 2>/dev/null; rm -rf /etc/netns/$ns
done
ip link del br-lab 2>/dev/null
rm -rf /tmp/netlab
echo "Прибрано."
