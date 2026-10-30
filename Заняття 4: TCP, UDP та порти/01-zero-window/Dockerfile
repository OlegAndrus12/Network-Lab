# Linux-контейнер для демо: tcpdump, ss (iproute2), tc/netem без sudo на хості
FROM python:3.12-slim
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends iproute2 tcpdump procps netcat-openbsd curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
