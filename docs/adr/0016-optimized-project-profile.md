# Use a fixed optimized project profile

## Decision

Compile generated projects with `-O2` and stack protection on every
function. Use Linux read-only relocations and startup symbol resolution.
Apply this fixed profile to both methods and architectures.

The generation prompt requires exact original-data evidence for every
nonempty C string. This includes static-assertion diagnostic strings.
An empty diagnostic string satisfies that rule.

## Evidence

The public decimal control matched behavior while its generated
`-O0` parser shared at least 64 original instruction bytes. Repair also
added unsupported static-assertion messages.

Public run `m1-public-decimal-profile-5f0189f210fd4772ab5155335d0fb73a`
compared the same candidate with empty diagnostic strings under two
optimization levels. Both profiles passed behavior across four builds.
The `-O0` build failed the exact-byte check. The `-O2` build passed
integrity.

A pinned-container regression builds the public decimal fixture with
both compilers on each architecture. It checks large unsigned values
and the exact-byte boundary. The previous profile failed its x86-64
GCC check on a matching byte window.

## Limits

Every original-text match of at least 64 bytes remains a failure.
Optimization provides a normal release build profile. Independent
compilation can still produce identical machine code.

The new profile passed the four pinned compiler and architecture tests.
The earlier profile failed the GCC byte-window assertion. The negative
control reached that assertion after its build and behavior checks passed.
