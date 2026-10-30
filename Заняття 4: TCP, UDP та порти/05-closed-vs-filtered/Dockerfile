# Linux-лабораторія для демо 05: iptables, tcpdump, ss, netcat-openbsd
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends iproute2 iptables tcpdump procps netcat-openbsd curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
COPY probe.py open_server.py linux_lab.sh ./
CMD ["bash", "/demo/linux_lab.sh"]
