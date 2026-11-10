# Use a hardened CMake build profile

## Decision

Use stack protection on every function. On Linux, resolve dynamic
symbols at startup and make the relocation data read-only after
startup. Apply the same profile to both methods and both architectures.

The profile uses options from the pinned C compilers and linker. It
requires no new dependency. [GCC stack protection](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html) and [GNU linker options](https://sourceware.org/binutils/docs/ld/Options.html) describe the options.

## Evidence

Public `-O0` builds of `bitstats` and `filemarks` shared up to 297 bytes
of executable code with independently rebuilt projects. The GCC
`bitstats` match included 166 bytes from C runtime startup code. The
exact-byte rule rejects this match.

Public probe `m1-public-text-profile-c234d81c6c5e45cf8f7f1a77e7a93ec8`
compared the default profile with two hardened profiles. Stack
protection with read-only relocations and startup symbol resolution
removed every 64-byte match in the four x86-64 comparisons.

Public run `m1-public-hardened-e675da21dc2a43f4ba29dd132b067fd4`
matched all 32 variant-case pairs in all four compiler and architecture
builds. All four variants passed the source integrity checks. The
checker still detected 64 and 65 original code bytes in typed C
initializers. The separate data provenance check rejected the 63-byte
control.

## Limits

Independent compilation can produce the same machine code. Keep the
64-byte check on every source and binary artifact. A match remains a
failure, including when the bytes come from the C runtime.
