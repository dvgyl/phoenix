# Use the verified image build cache

## Decision

Use the previous pinned image recipes while the Ubuntu snapshot service
has intermittent index failures. Reuse their verified local build cache
to build updated worker packages. Record the actual resulting image
identities before any evaluation.

## Evidence

The package-only fallback passed its signed repository tests. The normal
image build then failed while fetching signed snapshot indexes. Two
native CI attempts and local retries returned server errors. Direct
probes of the service's official DNS addresses also failed on some
required indexes.

The previous recipes have successful local build layers for the pinned
toolchains, QEMU, and checker. The worker package can be updated from
the current source with the normal build scripts and those layers.

## Limits

A clean build still requires the upstream snapshot. Native CI remains
pending. The package fallback proposal is retained in ADR 0009 and Git
history.
