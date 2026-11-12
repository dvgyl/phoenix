# ADR 0038. Structural byte-source observations

Date: 2026-11-12.
Status: Reader proposal. Production U5 remains open.

This unit adds the pure source reader from the approved Astra U5 design.
It changes no exporter, schema, existing reader, pipeline, or generated C.
Its data shape is `ByteSourceObservation`, with frozen `SourceToken` and
`SourceSpan` children. Keys and gaps use the byte-graph records. Symbol
storage uses the existing static `StoragePiece` record.

The wire uses schema 1. It has exactly the approved fields. JSON has sorted
keys, compact separators, ASCII escapes, and one final LF. Duplicate keys,
unknown fields, alternative encoding, floats used as integers, and Boolean
integer aliases reject. Addresses use minimal lowercase hexadecimal text.
The complete encoded bytes determine the observation digest. No digest
field refers to its own record.

The reader compares the function, binary, pass, lift, and raw C identities
with the supplied structural graph and ordinary lift. Raw C bytes use
strict UTF-8. The byte count and complete source digest must agree.
The supplied graph is an immutable structural proposal. It must come from
the graph reader. Neither this API nor a Python constructor authenticates
the producer or gives permission to emit C.

Tokens have contiguous ordinals from zero. Their positive byte spans are
ordered and do not overlap. Each span stays inside the exact source and
starts and ends on UTF-8 boundaries. Its digest binds the exact substring.
The reader preserves gaps between token spans. It does not infer missing
tokens or source semantics from whitespace, punctuation, or addresses.

An operation association names an ordinary analyzed operation in the graph.
The operation can be excluded dead evidence. Its presence does not prove
that a printer token actually belongs to that operation. Value and formal
associations are also proposals. The reader checks exact referenced IDs.
It does not infer arity, a C type, a pointer, a storage role, or availability
on a predecessor. Null associations remain null. Unknown nonempty token
kinds remain data for a later grammar to accept or refuse.

Every storage piece has the existing address, size, register, and signed
stack-offset fields. Spans cannot wrap. Stack offsets must match their
unsigned address representation. Stack pieces cannot cross zero. They have
no register label. Non-stack pieces cannot have a stack offset. These
checks preserve static proposal consistency. They do not establish a
callable interface or an object capacity.

Source gaps use the existing six finite byte-graph gap codes. Block, raw
or analyzed operation, and value references must resolve. A block paired
with an operation must own that active analyzed operation. Duplicate gaps
reject. A declared `unavailable` observation has no tokens and contains a
`source_unbound` gap. The exact ordinary source identity is still retained.

The default maxima are 16 MiB of wire bytes, 1 MiB of source bytes, 65,536
tokens, four storage pieces per token, and 256 gaps. Each limit can be
reduced. Nonpositive, raised, Boolean, float, and wrong record types reject.
Formal ordinals are at most 127. Token kinds have at most 128 UTF-8 bytes.
These are conservative first-profile limits. Nothing is truncated.
Wire size is checked before JSON parsing. Source character count is checked
before UTF-8 allocation. Encoded source size is checked before hashing.
The bounded JSON tree is created before token and gap count checks.

`exact_printer_bytes` is the producer's claim. The reader can check exact
bytes and references, but the old evidence cannot authenticate a complete
token inventory or its printer origin. A coherent empty token list can
pass. Tests preserve this limit. The producer review and later complete
source grammar must establish the additional correspondence. Parsing alone
cannot close that gate.

The source companion producer, retained pass record, pinned API compilation,
actual public export, recurrence and effect checks, complete-function
grammar, interface checker, emitter, protected definitions, and pipeline
option remain required. Independent Sol review and compiled public controls
remain required. The full capture review remains separate and open. This
unit supplies no live result, held-out score, or milestone acceptance.
