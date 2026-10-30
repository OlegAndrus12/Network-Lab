# Linux-середовище для демо: python + tcpdump/ss (на macOS без sudo tcpdump недоступний)
FROM python:3.12-slim
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends tcpdump iproute2 procps > /dev/null \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
