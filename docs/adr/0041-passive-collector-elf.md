# ADR0041. Read the collector ELF as passive bytes

Date: 2026-11-12.

Status: U1 implementation. Synthetic validation only. Independent review is
OPEN. Both Linux layout profiles remain test-only.

## Purpose and scope

Phoenix needs independent inspection of retained collector data under corrected
F3. U1 supplies a bounded ELF view. It does not supply complete logical readback,
a compiler witness comparison, or trusted build issuance. SPEC section 9 remains
open. Full capture review remains OPEN after provider screening.

The accepted design is in
`/Volumes/PhoenixWork/audit/m2-compiled-data-design-astra-20261112/`.
Its four inputs have these SHA-256 identities.

| File | SHA-256 |
| --- | --- |
| `design.md` | `08ce7356c8a54a45b5979db7ced54e08738990fcb00475cdecf8fb87a2cb9bb1` |
| `api.md` | `9b5bad121821fcadd51de2c39035e1a7c0734ee82edd19382389c60aada3571b` |
| `implementation-plan.md` | `53a3b9e08cd394785d072a602dee676b18ef1b4ccf61956b9cce4d43389833b4` |
| `report.md` | `2c1fac897c206f4894c24ef29039075cc95b523aa7c76bfd70c254d0c414af5a` |

The implementation base is `d736ef8728d474cf3bb7d050bb0a1d173f54a034`.
The principal assigned ADR0041 because ADR0038 already exists. This filename
change does not expand the unit.

## Interface and records

`read_collector_elf(raw, *, machine, limits)` accepts exact immutable bytes,
machine 62 or 183, and an exact `InspectionLimits` record. It checks every limit
on every call. Missing fields, Boolean values, float values, raised values, and
record subclasses refuse. A fresh limit snapshot preserves caller reductions.

Success returns a frozen `CollectorElf`. Failure returns one frozen
`InspectionRejected`, with a fixed bounded detail and no partial view. Only the
private format-refusal exception is converted. Programming exceptions remain
visible. The only local `AttributeError` conversion checks missing limit fields.

Records keep input index order. File offsets and ELF virtual addresses have
separate types. The view retains the exact input bytes. It also retains the ELF
header fields and all program headers, including non-load program headers and
physical addresses. These additional observations prevent record loss. They do
not grant authority. All exported record constructors are ordinary data
constructors. No consumer may treat a constructed record as an approved build.

The product module imports only the Python standard library. It does not import
the renderer, source reader, ingest module, native declarations, or reconstruction
code. It performs no filesystem, network, process, environment, clock, native
loading, or provider operation.

## Structural contract

The reader requires little-endian ELF64 ET_DYN with ordinary section numbering.
It requires unstripped static and dynamic symbol tables. Header sizes, entry
sizes, alignment, integer ranges, file extents, section links, and consumed
mappings are checked before access. No allocation uses `p_memsz`.

Positive-length load file ranges and virtual ranges must be disjoint. Ordinary
section file ranges and ELF metadata tables must also be disjoint. Allocated
section virtual ranges cannot overlap. Consumed objects must be complete,
file-backed PROGBITS objects. TLS, compressed data, BSS, file holes, and executable
data mappings refuse.

The reader requires SysV hashing and immediate binding. It checks the complete
bucket and chain structure, symbol reachability, bucket membership, and cycles.
Each fixed export must have one dynamic row and one matching static row. Required
exports have the installed binding, type, visibility, size, and version contract.
`qemu_plugin_version` contains the signed little-endian value 4. Its object may be
ordinary writable data, but no relocation may touch it. The installer has
nonempty executable file-backed storage. The reader never calls it.

The version-index array, when present, must match DT_VERSYM and the dynamic symbol
count. Required exports have version index 1 with no hidden bit. Other version
metadata, imports, dependencies, and permitted remaining dynamic tags remain
bounded evidence. This unit does not resolve dependency versions or approve an
installed dependency context. RPATH, RUNPATH, unsupported relocation encodings,
and text relocations refuse.

Allocated RELA sections must match complete DT_RELA and DT_JMPREL ranges.
DT_RELACOUNT must describe a leading relative run. All accepted writes have
width eight and a checked writable, non-executable, file-backed destination.
Only relative, GLOB_DAT, and JUMP_SLOT kinds are accepted. Their numbers are
explicit for each machine. IFUNC, COPY, TLS, unknown widths, duplicate writes,
and writes into protected objects or ELF metadata refuse.

The 47 fixed table names and element sizes are explicit. All directory tags,
dimensions, storage extents, local symbols, and relative pointer cells are
checked. Empty tables retain one zero physical element. Table objects cannot
share storage. The root table has one physical row. These are physical checks.
U1 does not decode the root's logical fields or compare D, R, N, or witness words.

