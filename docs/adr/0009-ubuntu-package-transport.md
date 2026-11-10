# Use package-only Ubuntu download fallback

## Decision

Use the pinned Ubuntu snapshot as the sole source of signed indexes.
Permit the official Ubuntu package pool as a package-only fallback.
Use APT's mirror transport with the `type:deb` filter. The snapshot's
authenticated index determines each package version and hash.
[APT mirror transport](https://manpages.ubuntu.com/manpages/noble/man1/apt-transport-mirror.1.html),
[APT authentication](https://manpages.ubuntu.com/manpages/noble/man8/apt-secure.8.html).

Fetch the CA bootstrap package from the official Ubuntu archive.
Check its pinned SHA-256 before extraction. Remove the persistent
integrity package cache because APT can reuse a cached archive after
a size check. Each Dockerfile is included in its image source digest.
[APT archive acquisition](https://raw.githubusercontent.com/Debian/apt/2.7.14/apt-pkg/acquire-item.cc).

## Evidence

Three x86-64 CI attempts stopped on snapshot package delivery. Two
returned HTTP 503. The other failed the CA package checksum.

A signed synthetic repository probe passed on APT 2.8.3 in both pinned
Linux worker images. The download-only install used the fallback when
the primary package request failed. It rejected a same-size package
with one changed byte. Index failure and a modified index signature
stopped the update. The request log contained no fallback index requests.
Each scenario used empty lists and package caches.

The probe used the installed GnuPG 2.5.21 executable to sign its
synthetic repository. The installation uses 15,784 KiB on the host.
The tool runs as a separate process. The notice entry followed the
first probe. Further reuse requires the notice and license check first.

## Limits

An unavailable snapshot index stops the build. An official pool can
remove an old package. Normal image builds, package inventory checks,
and public CI are required before adoption. Reused build layers require
a trusted cache.
