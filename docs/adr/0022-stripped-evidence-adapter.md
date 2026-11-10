# ADR0022: Opt-in stripped-binary evidence

Date: 2026-11-10
Status: Candidate for independent review

U1 implements the completed Astra design in
`/Volumes/PhoenixWork/audit/m2-production-design-astra/`. It adds a separate evidence path.
The normal pipeline and `Program.Function.entry` retain Ghidra addresses.

`lift.mapping` owns the source mapping and a complete-artifact commit record.
`lift.index` owns the bounded immutable static index. `recover.addresses`
owns ELF program headers and address proofs. `recover.imports` owns bounded
dynamic import validation. `recover.plan` produces a static plan candidate.
The candidate cannot execute a target.

The installed source-info API was checked by the supplied public probe.
Its source hashes remain in the design audit. The production exporter must
also compile and run against the locked installation. Source-info offsets
and `FileBytes.getFileOffset()` establish file positions. Image base alone
does not establish file positions. Changed memory spans remain unavailable
byte evidence. Only unchanged executable spans can witness instructions.

Mapping publication uses three files. A commit record binds the exact
completed lift and mapping bytes. Readers require all three files and check
both digests. A failed or partial publication cannot enter new recovery.
The lift digest is outside the hashed lift object.

Import identity requires both a Ghidra call/thunk path and an ELF relocation
at a referenced GOT slot. Version identity is retained. DT_NEEDED order does
not establish provider ownership. Unsupported sites retain explicit gaps.

The implementation task limited the writer to one worker and static checks.
The parent owns commits and independent reviews. Linux fixture builds and
later live gates remain with the parent. This unit does not claim M2 or section 9 completion.

The source-info API names are `MemoryBlockSourceInfo.getFileBytes()`,
`getFileBytesOffset(Address)`, `getMinAddress()`, `getMaxAddress()`, and
`getLength()`. `FileBytes` is in `ghidra.program.database.mem`.
`FileBytes.getFileOffset()` gives the source file base offset. The initial
profile requires one complete FileBytes source with base offset zero.
Its original-byte hash must equal the input binary hash. Partial source
objects and byte-mapped source spans are unsupported.

The supplied source hashes are
`a9eda47bf9befab3c3b19b9e228abcd476d8ce0ea4f4c368f7b76575e188f4ba`
for MemoryBlockSourceInfo and
`8d42c261b55979d7733b0e5e78547e3261c07dd59eb1ba02bf70ee13e05c9dc5`
for FileBytes. This unit checks installed declarations with `javap` and
compiles and runs the exporter against Ghidra 12.2. It does not open a source
archive. Ghidra stays at commit
`8ca9077040cc43cd790babcfccf19475622a3e9a`.

No upstream implementation is copied. The Ghidra and Gson Apache-2.0
notices in `THIRD_PARTY_NOTICES` remain required. ADR0005 and ADR0019
retain their provenance role. The newer U1 rule keeps target and label
arrays separate even when their lengths match. It supersedes ADR0019's
permission to pair equal-length arrays.

`recover.plan` is the minimal candidate module. It is not `observe.plan`
because U1 provides no observer or executable wire plan. Unsupported raw
transfer forms and missing instruction bodies retain gaps. The existing
Ghidra synthetic external thunk entries remain Ghidra metadata. They do
not become original instruction witnesses.
