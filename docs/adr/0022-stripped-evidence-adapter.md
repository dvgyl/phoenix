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

Opt-in publication writes `lift.json`, `mapping.json`,
`evidence-commit.json`, and `ghidra.log` in a new generation directory.
The commit record binds the exact lift and mapping bytes. The log is
diagnostic. The lift digest is outside the hashed lift object.

Call `read_companion(output.parent, binary_bytes)` to read the current
opt-in generation. The reader reads `evidence-current` once. It requires a regular file,
limits the byte count, and opens without following a symbolic link. This file
contains one directory name in the form `generation-<32 lowercase hex
digits>` followed by a newline. The reader checks the files, commit
digests, binary identity, and lift structure in that directory. The opt-in
launcher returns the selected generation's own lift path. Use that path to
keep a specific generation after a refresh.

The publisher validates a complete generation before it replaces
`evidence-current` atomically. A failure before replacement leaves the
previous selection readable. The publisher keeps earlier generations and
can leave a complete unselected generation if selector replacement fails.
This contract covers process failures and concurrent refreshes. Power-loss
durability and automatic deletion of generations are outside its scope.

Saved flat U1 exports remain archived in their original layout. The
production reader requires a selector. To check a saved flat export with
the new reader, first verify its archived commit and public binary hashes.
Then publish copies of the saved lift and mapping bytes in a separate
directory. Keep the saved files and their hashes intact. The default
launcher continues to write one lift file at the requested path.

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

A failed validation retains the bounded Ghidra diagnostic in the error.
It does not change the prior selection or its diagnostic file. A resolved
call edge must agree with the raw transfer operation at its exact site.
An instruction witness for a different target does not prove the edge.
