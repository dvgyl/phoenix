#!/bin/sh
set -eu

copy_file() {
    source_root=$1
    path=$2
    target_root=$3
    mkdir -p "$target_root$(dirname "$path")"
    cp -L "$source_root$path" "$target_root$path"
}

make_root() {
    source_root=$1
    target_root=$2
    triple=$3
    loader=$4
    install -d "$target_root/usr/lib/$triple" "$target_root/usr/lib/locale"
    ln -s usr/lib "$target_root/lib"
    if [ "$triple" = x86_64-linux-gnu ]; then
        mkdir -p "$target_root/lib64"
        ln -s "../lib/$triple/$loader" "$target_root/lib64/$loader"
    else
        ln -s "$triple/$loader" "$target_root/usr/lib/$loader"
    fi
    for library in libc.so.6 libm.so.6 libdl.so.2 librt.so.1 libpthread.so.0 \
        libgcc_s.so.1 libutil.so.1 libresolv.so.2 "$loader"; do
        copy_file "$source_root" "/usr/lib/$triple/$library" "$target_root"
    done
    cp -a /usr/lib/locale/C.utf8 "$target_root/usr/lib/locale/"
}

case "$1" in
    amd64)
        make_root "" /opt/phoenix-runtime x86_64-linux-gnu ld-linux-x86-64.so.2
        ;;
    arm64)
        make_root "" /opt/phoenix-runtime aarch64-linux-gnu ld-linux-aarch64.so.1
        make_root /opt/x86-base /opt/phoenix-qemu-root x86_64-linux-gnu ld-linux-x86-64.so.2
        install -D /opt/qemu/bin/qemu-x86_64 /opt/phoenix-qemu-root/usr/bin/qemu-x86_64
        for path in $(ldd /opt/qemu/bin/qemu-x86_64 | awk '{for (i=1;i<=NF;i++) if ($i ~ "^/") print $i}'); do
            copy_file "" "/usr/lib/aarch64-linux-gnu/$(basename "$path")" /opt/phoenix-qemu-root
        done
        ln -s aarch64-linux-gnu/ld-linux-aarch64.so.1 /opt/phoenix-qemu-root/lib/ld-linux-aarch64.so.1
        ;;
    *)
        printf '%s\n' "Unsupported container architecture." >&2
        exit 1
        ;;
esac
