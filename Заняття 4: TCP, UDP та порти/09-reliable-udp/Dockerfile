# Маленький Linux для демо: тут є tc/netem, ss і tcpdump (на macOS їх немає)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 procps tcpdump \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /demo
COPY *.py run_demo.sh ./
CMD ["bash", "run_demo.sh"]
