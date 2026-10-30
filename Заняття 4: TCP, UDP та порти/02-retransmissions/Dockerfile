# Образ для демо: Linux-інструменти, яких немає на macOS (tc/netem, ss, nstat, tshark)
FROM python:3.12-slim
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      iproute2 ethtool tcpdump tshark procps netcat-openbsd curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
