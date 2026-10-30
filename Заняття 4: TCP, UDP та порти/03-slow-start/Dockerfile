# Образ для демо: Python + інструменти Linux (tc/netem, ss, tcpdump)
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends iproute2 ethtool tcpdump procps netcat-openbsd curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
