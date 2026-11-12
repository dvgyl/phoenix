# ADR 0037. Render and decode complete typed collector data

Date: 2026-11-12
Status: Implemented as a pure unit. Independent review remains open.

Phoenix needs a complete typed header for the later native collector.
The approved Astra design requires one retained directory for all tables.
A header hash cannot prove that a linker retained those tables.

`collector_header.py` validates and renders `CollectorData`.
`collector_header_read.py` independently decodes the generated syntax.
`native/collector_data_v1.h` fixes all native declarations.
The C data schema remains `phoenix-eager-c-data-1`.
This is its first representation in this worktree. A later shape change
must have an explicit schema identity before production use.

The fixed schema has 47 tables. Table tags are their fixed positions,
starting at one. The first table contains `uint8_t` data. The other tables
have fixed record types. Each nested record has its own native declaration.
Pairs and scalar array members also have fixed table types.
Strings use strict UTF-8 bytes with explicit lengths. Witnesses use their
original bytes. No input text becomes a quoted C string or an identifier.
The header contains no JSON object, generated function, or executable logic.

Each table slice has a `uint32_t` offset and count. Addresses and other
unsigned values use `uint64_t`. Source constants use fixed-width hexadecimal
`UINT64_C` tokens. Byte constants have two lowercase hexadecimal digits.
Options have numeric zero and one tags. Variants have fixed numeric tags
and separate typed payload slices. Inactive payloads are zero.
A signed dynamic tag has a sign tag and an unsigned magnitude.
This represents `INT64_MIN` without an overflowing C expression.

Geometry uses start and size fields. The reader restores the exact exclusive
end. An end of `2**64` is supported when the size fits in `uint64_t`.
A size of `2**64` is not representable. The renderer explicitly refuses it.
For example, a load envelope from zero to `2**64` is unsupported.
The renderer does not wrap that size or replace the envelope with segments.
This conservative representation limit does not change `CollectorData`.

The exported `const` directory is `phoenix_collector_data_v1`.
Its fixed type contains the logical data identity, renderer source identity,
native declaration identity, and an entry for every table.
Each entry contains its fixed tag, logical count, logical element length,
logical table length, physical element length, physical storage length,
and table address. Physical lengths use fixed `sizeof` expressions.
The native declarations contain the fixed visibility, `used`, and `retain`
annotations. An empty table has one zero storage element and logical count
zero. The reader never returns an invented logical record for that element.

The supported native profile has 64-bit pointers. A fixed C assertion checks
that condition. Logical constant storage includes all table fields and the
complete directory. It excludes empty-table storage elements and padding.
The directory contributes 96 identity bytes and 56 bytes for each table.
The renderer never hashes a C memory image or padding.

`HeaderLimits` permits at most 64 MiB of generated source and 32 MiB of
logical constant storage. Lower caller limits remain binding. Boolean,
float, nonpositive, and raised limits are invalid. The renderer checks each
row reservation, index bound, UTF-8 byte count, and exact source length
before it allocates the corresponding tables or source. Fixed native
source reads have a 2 MiB bound. Each fixed Python renderer source read
also has a 2 MiB bound.

The renderer rejects unknown record types, changed fields, unknown variants,
invalid literals, mutable array members, and invalid exact scalar types.
It checks canonical plan and scope identities and their internal links.
It checks the installed policy identity, complete gaps, request evidence,
register order, limits, ELF geometry, route bindings, and route memberships.
The internal checks also compare continuation users, disposition route IDs,
omission metadata, and guard roles with their complete source records.
Neutral thunk limits remain binding. Route membership construction makes
one pass over the retained path positions. It does not form a cross-product.
These checks establish internal data consistency. Raw reconstruction still
belongs to `prepare_collector_data` and the later production boundary.

The renderer source identity hashes a canonical manifest for two fixed
relative names. Each entry has the actual byte length and SHA-256 digest.
The names are `phoenix/observe/collector_header.py` and
`phoenix/observe/collector_header_read.py`. The native declaration identity
is the SHA-256 digest of the actual fixed header bytes. No caller supplies
these identities. Neither source identity depends on generated output.
The generated header contains no header, plugin, receipt, or runtime hash.
`GeneratedHeader.sha256` hashes the exact returned source bytes externally.

The reader accepts only the fixed include, table order, types, identifiers,
initializer grammar, directory type, fields, references, and final LF.
It validates every directory entry. It rejects missing or extra tables,
unknown tokens, integer overflow, invalid tags, invalid UTF-8, invalid slices,
noncanonical storage reuse, unreferenced rows, and trailing source.
Each slice checks the offset first. Its count must fit in the remaining
table length. The reader reconstructs a complete immutable `FrozenRecord`.
It checks the complete logical digest with the retained lower data bound.
It does not import the writer or use the writer's table construction.
Tests compare this result with `CollectorData.record()` and its independent
conversion to the canonical logical record.

No constructor, digest, header, or source parser grants runtime authority.
The native installer and independent compiled-data reader remain later units.
Actual plugin inspection must bind the complete decoded tables to the plugin
bytes and trusted build receipt. Source parsing and syntax-only checks do
not establish linker retention. Build issuance, source closure, cache rules,
native collection, calibration, and production admission remain open.
The full capture review remains OPEN after provider screening.
This unit does not retry or certify that review. Production remains HOLD.
