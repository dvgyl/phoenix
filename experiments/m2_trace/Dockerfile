FROM --platform=linux/arm64 ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852 AS build
ENV SOURCE_DATE_EPOCH=1794268800
ADD --checksum=sha256:641de77d8f142cfd62a1a6f964ba67b20754d3337c480efb529d086075a06c9a \
    https://snapshot.ubuntu.com/ubuntu/20261107T000000Z/pool/main/c/ca-certificates/ca-certificates_20240203_all.deb /opt/ubuntu-ca.deb
RUN dpkg-deb -x /opt/ubuntu-ca.deb /opt/ubuntu-ca && \
    mkdir -p /etc/ssl/certs && \
    cat /opt/ubuntu-ca/usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt && \
    rm -rf /opt/ubuntu-ca /opt/ubuntu-ca.deb && \
    printf '%s\n' 'Types: deb' \
      'URIs: https://snapshot.ubuntu.com/ubuntu/20261107T000000Z/' \
      'Suites: noble noble-updates noble-security' 'Components: main universe' \
      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
      'Check-Valid-Until: no' > /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get -o Acquire::Retries=3 --error-on=any update && \
    apt-get install -y --no-install-recommends \
      gcc-13=13.3.0-6ubuntu2~24.04.1 libc6-dev=2.39-0ubuntu8.9 \
      libglib2.0-dev=2.80.0-6ubuntu3.10 python3=3.12.3-0ubuntu2.1 \
      python3-venv=3.12.3-0ubuntu2.1 ninja-build=1.11.1-2 pkgconf=1.8.1-2build1 \
      make=4.3-4.1build2 xz-utils=5.6.1+really5.4.5-1ubuntu0.4 && \
    rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894 \
    https://download.qemu.org/qemu-9.2.0.tar.xz /opt/source/qemu-9.2.0.tar.xz
RUN mkdir /build && tar -xJf /opt/source/qemu-9.2.0.tar.xz -C /build
WORKDIR /build/qemu-9.2.0
RUN printf '%s  %s\n' e4c5bf7e92075d7c1e6b1dcb6164bca6c549b2912a62b56ce1a777be4c7b8788 include/qemu/qemu-plugin.h | sha256sum -c - && \
    ./configure --cc=gcc-13 --target-list=x86_64-linux-user --enable-plugins \
      --disable-system --disable-tools --disable-docs --disable-guest-agent \
      --disable-download --disable-capstone && \
    build/pyvenv/bin/meson --version | grep -x 1.5.0 && \
    ninja -C build -j 2 qemu-x86_64 && \
    cp COPYING LICENSE /opt/source/ && \
    cp include/qemu/qemu-plugin.h /opt/source/
COPY experiments/m2_trace/observer.c /opt/source/observer.c
RUN gcc-13 -std=c11 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared \
      $(pkg-config --cflags glib-2.0) -I /opt/source /opt/source/observer.c \
      -o /opt/observer.so $(pkg-config --libs glib-2.0)
COPY --from=accepted /opt/launch-target /opt/launch-target
COPY --from=accepted /opt/phoenix-qemu-root /opt/phoenix-qemu-root
COPY --from=accepted /accepted-image-id /opt/source/accepted-image-id
RUN find /opt/phoenix-qemu-root/usr/lib/x86_64-linux-gnu /opt/phoenix-qemu-root/usr/lib/locale \
      -type f -exec sha256sum {} + | sort > /opt/source/guest-runtime.sha256 && \
    install -m 0555 build/qemu-x86_64 /opt/phoenix-qemu-root/usr/bin/qemu-x86_64 && \
    install -m 0444 /opt/observer.so /opt/phoenix-qemu-root/observer.so && \
    for library in $({ ldd build/qemu-x86_64; ldd /opt/observer.so; } | awk '{for (i=1;i<=NF;i++) if ($i ~ "^/") print $i}' | sort -u); do \
      install -D "$library" "/opt/phoenix-qemu-root$library"; done && \
    dpkg-query -W > /opt/source/packages.txt
COPY phoenix /opt/phoenix/phoenix
COPY phoenix_eval /opt/phoenix/phoenix_eval
COPY experiments/m2_trace /opt/phoenix/experiments/m2_trace
COPY experiments/m2_trace/Dockerfile /opt/source/Dockerfile
COPY THIRD_PARTY_NOTICES /opt/source/THIRD_PARTY_NOTICES
RUN sha256sum /opt/observer.so /opt/phoenix-qemu-root/usr/bin/qemu-x86_64 > /opt/source/observer.sha256
WORKDIR /opt/phoenix
ENTRYPOINT ["/usr/bin/python3", "-B", "-m", "experiments.m2_trace.worker"]
