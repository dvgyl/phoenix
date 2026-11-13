# ADR0043. Install the independent candidate collector layout

Date: 2026-11-13.

Status: First U2 subunit. Synthetic layout checks only. Fresh independent
implementation review is required before a decoder uses this layout.

## Scope

Phoenix needs complete independent readback of compiled collector data.
This subunit installs the layout and semantic descriptors only. It does
not decode ELF, issue an inspection, approve Linux, collect a trace, or
close capture review. Both machine-specific definitions remain test-only.

The selected sequence comes from the final checkpoint design and the
independent Sol design review. Root accepted the restricted sequence.
The first subunit has only these product files.

- `phoenix/observe/collector_layout.py`.
- `tests/test_observe_collector_layout.py`.
- This ADR.

The writer, source reader, collector-data module, native declarations,
passive ELF reader, dependencies, recipes, and old identity algorithms
remain unchanged. There is no `collector_compiled.py` in this subunit.
There is no final `LayoutProfile` parser or serializer.

## Data and responsibilities

`LayoutDefinition` is a frozen private-stage record with immutable nested
records and tuples. It contains an explicit candidate machine, declaration
identity, types, members, tables, and private field specifications.
It has no witness-source, assertion-source, or reader-manifest digest.
Those source inputs are not available. No placeholder represents them.
A definition is not a complete final profile or an authority record.

The independent typed descriptors distinguish unsigned integers, Booleans,
fixed numbers, restored endpoints, signed pairs, text, digests, instruction
witnesses, literals, table slices, options, and variants. Table slices
retain their exact target and their array or single-record mode. Table
kinds distinguish storage, scalar rows, ordered pairs, and logical objects.
A future decoder must use a separate logical-object type. It must not
represent an object as an ordinary array tuple.

`TypeLayout`, `MemberLayout`, and `TableLayout` retain the final contract
fields. Each `TableLayout.fields` entry has only `logical_name`,
`native_name`, and `descriptor`. Private `FieldSpec` records also have a
native offset. This offset does not extend the final table wire shape.

The source inventory contains 214 fields, 100 native types, 653 expanded
members, and 47 tables. These are schema counts, not evaluation results.
Explicit candidate geometry supplies sizes, alignments, and field offsets.
No host ABI calculation, compiler, native packing, or writer helper supplies
an expected value.

Member expansion preserves composite members and their children. Child
offsets are relative to the owner type. Arrays remain one member with an
extent of 32 or 47. Validation checks the installed graph once per machine
at import. It checks exact identities and order, names, types, dimensions,
containment, disjoint siblings, leaf coverage, and cycles. Invalid installed
records raise programming errors. There is no mutable global call state.

`_definition` selects an installed definition. Its private exceptions are
not a new public refusal family. A later decoder must map profile input
errors to the existing U1 refusal types at its public input boundary.
`_expected_witness` derives 5021 unsigned words from the installed records.
The explicit little-endian test representation has 40168 bytes. Submitted
input cannot supply expected witness values. This module has no witness
comparison or byte-decoding entry point.

The module imports only the standard library. The observed product import
closure also includes `phoenix/__init__.py` and
`phoenix/observe/__init__.py`. Pure layout operations need no filesystem,
environment, process, clock, network, provider, or publication operation.

## Evidence and trade-offs

The normative inventory is the final checkpoint
`docs/checkpoints/2026-11-13-pause/compiled-data-design/design.md`.
Its SHA-256 is
`08ce7356c8a54a45b5979db7ced54e08738990fcb00475cdecf8fb87a2cb9bb1`.
The independently checked proposed-layout record has SHA-256
`2afb7057b427333e0c6caea163bb16c513d9432dd1fae57284edb13367f70868`.
The native declaration identity is
`2e278603d75d6cd436aedc72af3f1903334dadc37d6d8847dfd3dd825018acb3`.

The product inventory was transcribed from the normative document.
The test file retains bounded literal type, member, table, and field
expectations. The type/member/table literals can reproduce the exact
proposed-layout JSON identity. Tests need no external audit path.
They compare every record and every witness position. Direct offset and
type-code controls supplement those complete comparisons.

