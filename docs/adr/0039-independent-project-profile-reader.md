# ADR 0039. Independent project profile reader

Date 2026-11-12. Status proposed for independent review.

Phoenix needs verified completion through SPEC.md section 9. P1 supplies one
prerequisite. It adds a pure reader for `phoenix-project-v2`. It does not
complete a milestone or permit production selection.

## Scope and authority

Only `phoenix_eval/project_profile.py` and its public host tests implement P1.
No existing implementation, schema, pin, CLI, or evaluator caller changes.
The module imports only Python standard library modules. It does not import
`phoenix`. Its public operations receive bytes or immutable records. They
perform no filesystem, environment, subprocess, clock, provider, or Phoenix
operation.

`ParsedProjectV2` contains consistency data. Its constructor does not grant
authority. It has no integrity status, build receipt, or submission result.
No source contents or trusted original-function inventory are supplied to P1.
Manifest and correspondence original and origin digests must agree. That
agreement does not authenticate either digest.

The selected design requires exact supplied canonical CMake. The producer and
the evaluated package must retain the same file. The renderer freezes the
inspected old `PROJECT_CMAKE` bytes as literal v2 policy data. It replaces only
the single executable line with the sorted multi-line source stanza. A future
change to the legacy constant cannot change this renderer. Tests retain an
independently authored full golden build file.

## Complete immutable records

All records are frozen slotted dataclasses. Arrays become tuples. Canonical
inputs remain the exact supplied bytes. Strings and integers remain scalar
values. The complete records are `FileRow`, `CorrespondenceFileRow`,
`ProjectManifestV2`, `Span`, `Anchor`, `FunctionRow`, `GlobalRow`,
`SharedTypeRow`, `CorrespondenceV1`, and `ParsedProjectV2`.

Every wire field is retained. This includes schema and profile literals,
original and origin hashes, all file rows, correspondence binding, CMake
hash, address space, declaration version, function entries and linkage,
all span hashes, complete anchors, optional type definitions, declarations,
users, and proposal claims. P1 does not replace the map with a summary.

The renderer parses both retained canonical inputs again. It compares the
complete record tree with those parsed records. Comparison requires exact
record and scalar types, exact tuple lengths, and exact values. It does not
serialize an untrusted direct object. Direct construction, subclassing, or
forced mutation cannot introduce a path into the fixed CMake grammar.

## Raw parsing and limits

A raw byte scanner precedes JSON tree allocation for both files. It bounds
container depth, decimal tokens, strings, arrays, span occurrences, and
reference edges. It detects duplicate keys. It rejects metadata escapes,
non-ASCII metadata, floats, nonfinite values, negative zero, extra whitespace,
and invalid JSON syntax. Complete field checks and canonical byte comparison
follow decoding. Canonical JSON has sorted keys, compact separators, ASCII
metadata, and one final LF. All supported metadata grammars exclude characters
that require JSON escapes. Source bytes are never decoded or re-encoded.

`ProfileLimits` contains all P1 resource maxima from the approved API.
Only an exact `ProfileLimits` record with positive exact integer values is
accepted. Boolean values, floats, other types, and raised limits fail before
raw parsing. Caller reductions apply to every field. String reductions for
source paths, identifiers, and evidence IDs also apply before JSON decoding.
The fixed correspondence filename is not a source path.

| Resource | Maximum |
| --- | ---: |
| C sources | 64 |
| Headers | 128 |
| Declared C and header bytes plus derived CMake | 4,194,304 |
| Derived or supplied CMake bytes | 16,384 |
| Manifest bytes | 262,144 |
| Correspondence bytes | 1,048,576 |
| Source path bytes | 58 |
| Container levels | 16 |
| Decimal integer digits | 20 |
| Functions | 8,192 |
| Globals | 8,192 |
| Shared types | 4,096 |
| Serialized span occurrences | 32,768 |
| C identifier bytes | 128 |
| Evidence record ID bytes | 128 |
| Reference edges across both inputs | 65,536 |

Counts are checked before record or lookup-index construction. Declared
file-size sums include the exact derived CMake length. These sums are checked
before hashing or rendering. P1 cannot check actual source file sizes.
Future byte admission must check actual bytes. Limits constrain bytes,
tokens, records, and edges. They do not claim an exact Python memory bound.

The API does not define every edge-count contribution. This implementation
uses a conservative structural definition. Count one edge for each serialized
`path` field, including file rows and the fixed correspondence filename.
Count one for each function `origin_entry`. Count two for each complete
anchor, for its artifact and record references. Count one for each
`shared_type_ids` element and each `users` element. All span path occurrences
therefore count. Repeated definition and declaration spans count separately.
Original, origin, content, and declaration-version digests are identity
bindings, not additional graph edges. Add the two input counts before JSON
decoding. Do not deduplicate these counts.

A span occurrence is each serialized non-null definition, signature, body,
or declaration span. A type definition repeated in its declarations counts
twice. Null definitions count zero. This definition also applies to caller
reductions. The scanner charges malformed extra structures conservatively.
They cannot produce a parsed project.

