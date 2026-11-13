# ADR0042. Ordinary byte graph observations, schema 2

Date: 2026-11-13.
Status: Unit A implementation. Independent review remains required.

## Purpose

The ordinary Java decoder can attach an operation to a block while its
`isDead()` result is true. A block cover minimum can differ from the ordinary
function entry. Schema 1 cannot retain these observations under its existing
rules. The new reader uses schema 2 and profile `ordinary-byte-adapter/1`.
The existing readers and publication versions retain their exact contracts.

This decision implements only Unit A of the approved ordinary byte adapter
design. ADR0041 is occupied by the separate ELF reader. The allocation of
0042 does not change the approved design.

## Data and boundary

`parse_pass_record` reads the complete supplied pass record. It checks the
fixed Ghidra, Java, language, compiler, simplification, and printer values.
The pass hash is SHA-256 of canonical pass bytes. It identifies supplied
content. It does not prove that a decompiler call occurred. Unit D must bind
the actual source and tool manifests.

`parse_byte_graph_v2` accepts bytes, an ordinary `LiftIndex`, a `PassRecord`,
and bounded limits. It returns a frozen `ByteGraphV2`. Every retained record
is a frozen dataclass. Every array is a tuple. `record()` returns a detached
JSON object. `to_bytes()` returns sorted, compact ASCII JSON with one final
LF. Noncanonical strict UTF-8 JSON can be read. Hashes use canonical bytes.

The reader has no file, process, environment, provider, publication, or
emission operation. A constructor, a matching hash, or an accepted graph
cannot grant producer or semantic authority.

The graph retains these distinct observations:

- The ordinary function entry and the decoded block at index zero.
- Both cover extrema, or two null endpoints for an empty cover.
- The complete supplied Java operation bank and value bank.
- Actual Java Boolean flags, including true flags on block-owned operations.
- Ordered repeated operands, unused values, and distinct equal-storage keys.
- Raw instruction addresses, including instructions with no raw operations.
- Separate raw and analyzed operation identities.
- Ordered reciprocal edges, including parallel edges and self-loops.
- Explicit native limitations and proof gaps.

`native_entry_address` must be null. All four native-inventory fields must
be `not_exported`. The five global native, entry-effect, and memory-effect
gaps are mandatory. No field can state that these proofs passed.

## Unit A implementation choices

The API did not assign a separate representation to raw instruction sites.
This reader uses its documented `Address` object. The current ordinary index
supports RAM named `ram`. The reader checks entry and instruction addresses
against that exact domain. Supporting another RAM name requires a separately
reviewed index change.

Block indices must equal decoded list slots. The reader rejects null holes
and missing block zero. It never renumbers or inserts a block. The operation
bank must match the supplied ordinary analyzed roster in order and projected
content. Value iteration order remains exact. The ordinary lift cannot
independently authenticate unused values or their iteration order.

Each unowned operation requires its own `unowned_operation` gap. An unknown
mnemonic requires an operation-specific `unsupported_opcode` gap. Recognized
names are the 74 named-case return strings of pinned
`PcodeOp.getMnemonic()`. The ordinary exporter stores these strings.
The six conversion and rounding names are `INT2FLOAT`, `FLOAT2FLOAT`,
`TRUNC`, `CEIL`, `FLOOR`, and `ROUND`. Their `FLOAT_` constant identifiers
are not recognized mnemonics. Recognition does not check semantics.
A phi operation with no parent or a different incoming-edge count requires
its own `phi_binding_unproved` gap. Its actual operands remain unchanged.

A value requires `ssa_unbound` unless exactly one constant, input, or
explicit-definition interpretation applies. A free nonconstant value also
requires that gap. Java constants can be free. All flags remain exact,
including conflicting combinations. Constant bits must equal the observed
offset and fit the value width. Flags are not inferred from storage names.

The record-specific required gaps use only the relevant operation or value
reference. Their other reference fields are null. Global gaps have all
references null. All gaps must be unique and sorted by canonical bytes.

Limits independently bound both operation domains and repeated references.
The reader also bounds functions, blocks, listing blocks, raw instructions,
values, inputs, edges, gaps, source bytes, graph bytes, and JSON depth.
Function range counts and aggregate listing-block range counts use the raw
instruction bound. Listing edge counts use the edge bound. Canonical output
must also fit the graph byte bound.

Limits combine. For example, a full 65,792-value record can exceed the
16 MiB graph cap before its value count exceeds the hard maximum. Tests use
lower value limits to check the exact independent count boundary. The hard
value maximum and its next count also remain subject to the byte cap. The
reference maximum equals 256 operations times 257 references. Exceeding that
maximum also exceeds an input or operation limit. Depth 32 can pass the depth
check but still fail the closed graph shape. Bounds are not a process-memory
guarantee. Later units own program, bundle, context, mapping, and source bounds.

Errors have finite classes for format, limit, pin, and binding failures.
All supplied roster keys must be exact integers from zero through 2^64−1.
The reader checks these keys before roster comparison or function lookup.
It checks the selected `Function.entry` with the same rule before comparison.
Boolean, float, negative, and overflowing identities cause a format error.
Listing-edge callers use the same integer rule before the edge count comparison.
The optional `None` caller remains valid. This check does not certify edge semantics.
Valid but mismatched identities remain binding errors.
Messages do not include caller data or process logs. The reader does not
convert unexpected implementation exceptions into successful observations.

## Alternatives and trade-offs

Changing schema 1 would make existing consumers accept a different meaning.
Removing dead operations or changing their flags would destroy observations.
Sorting storage or predecessor keys would destroy identity and phi slot order.
These alternatives are rejected.

Separate immutable schema 2 records require more types and explicit consumer
selection. They preserve the old contracts and make the observation scope
visible. Mutable JSON-only results would permit changes after parsing.
Frozen records prevent such ordinary mutation. They remain supplied data,
not certificates.

## Evidence and remaining gates

The baseline is the four final public design records in the approved
`2026-11-13-pause/byte-adapter-design` checkpoint. Primary sources are pinned
to Ghidra revision `8ca9077040cc43cd790babcfccf19475622a3e9a`.
`HighFunction.java` separates function identity from block cover extrema.
`PcodeSyntaxTree.java` assigns block slots and operation order during decode.
`PcodeOpBank.java` preserves the complete ordered Java operation bank.
`PcodeOpAST.java` and `PcodeBlockBasic.java` explain the retained dead flag.
`PcodeBlock.java` exposes reciprocal edge slots. `VarnodeAST.java` exposes
local identities and independent flags. Native `block.cc` distinguishes the
entry block, cover minimum, and native entry address.

Tests use independent literal records written before the reader. Further
controls cover the approved Unit A matrix, malformed records, exact and
one-over bounds, coherent fabricated records, and Hypothesis mutations and
round trips. The unchanged old readers must reject schema 2. Their unchanged
tests remain part of the verification gate.

Unit B, a producer, a selector, a semantic checker, and an emitter are not
implemented here. Producer admission and production remain HOLD. The full
capture review remains OPEN after provider screening. This work does not
retry or replace that review.

The root must obtain independent review and run the full repository hook.
Native inventories, entry relations, raw effects, source grammar, callable
interfaces, pointer proofs, active emission, and Linux controls remain open.
Phoenix must still complete M4, publish the required T0–T3 comparisons and
artifacts, and reproduce every headline with `phoenix-eval --replay`.
No SPEC section 9 completion claim follows from this reader.
