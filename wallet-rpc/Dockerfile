FROM debian:bookworm-slim

ARG MONERO_VERSION=0.18.4.3

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates bzip2 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://downloads.getmonero.org/cli/monero-linux-x64-v${MONERO_VERSION}.tar.bz2" -o /tmp/monero.tar.bz2 \
    && tar -xjf /tmp/monero.tar.bz2 -C /tmp \
    && cp /tmp/monero-x86_64-linux-gnu-v${MONERO_VERSION}/monero-wallet-rpc /usr/local/bin/monero-wallet-rpc \
    && cp /tmp/monero-x86_64-linux-gnu-v${MONERO_VERSION}/monero-wallet-cli /usr/local/bin/monero-wallet-cli \
    && chmod +x /usr/local/bin/monero-wallet-rpc /usr/local/bin/monero-wallet-cli \
    && rm -rf /tmp/monero*

RUN useradd -m -u 1000 monero \
    && mkdir -p /wallet \
    && chown monero:monero /wallet

USER monero
WORKDIR /wallet
EXPOSE 18082

ENTRYPOINT ["monero-wallet-rpc"]