Some maxima constrain the same input. For example, the correspondence byte
limit can prevent a complete valid fixture from reaching the function limit.
The fixed source count and path grammar keep derived CMake below its hard
byte cap. Tests check valid fixtures at reduced inclusive limits. Separate
raw controls check hard token, array, nesting, and byte limits. A malformed
raw control is not a valid-project acceptance result.

## Consistency rules and limits of interpretation

Paths and identifiers use full-string matches of the approved ASCII grammars.
Arrays must be sorted and unique. Lowercase paths make ASCII case aliases
impossible in an accepted roster. Invalid aliases are rejected without
normalization. Digests have exactly 64 lowercase hexadecimal digits.

Functions sort by numeric canonical 64-bit Ghidra RAM entry. Entries and
function keys are unique. External definition names are unique across both
functions and globals. Exactly one function is the external `main`. Internal
function names can repeat in different C files. Function ranges must have
matching outer endpoints, ordered nonoverlapping signature and body spans,
and a listed C file. Distinct function definitions cannot overlap.

Every span is a positive half-open byte range within its declared file size.
This arithmetic cannot prove token boundaries, braces, a real function,
correct abstract syntax tree association, or correct original association.
Later compiler and origin adapters must supply that evidence.

Global and shared-type IDs use the exact approved domain label, one actual
NUL byte, and canonical original-plus-complete-anchor bytes. Declaration
version hashes use canonical complete manifest header rows. Shared type
references must resolve. Each user path must name a listed C file. Shared
types need a header declaration. A present definition must be a declaration.
A typedef requires a definition. Distinct type IDs cannot own the same
`(path, start, end)` definition, even if their claimed span hashes differ.
Same-layout types with different anchors keep distinct nominal identities.

An external global needs one C definition and at least one header declaration.
An internal global can have no separate declarations. P1 does not prove C
linkage, declaration compatibility, layout, storage, or anchor truth.

The approved wire does not require nonempty type users or equality between
users and explicit function/global references. P1 checks resolution and
listed C paths only. Empty users and additional listed users remain
consistency data. The later actual compiler gate must verify the complete
user set. It must not remove an obligation because a producer omitted a
user. This is an explicit architectural limit, not a recovery claim.

## Error boundaries

P1 emits only the applicable finite categories from the approved taxonomy.
Failures use selection, parse, roster, content, or correspondence phases.
Details contain fixed text with at most 160 characters. Limit or parse failure
returns no partial record and no integrity success.

Missing limit fields are rejected before parsing. A missing record field is
not equivalent to a present null field. Direct-object comparison requires
every field to exist.

Expected errors are converted at their actual boundaries. The JSON decoder
converts `JSONDecodeError` only. Hash calls have no broad error handler.
Programming errors, including `ValueError` from a hash implementation, remain
visible. This structure retains the lesson from the reviewed byte-source F1
correction. A programming failure must not become a successful negative
input control.

## Accepted design process exception

The designer created four new reports outside its assigned audit directory.
The supervisor verified their creation and exact hashes, preserved the
originals, copied them to the authorized dated directory, read all four,
and accepted bounded P1 content. Preserve that exception. This unit uses only
those authorized copies and `output-scope-exception.json` from
`/Volumes/PhoenixWork/audit/m3-project-profile-design-astra-20261112`.

| Authorized design copy | SHA-256 |
| --- | --- |
| `design.md` | `da60f1152fa2790c69b770e72d4857ac1d4d1cd7cc4f57a52051db4317c9d383` |
| `api.md` | `700fcce6504990ac32663734a2618b89787ceb7274a447b208d294f3e7aca1e6` |
| `implementation-plan.md` | `dbd5793b61228075d09dca8437d6d081d044211b52d5dc9d302e046ed2e41610` |
| `report.md` | `436417b8ace597713cfdf0a862a9344e7abd2247059be02413e04c8a0496b3e9` |

The design plan names absent `phoenix.diff` and `phoenix.sandbox` coverage
packages. Actual comparison and isolation code belongs to `phoenix_eval`.
Use current `scripts/check` and `docs/QUESTIONS.md`. No duplicate package is
added. The supervisor owns the full mandatory gate and fresh independent
Sol and Astra reviews. This worker makes no Git metadata changes.

P2 through P9, actual source-byte admission, descriptor and archive safety,
publication, policy pins, origin inventory, native compiler receipts and
launchers, compiler integrity, capture, replay, the pipeline, and the module
producer remain outside P1. VM and live checks require the private Author's
release. M2 through M4, publication, baselines, ablations, costs, failure
reports, and exact headline replay remain necessary for SPEC.md section 9.


## Artifact collection error

The worker's checksum collector used an unrestricted audit-directory scan.
It included an events.jsonl file that the worker did not create. It read
that file's bytes to compute digests. Two checksum-generation passes and
the failed checksum-verification pass performed those reads. This violated the task's event-file
read limit. No event contents were printed or used for implementation.
The correction uses an explicit list of files created by this worker.
The event file is excluded from every further read and current checksum
collection. The failed checksum check and the earlier candidate evidence
remain preserved. This error is separate from the supervisor-accepted
design output-scope exception. No supervisor acceptance of this error is
claimed.
