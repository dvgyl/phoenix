# ADR 0035. Reconstruct complete eager collector data

Date: 2026-11-12
Status: Implemented as a pure data unit. Independent review remains required.

Phoenix needs one complete static record for the later typed C renderer.
A selected list of sites can lose shared roles, import evidence, or route
positions. A caller-supplied certificate can also use an old policy.

`prepare_collector_data` accepts exact binary, lift, mapping, full-plan,
and scope bytes. It checks all input byte bounds before parsing or hashing.
It validates both limit records and the request types before reconstruction.
It then reparses the lift and mapping, proves addresses, rebuilds the full
plan, and compiles the scope with the installed policy. The supplied plan
and scope must equal their complete canonical reconstructions.

`CollectorData` is a frozen dataclass. It retains the complete `TracePlan`,
`ScopeSelection`, and checked `ElfImage`. It also retains the original
identity, all required evidence digests, geometry, and exact transport
limits. Nested collections are tuples. `record()` returns `FrozenRecord`
objects and tuple children. Object entries have sorted names. Arrays keep
their original order. No selected-field projection replaces a source record.

The canonical encoder traverses all dataclass fields. It writes ASCII JSON
with sorted keys, compact separators, and one final LF. It checks each
output token against the byte bound before it appends the token. It does
not first allocate an `asdict` copy of the complete data. `sha256` hashes
these exact canonical bytes. Neither the hash nor the dataclass constructor
proves which process produced the data.

`TransportLimits` is separate from `CaptureLimits`. Its maxima are 16 MiB
for the original, 64 MiB each for lift and mapping, and 16 MiB for the
canonical data. The original bound matches `MAX_PROGRAM_BYTES` in
`phoenix_eval/worker.py`. The record maxima are 4,096 users, routes, and
omissions, 65,536 gaps per inventory, and 1,024 load segments. Route path
positions and memberships each have a maximum of `4096 * 32 * 9`.
Every supplied lower limit remains binding. Boolean, float, nonpositive,
and raised limits are invalid. The snapshot width is exactly eight bytes.

Executable geometry uses the minimum executable load address and the
maximum executable file end. Load-memory geometry includes all load
segments, including nonexecutables and memory-only spans. An exclusive
end can equal `2**64`. The record does not assign a runtime bias, a QEMU
address, a library identity, or a provider identity.

This unit keeps unsupported active guards as explicit data. It retains
empty contracts and the eager-only profile. It does not grant permission
to execute an unsupported path. The nine-file policy identity algorithm
is unchanged. The retained `read_selected_generation` helper legitimately
changes that identity relative to the old frame branch. This unit does
not define or change an admission identity.

The corrected Astra design requires later independent C decoding,
compiled-table retention, trusted build issuance, per-trial calibration,
and exact launch association. Those units are not implemented here.
The full capture review remains OPEN after provider screening. This unit
neither retries nor replaces that review. Production admission remains
HOLD. No runtime authority, frame tree, or local runtime fact is issued.
