ARG UBUNTU_BASE=ubuntu:24.04
ARG X86_PLATFORM=linux/amd64
FROM --platform=${X86_PLATFORM} ${UBUNTU_BASE} AS x86-base
FROM ${UBUNTU_BASE}
ARG UBUNTU_SNAPSHOT
ARG TARGETARCH
ADD --checksum=sha256:641de77d8f142cfd62a1a6f964ba67b20754d3337c480efb529d086075a06c9a \
    https://snapshot.ubuntu.com/ubuntu/20261107T000000Z/pool/main/c/ca-certificates/ca-certificates_20240203_all.deb \
    /opt/ubuntu-ca.deb
RUN dpkg-deb -x /opt/ubuntu-ca.deb /opt/ubuntu-ca && \
    mkdir -p /etc/ssl/certs && \
    cat /opt/ubuntu-ca/usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt && \
    rm -rf /opt/ubuntu-ca /opt/ubuntu-ca.deb
RUN printf '%s\n' 'Types: deb' \
        "URIs: https://snapshot.ubuntu.com/ubuntu/$UBUNTU_SNAPSHOT/" \
        'Suites: noble noble-updates noble-security' 'Components: main universe' \
        'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
        'Check-Valid-Until: no' > /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get -o Acquire::Retries=3 --error-on=any update && \
    if [ "$TARGETARCH" = arm64 ]; then set -- qemu-user; else set --; fi && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        binutils clang cmake gcc libc6-dev make python3 "$@" && \
    rm -rf /var/lib/apt/lists/*
COPY --from=x86-base /usr/lib/x86_64-linux-gnu /opt/x86-base/usr/lib/x86_64-linux-gnu
COPY containers/prepare-runtime.sh /opt/prepare-runtime.sh
RUN sh /opt/prepare-runtime.sh "$TARGETARCH"
COPY phoenix_eval /opt/phoenix/phoenix_eval
WORKDIR /opt/phoenix
ENTRYPOINT ["/usr/bin/python3", "-B", "-m", "phoenix_eval.worker"]