Typed expansion avoids a second 653-row product list. The tests retain
that full literal list to detect expansion and transcription errors.
The larger test file is intentional evidence within the approved scope.
The product module does not parse the design document at runtime.

These synthetic checks establish the installed candidate contract only.
They do not prove native layout, compiler retention, Linux compatibility,
process memory, or performance. A compiler version string proves none of
those properties.

## Future private readback and public-success gates

The next separately reviewed subunit can implement private `LogicalReadback`.
It must call the public U1 reader on exact immutable bytes. It must check
the complete witness, bind the directory, decode every field, enforce
slice ownership and exhaustion, and compare complete canonical bytes.
No decoder stub in this subunit claims that work.

Sol F1 remains a public-success gate. The final inspection needs explicit
`identity_inputs` for actual reader-manifest and final-profile bytes.
Root has not accepted a final signature amendment. Freeze actual source
bytes first. Produce their manifests outside those source files. Review
the schemas, bounds, source allowlists, and installed source association.
Never embed a source manifest's own digest in the source it hashes.

Sol F2 remains a public-success gate. One immutable metadata-evidence
transaction must retain the final inspection and both complete metadata
arrays from the same parse. Include null dynamic tail rows and accepted
relocations outside directory pointers. Preserve input order. A mutable
global, hidden callback, or second independent parse is not this transaction.
Root must freeze its interface. The arrays share the 64 MiB evidence cap.
They do not belong unbounded inside the 64 KiB inspection record.

Sol F3 requires one shared conservative work budget. U1 remains unchanged
at source SHA-256
`dae95a30f96c556a1731a59edada95e4622991889ffcfdfa576bf773a17929eb`.
The future decoder must preserve every caller reduction. Pass only the
remaining scan and scalar allowance to U1. After successful U1, debit its
conservative source-associated cost before witness work. Recheck this
association after any U1 accounting change. Conservative refusal is valid.
Do not give U1 and U2 separate full budgets.

For plugin bytes L, program count P, section count S, symbol count Y,
dynamic count D, relocation count R, hash-word count H, and version-cell
count V, the selected scalar debit is
`14 + 8*P + 10*S + 2*D + 6*Y + V + H + 3*R + 47*7`.
The scan debit is `2*L + 2*sum(section name lengths) +
3*sum(symbol name lengths) + 2*sum(needed name lengths) +
6*limits.symbol_name_bytes`. Derive counts from the accepted U1 view.
Charge later reads, scans, comparisons, hashes, appends, and copies to
that same budget before each operation.

Sol F4 fixes refusal order. Validate input types and limits, including
profile type and ID selection, first. The selected definition supplies
the machine. Then preserve the complete U1 refusal order. U1 already
checks physical directory data before the witness. U1 refusal must
therefore precede witness refusal. After successful U1, apply its debit,
check the witness, bind the directory independently, and decode. A zero
remaining allowance must return `work_limit` before calling U1 with an
invalid zero limit. Keep U1 bytes and failure categories exact.

Sol F5 requires limits before work. Read the fixed limit references
before large arrays. This preflight grants no slice ownership. Check
counts before tuple construction. Enforce plan and scope subtree byte
caps before each append during canonical emission. Reserve each final
LF. A final span-length check alone is insufficient. Charge preflight
reads, traversal reads, and output copies separately.

## Remaining gates

Root must run the full repository hook and obtain fresh independent Sol
implementation review before any decoder uses this layout. Public success
also needs F1 and F2 resolution and separate integration review. U3 must
supply the actual witness and assertion sources. U4 must validate actual
GCC and Clang output at O0 and O2 on both required native hosts.
Page-granule applicability, loader assumptions, resource measurements,
repeated build identity, and actual retained data remain unapproved.

U5 still needs trusted issuance, fresh cache inspection, complete native
table traversal, operational use of those same tables, complete source
and import closure, launch association, and per-trial calibration.
Full capture review remains OPEN after provider screening. This work
does not retry, replace, or bypass that review. No corpus score, runtime
authority, milestone acceptance, or SPEC section 9 completion follows.
