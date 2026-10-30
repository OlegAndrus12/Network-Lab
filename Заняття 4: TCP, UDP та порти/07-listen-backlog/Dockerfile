# Linux-середовище для демо: ss, tcpdump, nc, sysctl
FROM python:3.12-slim
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends iproute2 tcpdump procps netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