A pointer cell must have exactly one machine-specific relative relocation with
symbol index zero. Its nonnegative addend must equal the corresponding local
symbol's virtual address. The original pointer word is not a fallback. Changing
that word can leave the passive interpretation unchanged while changing the
input identity. A later issued receipt must bind the exact input bytes.

## Page granules and the compatibility HOLD

The accepted design requires that page rounding not create a writable alias.
It permits a writable directory only with complete GNU RELRO protection. The
design does not define a kernel page-size parameter or an approved granule set.
This task has no network or Linux access. No pinned kernel or dynamic-loader
source was read. The rules below are explicit test assumptions, not observed
Linux behavior.

| Choice | Consequence | Decision |
| --- | --- | --- |
| Reject all rounded writable aliases, including RELRO prefixes | Conservative rejection does not need to infer final protection. It rejects a useful protected-prefix case. An arbitrary granule set still needs a bound. | Do not use this as the sole rule. Keep it as the fallback if RELRO semantics cannot be approved. |
| Install one explicit granule per build context | This can accept ordinary output for a known host. It needs an approved context field and pinned loader evidence. The current API has neither. | HOLD for a separate contract decision. Do not infer it from `p_align` or the current host. |
| Check every member of an installed candidate set | Acceptance requires all candidate checks to pass. This can reject output that would work for one member. | Use the fixed test-only set 4096, 16384, and 65536 for both machines. Production applicability remains HOLD. |

For each candidate granule, every load must have congruent file and virtual
addresses. A rounded mapping must not substitute different file bytes or
anonymous zero fill for a consumed section. A rounded executable mapping cannot
cover data. These checks also apply to read-only mappings.

For each read-only consumed object, inspect both virtual overlap and file-byte
aliases through every writable load. A file alias is translated into the
writable load's virtual-address domain. For the test model, RELRO protection is
`[floor(relro_start / g) * g, floor(relro_end / g) * g)` for granule `g`.
Every overlapping byte must be inside that interval. Immediate binding is
mandatory. Checking only the exact RELRO start would miss protected prefixes.
Rounding the RELRO end upward would invent protection.

Synthetic controls include a writable load prefix that aliases read-only table
bytes. Complete RELRO protection permits it. A shortened RELRO end refuses it.
Another control uses disjoint exact loads whose rounded mappings substitute
different file bytes. It refuses before table interpretation.

This candidate set is not an assertion that all Linux granules or loader rules
have been validated. U4 must pin the kernel and loader evidence, establish the
applicable granules, and test actual outputs. A common 4 KiB-only output can fail
this conservative three-granule check. Do not change the future recipe or weaken
the parser silently to make that output pass. Review the contract first. A pure
parser success cannot activate either native profile.

## Bounds and validation

All schema caps are installed constants. Every positive caller reduction remains
binding. Logical-output, nesting, and inspection-record limits are retained for
U2. U1 does not emit those records or consume those budgets.

The reader uses memory views and builds one NUL index per string table. It charges
byte scans and name copies before work. Symbol counts and hash dimensions are
checked before dependent allocation. Load lookup uses a sorted address index.
Symbol lookup uses name indexes. Relocation lookup uses a destination map.
Protected ranges use sorted interval checks. There is no relocation-by-table-row
comparison.

The limits bound bytes and record counts. They do not establish a total Python
memory bound. U4 still needs measured resource use and the separate process
memory limit. U2 must account for the complete inspection's work when it combines
ELF reading with semantic decoding.

Tests build literal synthetic ELF images without the product reader as a
serializer or expected oracle. They cover both machines, all 47 pointers,
imports, complete dynamic RELA metadata, hash collisions, versions, exact limits,
aliases, empty storage, stale pointer words, integer endpoints, arbitrary bounded
bytes, and structure-preserving mutations. Programming-fault injection checks
that unexpected exceptions remain visible.

No compiler, container, target, or real provider was used. No actual Linux
compiler output was validated. A coherent fabricated ELF can pass U1. That result
cannot satisfy trusted build issuance, actual table use, or SPEC section 9.

## Remaining gates

The principal must run the full quality gate and obtain fresh independent source
review before U2 relies on this module. U2 must independently decode every logical
field and compare complete canonical records. U3 must provide the fixed witness
and assertions. U4 must validate actual native Linux compiler outputs and the
page-granule contract. U5 must bind fresh inspection to trusted issuance and prove
that the native collector uses these exact arrays.

Full capture review, calibration, deployment, recovery, localization, milestone
acceptance, M4 publication, and replay remain separate gates.
