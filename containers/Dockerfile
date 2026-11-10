ARG UBUNTU_BASE=ubuntu:24.04
ARG X86_PLATFORM=linux/amd64
FROM --platform=${X86_PLATFORM} ${UBUNTU_BASE} AS x86-base
FROM ${UBUNTU_BASE} AS toolchain
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
FROM scratch AS qemu-source
ADD --checksum=sha256:847346c1b82c1a54b2c38f6edbd85549edeb17430b7d4d3da12620e2962bc4f3 \
    https://download.qemu.org/qemu-8.2.2.tar.xz /qemu.tar.xz

FROM toolchain AS qemu-build
RUN apt-get -o Acquire::Retries=3 --error-on=any update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        libglib2.0-dev meson ninja-build pkg-config python3-venv
RUN --mount=type=bind,from=qemu-source,target=/source \
    python3 -m tarfile -e /source/qemu.tar.xz /build
WORKDIR /build/qemu-8.2.2
RUN ./configure --target-list=x86_64-linux-user --enable-plugins \
        --disable-system --disable-tools --disable-docs --disable-guest-agent \
        --disable-download --disable-capstone && \
    ninja -C build -j 4 qemu-x86_64 && \
    install -D build/qemu-x86_64 /opt/qemu/bin/qemu-x86_64

FROM toolchain AS worker-common
COPY --from=phoenix_launcher /launch-target /opt/launch-target
COPY --from=x86-base /usr/lib/x86_64-linux-gnu /opt/x86-base/usr/lib/x86_64-linux-gnu
COPY containers/prepare-runtime.sh /opt/prepare-runtime.sh
COPY phoenix_eval /opt/phoenix/phoenix_eval
WORKDIR /opt/phoenix
ENTRYPOINT ["/usr/bin/python3", "-B", "-m", "phoenix_eval.worker"]

FROM worker-common AS worker-amd64
RUN sh /opt/prepare-runtime.sh amd64

FROM worker-common AS worker-arm64
COPY --from=qemu-build /opt/qemu /opt/qemu
RUN sh /opt/prepare-runtime.sh arm64
ADD --checksum=sha256:c53a2af163e80e3f4bc6c60dbdfc84003db329d757e37cd8a16a77e1d82606ff \
    https://raw.githubusercontent.com/qemu/qemu/v8.2.2/include/qemu/qemu-plugin.h /opt/plugin/qemu-plugin.h
COPY containers/code-coverage.c /opt/plugin/code-coverage.c
RUN gcc -std=c11 -Wall -Wextra -Werror -fPIC -shared \
    -o /opt/phoenix-qemu-root/code-coverage.so /opt/plugin/code-coverage.c
