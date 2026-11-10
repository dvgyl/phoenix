# Bounded static lift evidence

Phoenix M2 needs storage and indirect-flow evidence without changing the
current recovery path. Add an optional `static_evidence` object to each
lift function. Keep the outer `schema_version` at 1. Give the new object
its own `schema_version` of 1 and a fixed `status` of `proposal`.

`recover()` rejects outer version 2. It reads the existing signature,
p-code, ranges, and edges. The independent integrity shape reader reads
the recovered `Program`, not the new record. A separate evidence version
preserves these callers without a pipeline change. Old exports remain
valid. An older copy of the strict JSON Schema will reject the new field.
Use the updated schema to validate new exports.

Keep `listing` and `decompiler` prototypes separate. Each has its own
source, convention name, parameter slots, and result slot. Preserve
custom listing storage. The decompiler API does not expose that flag,
so its value is null. A missing HighFunction gives a null decompiler
prototype and no jump tables. This is unavailable evidence, not proof
that no indirect transfer exists.

Store each VariableStorage piece in API order. Keep its address, byte
size, register reference, and signed stack offset. Stack offsets use
Ghidra's stack-space base. Do not infer a runtime stack pointer. Preserve
bad, unassigned, unknown, void, compound, automatic, and forced-indirect
storage. Keep unresolved register names null. The register table contains
used storage registers and their base registers. It is not a complete
language register table.

Validate the occupied byte intervals. Pieces in one storage record must
not overlap. A span must not wrap its 64-bit address encoding. A stack
span must also stay within the signed 64-bit range and must not cross
offset zero. A negative span can end at byte -1. For the supported
x86-64 little-endian contract, every compound piece after the first
must resolve to a register. Preserve the valid API order.

Check each register's address against its base and least-bit offset.
The byte displacement is `least_bit // 8`. The occupied byte span includes
the residual `least_bit % 8` bits. The full bit range must fit inside
the base register. Shared-address aliases remain valid. A storage piece
can be smaller than its referenced register, as the pinned lookup permits.
These checks validate metadata. They do not infer a calling convention.

Use a flat type table with local IDs in first-encounter order. Retain
paths, names, byte sizes, and pointer, typedef, or array references.
A size of -1 is unknown. Composite members and function signatures stay
opaque. This table does not recover signedness or structure layouts.
Pointer recursion uses explicit IDs. Never expand a DataType object tree.

Use HighFunction's JumpTable records. Preserve switch sites, targets,
and labels in API order. Repeated targets are valid. Ghidra returns
signed Java Integer labels. Keep the two arrays separate because labels
can be absent. Pair them only when their lengths match. Null sites and
targets remain unresolved. These proposals do not establish exhaustive
target sets, executed branches, or verified C types.

The exporter and reader limit each function to 128 parameters per
prototype, 32 storage pieces per slot, 256 types, 32 type nodes per path,
512 registers, and 256 jump tables. Each table has at most 4,096 targets
and 4,096 labels. Their combined function total is at most 16,384 items.
Storage has at most 8,192 bytes. Registers have at most 65,536 bits.
Evidence text has at most 1,024 characters. Exceeding a limit fails the
export or read. It does not publish a truncated record. The optional
file reader also limits input to 64 MiB and 65,536 functions.

`phoenix.lift.evidence` uses immutable typed records. Its boundary checks
reject duplicate JSON keys and identities, invalid widths, broken local
references, invalid recursive types, excess limits, and foreign jump
sites. Legacy functions return `evidence=None`. For new evidence, the reader
also retains the existing decompilation status. A timeout does not become
a successful decompilation because a prototype is present. Recovery does not consume
the proposals. Raw and analyzed p-code retain their separate domains.

The existing launcher gives each invocation fresh settings, cache, and
Java home directories. Pinned source confirms that script classes use
`<settings>/osgi/compiled-bundles/<sourceDirHash>`. Keep that isolation.
The optional `max_heap_mib` argument bounds the Java heap, including
launcher helper processes. Public checks use 384 MiB. Existing callers
retain the launcher's memory default. Clear inherited JVM option overrides
in the child environment to protect the isolated directory settings.

API reuse follows ADR 0005 and the existing Ghidra attribution records.
Ghidra is an NSA project under Apache-2.0. No upstream implementation or
new dependency is included. The installed source files below were read
and compared with commit `8ca9077040cc43cd790babcfccf19475622a3e9a`.

- [FunctionPrototype](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/pcode/FunctionPrototype.java) supplies parameters and return storage.
- [HighFunction](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/pcode/HighFunction.java) supplies prototypes and jump tables.
- [JumpTable](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/pcode/JumpTable.java) supplies switch sites, target arrays, and label arrays.
- [VariableStorage](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/listing/VariableStorage.java) supplies pieces and storage states.
- [Register](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/lang/Register.java) supplies names, widths, and base-register relations.
- [ApplicationUtilities](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/Utility/src/main/java/utility/application/ApplicationUtilities.java) defines settings and cache overrides.
- [BundleHost](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Features/Base/src/main/java/ghidra/app/plugin/core/osgi/BundleHost.java) locates the OSGi cache below settings.
- [GhidraSourceBundle](https://github.com/NationalSecurityAgency/ghidra/blob/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Features/Base/src/main/java/ghidra/app/plugin/core/osgi/GhidraSourceBundle.java) locates compiled script classes below settings.

ADR 0017 was the highest existing number. ADR 0018 is reserved for the
separate trace prototype. This task uses 0019. Task restrictions exclude
other agents, commits, target execution, and pipeline integration.
