Phoenix needs independent inspection of every retained collector table under corrected F3. This design defines the next bounded units. It does not approve runtime admission or establish SPEC.md section 9 completion.

Select a fixed data-only layout witness plus installed Linux layout profiles. Treat the plugin as bytes. Never load it to inspect it. Implement the pure ELF reader first. Actual Linux compilation remains blocked until the separate VM lease ends.

The comparison of the supplied alternatives is as follows.

| Alternative | Finding | Decision |
| --- | --- | --- |
| Data-only compiler witness | It can record actual offsets and sizes in the exact output. A submitted witness can also agree with fabricated tables. | Select with an installed expected layout, field type assertions, actual output checks, and later trusted issuance. Never let a witness define its own acceptance rule. |
| Debug metadata or compiler layout output | A type record need not describe a retained object. DWARF, tool output, split debug files, and stripping add parsing and identity requirements. | Do not add this dependency. A pinned compiler tool can supply a later diagnostic cross-check. It cannot replace table readback. |
| Explicit Linux profiles | These give deterministic field interpretation and bounded work. The current assertions establish Darwin syntax checks only. | Select as expected contracts. Activate each profile only after actual Linux compiler representatives pass. Do not claim that the existing checks prove Linux layout. |
| Inspector that links or loads the plugin | Relocation becomes easier, but loader code, constructors, symbol interposition, and plugin code enter the observation. | Reject for this boundary. A later isolated Linux execution can supplement tests. It cannot supply independent passive readback. |

The source findings determine this choice.

- The fixed header defines 47 tables and 46 record types. It has 214 top-level semantic fields. Each directory entry has six `uint64_t` fields and one pointer.
- `collector_header_read.py` decodes C source. Its `element_bytes()` returns logical size. It is not a Linux layout authority.
- The writer imports the source reader's schema. The compiled reader must not import either implementation or use their private functions.
- The source reader enforces cursor order. It rejects reused slices and unused rows. Preserve this rule in compiled decoding. Do not introduce the old candidate's optional string sharing.
- The directory has three identities and one entry for each table. The source attributes `used` and `retain` do not prove that an actual output contains those objects.
- The empty-table form has one zero physical element. A count of zero does not permit an absent array or a null pointer.
- `phoenix.ingest` checks stripped x86-64 executable inputs. It requires executable entry evidence and an interpreter. It rejects normal symbol tables. This is the wrong public contract for a native shared plugin.
- `pyproject.toml` has no runtime dependencies. A small standard-library parser avoids an added ELF package and its closure. Its narrower output profile is intentional.

The two read boundaries are separate.

The existing source decoder checks the finite source grammar and complete logical record. It can establish that the source contains the intended data. It cannot establish what the compiler emitted.

The new compiled decoder reads the actual ELF directory, witness, table objects, and relocation records. It decodes scalars at checked offsets. It rebuilds the complete logical record independently. It does not convert ELF bytes back to generated C and call `read_header`. It does not call the writer's projection, measurements, sizes, or validators.

The coordinator later compares three complete canonical byte strings. These come from raw-input reconstruction, source decoding, and compiled decoding. It compares all fields and array order before accepting their digests. The compiled decoder's success means representation consistency. Trusted build issuance remains a separate F1 operation.

The installed layout contract is precise.

There are two profile IDs, `linux-aarch64-lp64-le-rela-1` and `linux-x86_64-lp64-le-rela-1`. Their ELF machines are 183 and 62. Both have eight-bit bytes, little-endian integers, 64-bit pointers, and the field layout specified below. Their toolchain approvals, compiler outputs, and build contexts remain separate.

The complete field inventory at the end of this document is normative for the proposed profile. Its numbers are expected values for later Linux checks. They are not measured Linux values. The profile accepts only the fixed native declarations. Changed declarations require new source identities and a reviewed profile change.

The layout rules expand every field in that inventory.

| Descriptor | Exact native shape and relative offsets | Size and alignment |
| --- | --- | --- |
| `u`, `b`, `n:N`, `end:X` | One `uint64_t`. Boolean values must be 0 or 1. `end:X` stores size and restores the exclusive end with checked addition. | 8 and 8 |
| `s`, `h`, `w`, `e:...` | `struct phoenix_bytes_slice_v1`. `uint32_t offset` at 0 and `uint32_t count` at 4. | 8 and 4 |
| `a:T`, `r:T` | `struct phoenix_T_slice_v1`. The same two fields and offsets. The exact C slice type must match T. | 8 and 4 |
| `i` | `struct phoenix_signed_v1`. `uint64_t negative` at 0 and `uint64_t magnitude` at 8. | 16 and 8 |
| `o:D` | Anonymous struct. `uint64_t tag` at 0. D at member `payload`, offset 8. Expand D recursively. | `8 + size(D)` and 8 |
| `v:T1,...,Tn`, `v0:T1,...,Tn` | Anonymous struct. `uint64_t tag` at 0. Typed slice `payload_Ti` at `8 + 8*(i-1)`. Expand both slice fields. | `8 + 8*n` and 8 |

Each record has the listed top-level offsets. Its size is the last offset plus the last field size. Its alignment is the maximum field alignment. These particular profiles have no record padding. Byte-table elements have size and alignment 1. Every one of the 47 slice types has size 8 and alignment 4. Use exact type checks, not width alone.

`phoenix_table_directory_entry_v1` has size 56 and alignment 8. Its offsets are `tag=0`, `count=8`, `logical_element_bytes=16`, `logical_bytes=24`, `element_bytes=32`, `storage_bytes=40`, and `table=48`. The first six fields are `uint64_t`. The last field is `const void *`.

`phoenix_data_directory_v1` has size 2728 and alignment 8. Its three `uint8_t[32]` arrays start at 0, 32, and 64. Their names are `logical_data_sha256`, `renderer_sha256`, and `native_source_sha256`. Its `tables[47]` starts at 96. Entry i starts at `96 + 56*i` for zero-based i. Pointer cell i starts at `144 + 56*i`.

The witness is an additional fixed export, `phoenix_collector_layout_v1`. It is a `const uint64_t[]` with no pointers. The compiler emits it from fixed expressions, never from submitted layout numbers. Its exact encoding is in api.md. A fixed C translation unit also checks every field with `offsetof`, `sizeof`, alignment, and `_Generic`. Check the nested slice fields, signed pair fields, option tags and payloads, variant tags and every payload, array types and extents, directory fields, and all table tags.

The installed manifest assigns semantic paths to witness positions. The plugin cannot submit names, dimensions, a different manifest, or a different accepted profile. The inspector compares the entire witness with the installed expected vector before reading the tables. It uses installed offsets after that comparison. A changed witness and changed table cannot move the acceptance boundary together.

The witness is evidence from the exact compiler output only after a trusted build transaction. It does not authenticate itself. A coherent synthetic ELF can pass pure inspection. It must still fail trusted issuance when no controller registry entry exists.

The bounded ELF profile is deliberately narrower than general ELF.

- Require ELF64, little endian, version 1, ET_DYN, the selected native machine, and OSABI 0 or 3. Require ABI version 0, zero reserved identification bytes, zero machine flags, and no PT_INTERP. Require entry 0. Do not infer the plugin machine from the x86-64 guest.
- Require ordinary section numbering, a section name table, exactly one SHT_DYNSYM, one SHT_SYMTAB, and their bounded string tables. Reject extended numbering, missing sections, compressed consumed sections, and TLS consumed objects. Production output is unstripped.
- Header, program, section, symbol, dynamic, and RELA entry sizes are exactly 64, 56, 64, 24, 16, and 24 bytes. Check multiplication and addition before access. All addresses remain within 64 bits. Never allocate memory from `p_memsz`.
- Check every non-NOBITS file span against the actual byte length. Check section links, entry counts, alignment powers, segment size ordering, and virtual-address overflow. Require each consumed allocated section to map through exactly one readable PT_LOAD with the same file offset.
- Require disjoint positive-length PT_LOAD virtual intervals and file intervals. Reject conflicting aliases. Require disjoint ordinary file section intervals and disjoint ELF metadata tables. Normal section containment within a segment is permitted. Page rounding must not create a writable alias for a consumed read-only range.
- A consumed object must fit wholly in one file-backed allocated PROGBITS section and one permitted segment. Do not use BSS, synthesized zero fill, holes, external memory, or a section-only mapping. Require data in non-executable mappings. The witness and table arrays must be read-only. The directory may be writable before relocation only if PT_GNU_RELRO covers its whole range and immediate binding is fixed in the build profile.
- A relocation section is not the runtime relocation authority by itself. Match allocated SHT_RELA ranges with PT_DYNAMIC's DT_RELA and DT_JMPREL ranges, their sizes, and their linked dynamic symbol table. The corresponding virtual-to-file mappings must agree exactly.
- Use a fixed `--hash-style=sysv` linker profile for the first implementation. Require DT_HASH and reject DT_GNU_HASH for this profile. Check the whole bounded SysV bucket and chain structure. Check `nchain` against `.dynsym`, name hashes, bucket membership, cycle absence, and unique lookup for each required export. Do not accept a symbol that the loader cannot find through the actual hash table.
- Check DT_STRTAB, DT_STRSZ, DT_SYMTAB, DT_SYMENT, DT_HASH, DT_RELA, DT_RELASZ, DT_RELAENT, DT_JMPREL, DT_PLTRELSZ, and DT_PLTREL against their section descriptions. Reject duplicate singleton tags. Repeated DT_NEEDED is an ordered dependency list and must match the installed context later.
- Require a terminating DT_NULL. Remaining dynamic slots must be zero. Reject DT_REL, DT_RELR, Android packed relocation encodings, DT_TEXTREL, text-relocation flags, and any unrecognized relocation encoding. Validate DT_RELACOUNT if present. Its count must fit and describe a leading run of relative relocations.
- Inventory remaining dynamic tags and imports. The later installed build context must allow each tag, dependency, search path, and import. Reject RPATH and RUNPATH in this initial profile. Do not resolve dependencies on the host. Do not follow debug links or read source archives.

Export and symbol rules prevent ambiguous table selection.

Require four defined unversioned dynamic exports. `phoenix_collector_data_v1` and `phoenix_collector_layout_v1` are GLOBAL DEFAULT OBJECT symbols of exact installed sizes. `qemu_plugin_version` is GLOBAL DEFAULT OBJECT, four bytes containing little-endian signed integer 4, with no relocation. `qemu_plugin_install` is GLOBAL DEFAULT FUNC with a nonzero size contained in executable file-backed code. Never call it.

The `.symtab` mirror of each export must agree with `.dynsym` on value, size, type, binding, visibility, and section. A mirror is not a second definition. Require one row with each required name in each symbol table. Reject duplicate names even if one row is undefined. Reject multiple definitions within a symbol table, weak substitutes, IFUNC, absolute symbols, undefined required exports, versioned aliases, common symbols, or contradictory mirrors. If version metadata exists for dependencies, check SHT_GNU_versym and DT_VERSYM for the same bounded array of two-byte entries. Its count must equal the dynamic symbol count. Required exports must have exact version value 1, with no hidden-version bit. Import version records remain bounded evidence for the later dependency-context check. Reject extra defined public exports in this fixed build profile.

Require exactly one row with each fixed `phoenix_<table>` name in `.symtab`. That row must be a LOCAL OBJECT symbol. Preserve these symbols in the output. Names, values, sizes, and section ownership must match the directory entries and resolved pointers. No table lookup depends on table symbol order. No input-controlled symbol names are accepted. Different table objects may not share or overlap physical storage. This includes empty arrays with equal zero contents.

The pointer contract uses only static local-array relative relocations.

| Host machine | Accepted directory-pointer relocation | Symbol and addend |
| --- | --- | --- |
| x86-64, 62 | `R_X86_64_RELATIVE`, numeric 8, ELF64 RELA | Symbol index 0. Nonnegative addend A names the exact table start. |
| AArch64, 183 | `R_AARCH64_RELATIVE`, numeric 1027, ELF64 RELA | Symbol index 0. Nonnegative addend A names the exact table start. |

There are exactly 47 consumed pointer relocations. Each has an aligned eight-byte destination at the corresponding directory pointer cell. Each cell has exactly one runtime relocation. Missing, duplicate, overlapping, shifted, symbol-based, or unsupported relocations reject. There is no fallback to the unrelocated word. `R_X86_64_64` and `R_AARCH64_ABS64` are not accepted for a directory pointer. Static arrays should not need symbol interposition. If an actual toolchain emits another form, keep that profile on HOLD until a separate contract review.

For a relative relocation the runtime value is `B + A`, where B is the load bias. Inspection uses A as an ELF virtual address. It never guesses B and never simulates a loader. Require A to equal the fixed local table symbol's value. Map the complete physical table extent through checked file-backed ranges.

ELF RELA ignores the original pointer-cell word. Do not use that word as the target. Its bytes still belong to the plugin identity Q and the saved directory-byte hash. Changing only that word can preserve decoded meaning while changing Q. A stale issued receipt must reject that change.

Outside the directory cells, accept only relative, GLOB_DAT, and JUMP_SLOT relocations in this first profile. Their numeric kinds are 8, 6, 7 on x86-64 and 1027, 1025, 1026 on AArch64. Check all destinations as eight-byte writes. GLOB_DAT and JUMP_SLOT need valid dynamic symbol indexes. Reject IFUNC resolution, COPY, TLS, unknown widths, duplicate destinations, executable destinations, and every relocation that touches a table, witness, directory scalar, or version integer. Ordinary imports remain unresolved by this reader. Their exact allowed names and dependencies belong to the later build context.

The table check uses actual retained storage.

For each tag in fixed order, require the exact logical element size from the independent schema. Require `logical_bytes == count * logical_element_bytes`. Require `element_bytes` to equal the installed native size. Require `storage_bytes == max(1, count) * element_bytes`. The local symbol size must equal `storage_bytes`. Check all products before slicing or creating rows.

For count zero, inspect one complete physical element. All semantic cells must be zero. Return no logical row. This includes inactive termination tables. Empty storage does not enable nonreturn contracts. The bytes table has one zero byte when empty.

Read only semantic fields. Never include C padding in a logical digest. The initial profiles have no internal padding. The parser must still separate semantic spans from object spans. Alignment gaps outside symbols are not table data. The exact plugin hash covers all padding and gaps. A future profile with padding needs an explicit mask and new approval. Never use padding to carry a field or accept a relocation there.

All object spans must be disjoint from other consumed objects and ELF metadata. Parent section and segment containment is permitted. Zero-length logical slices still obey cursor order. Slices must start at the current cursor and fit in the remaining table. Record references have count one. The root table has exactly one row. After traversal, every table row and byte must be consumed exactly once. No trailing data, reused string, extra row, alternate root, or selected-site projection can pass.

Decode strict UTF-8, exact literal values, witness lengths 1 through 15, Boolean values, optional fields, variants, signed extremes, and start/size geometry. Inactive payloads must be zero. Reject negative zero and signed overflow. Restore exclusive endpoints without wrapping `2**64`. Compare every retained logical field with independently reconstructed raw-input data. Preserve `needed_library=None`, gap indexes and both address domains, every role and continuation user, and call-specific route positions.

The identity order stays acyclic.

1. Fixed declarations, witness source, both decoders, source closure, and the installed layout contract have source identities.
2. Raw input reconstruction produces D. The current renderer produces G with its existing R and N identities. Do not enlarge or reinterpret the existing component hash algorithms.
3. The new complete source manifest C includes G and all fixed compilation and inspection inputs. The build request K binds C, the installed profile, compiler, linker, flags, headers, images, and limits.
4. The actual compiler output has identity Q. The inspector produces record I from Q, the installed layout, complete logical data, table inventory, exports, and relocation evidence.
5. The trusted worker issues receipt B after checking I. B binds K, Q, and I. A controller-owned registry stores K, B, Q, and the build-context identity. I contains no B or future deployment identity.
6. Per-trial runtime and execution records bind each actual build separately. Calibration applicability and deployment occur later. Execution records bind the fixed launch profile, expanded launch specification, accepted case, both accepted oracles, and complete outcomes.

Keep F1 trusted issuance, F2 per-trial calibration and installed applicability, and F4 full source and launch closure. Do not expand the nine-file policy hash or ten-file admission hash. Keep QEMU 9.2 observer evidence separate from QEMU 8.2.2 and Rosetta oracle evidence. No observer artifact enters reconstructed C or a package archive.

The field inventory below completes the layout contract. Table tag 1 is `bytes`, with `uint8_t` elements. A field entry gives its native name, absolute offset within its record, and descriptor. Expand nested fields by the rules above. Logical names are unchanged except the two geometry `_size` fields, which restore `_end_exclusive` values. No other field is omitted.

`2 uints`

```text
f_value @ 0 : u
```

`3 strings`

```text
f_value @ 0 : s
```

`4 registers`

```text
f_name @ 0 : s
f_width @ 8 : u
```

`5 plan_gaps`

```text
f_address @ 0 : u
f_reason @ 8 : s
```

`6 positions`

```text
f_route_sha256 @ 0 : h
f_position @ 8 : u
```

`7 dispositions`

```text
f_address @ 0 : u
f_disposition @ 8 : v:user,transit,omitted
```

`8 dynamic`

```text
f_tag @ 0 : i
f_value @ 16 : u
```

`9 original`

```text
f_bytes @ 0 : u
f_sha256 @ 8 : h
```

`10 geometry`

```text
f_executable_file_start @ 0 : u
f_executable_file_size @ 8 : end:executable_file_start
f_load_memory_start @ 16 : u
f_load_memory_size @ 24 : end:load_memory_start
```

`11 transport_limits`

```text
f_data_bytes @ 0 : u
f_elf_segments @ 8 : u
f_gap_records @ 16 : u
f_lift_bytes @ 24 : u
f_mapping_bytes @ 32 : u
f_omissions @ 40 : u
f_original_bytes @ 48 : u
f_route_memberships @ 56 : u
f_route_path_positions @ 64 : u
f_routes @ 72 : u
f_users @ 80 : u
```

`12 trace_limits`

```text
f_events @ 0 : u
f_execution_callbacks @ 8 : u
f_frames @ 16 : u
f_snapshot_bytes @ 24 : u
f_translated_instructions @ 32 : u
f_wire_bytes @ 40 : u
```

`13 capture_limits`

```text
f_events @ 0 : u
f_execution_callbacks @ 8 : u
f_frames @ 16 : u
f_full_plan_bytes @ 24 : u
f_full_plan_sites @ 32 : u
f_guarded_instructions @ 40 : u
f_receipt_bytes @ 48 : u
f_route_entries @ 56 : u
f_scope_bytes @ 64 : u
f_snapshot_bytes @ 72 : u
f_thunk_neutral_bytes @ 80 : u
f_thunk_neutral_instructions @ 88 : u
f_translated_instructions @ 96 : u
f_wire_bytes @ 104 : u
```

`14 import_id`

```text
f_needed_library @ 0 : o:s
f_symbol @ 16 : s
f_version @ 24 : o:s
f_version_hidden @ 40 : b
```

`15 import_binding`

```text
f_address_proof_sha256 @ 0 : h
f_binary_sha256 @ 8 : h
f_function @ 16 : o:u
f_gap @ 32 : o:s
f_identity @ 48 : o:r:import_id
f_lift_sha256 @ 64 : h
f_relocation_file_offset @ 72 : o:u
f_relocation_kind @ 88 : o:u
f_relocation_slot @ 104 : o:u
f_site @ 120 : u
f_symbol_index @ 128 : o:u
f_thunk_path @ 144 : a:uints
```

`16 call`

```text
f_continuation @ 0 : u
f_import_gaps @ 8 : a:strings
f_imported @ 16 : o:r:import_binding
f_kind @ 32 : e:direct_call|indirect_call
```

`17 jump`

```text
f_kind @ 0 : e:indirect_jump
```

`18 return`

```text
f_kind @ 0 : e:return
```

`19 trace_site`

```text
f_address @ 0 : u
f_continuation_of @ 8 : a:uints
f_entry @ 16 : b
f_owner @ 24 : u
f_transfer @ 32 : v0:call,jump,return
f_witness_hex @ 64 : w
```

`20 trace_plan`

```text
f_address_proof_sha256 @ 0 : h
f_binary_sha256 @ 8 : h
f_gaps @ 16 : a:plan_gaps
f_lift_sha256 @ 24 : h
f_limits @ 32 : r:trace_limits
f_registers @ 40 : a:registers
f_schema @ 48 : n:2
f_scope @ 56 : a:uints
f_sites @ 64 : a:trace_site
```

`21 lift_main`

```text
f_kind @ 0 : e:lift_main
f_lift_sha256 @ 8 : h
f_main_elf @ 16 : u
```

`22 explicit_entry`

```text
f_kind @ 0 : e:explicit_entry
f_request_sha256 @ 8 : h
```

`23 requested_scope`

```text
f_policy @ 0 : e:main-window-six-v1
f_root @ 8 : u
f_root_evidence @ 16 : v:lift_main,explicit_entry
f_users @ 40 : a:uints
```

`24 user`

```text
f_kind @ 0 : e:user
f_owner @ 8 : u
```

`25 transit`

```text
f_kind @ 0 : e:transit
f_route_ids @ 8 : a:strings
```

`26 omitted`

```text
f_kind @ 0 : e:omitted
f_reason @ 8 : e:outside_requested_users|runtime_lifecycle_outside_window
```

`27 omitted_site`

```text
f_address @ 0 : u
f_full_roles @ 8 : a:strings
f_owner @ 16 : u
f_reason @ 24 : e:outside_requested_users|runtime_lifecycle_outside_window
f_witness_sha256 @ 32 : h
```

`28 transit_route`

```text
f_binding_sha256 @ 0 : h
f_call_site @ 8 : u
f_entries @ 16 : a:uints
f_instruction_path @ 24 : a:uints
f_request @ 32 : r:import_id
f_slot @ 40 : u
f_terminal @ 48 : u
```

`29 ordinary`

```text
f_kind @ 0 : e:ordinary
f_successor @ 8 : u
```

`30 local_direct`

```text
f_destination @ 0 : u
f_kind @ 8 : e:local_direct
```

`31 local_conditional`

```text
f_fallthrough @ 0 : u
f_kind @ 8 : e:local_conditional
f_taken @ 16 : u
```

`32 planned_roles`

```text
f_continuation @ 0 : o:u
f_destination @ 16 : o:u
f_kind @ 32 : e:planned_roles
f_transfer_kind @ 40 : e:direct_call|indirect_call|indirect_jump|return
```

`33 transit_instruction`

```text
f_kind @ 0 : e:transit_instruction
f_positions @ 8 : a:positions
```

`34 reject`

```text
f_kind @ 0 : e:reject
f_reason @ 8 : s
```

`35 guard_instruction`

```text
f_address @ 0 : u
f_full_roles @ 8 : a:strings
f_owner @ 16 : u
f_rule @ 24 : v:ordinary,local_direct,local_conditional,planned_roles,transit_instruction,reject
f_witness_hex @ 80 : w
```

`36 dormant_outside_window`

```text
f_kind @ 0 : e:dormant_outside_window
f_reason @ 8 : s
```

`37 guard_reject`

```text
f_kind @ 0 : e:guard_reject
f_reason @ 8 : s
```

`38 local_branch_guard`

```text
f_destination @ 0 : u
f_fallthrough @ 8 : o:u
f_kind @ 24 : e:local_branch_guard
f_rule @ 32 : e:local_direct|local_conditional
```

`39 metadata_only`

```text
f_kind @ 0 : e:metadata_only
f_reason @ 8 : s
```

`40 gap_record`

```text
f_address @ 0 : u
f_disposition @ 8 : v:dormant_outside_window,guard_reject,local_branch_guard,metadata_only
f_domain @ 48 : e:ghidra
f_elf @ 56 : o:u
f_index @ 72 : u
f_reason @ 80 : s
```

`41 exit_from_supported_bits`

```text
f_register @ 0 : s
f_transform @ 8 : s
f_width @ 16 : u
```

`42 exact_signal`

```text
f_signal @ 0 : u
```

`43 termination_contract`

```text
f_behavior @ 0 : e:process-termination
f_binary_sha256 @ 8 : h
f_call_site @ 16 : u
f_callbacks @ 24 : e:forbidden
f_cleanup @ 32 : e:no-unobserved-main-reentry
f_full_plan_sha256 @ 40 : h
f_import_binding_sha256 @ 48 : o:h
f_permitted_physical_route_sha256 @ 64 : h
f_provider_evidence_sha256 @ 72 : h
f_rule_sha256 @ 80 : h
f_runtime_manifest_base_sha256 @ 88 : h
f_schema @ 96 : n:1
f_termination_rule @ 104 : v:exit_from_supported_bits,exact_signal
```

`44 scope_selection`

```text
f_active_unlisted @ 0 : e:reject
f_address_proof_sha256 @ 8 : h
f_binary_sha256 @ 16 : h
f_claim @ 24 : e:requested-main-activation
f_contracts @ 32 : a:termination_contract
f_dispositions @ 40 : a:dispositions
f_full_plan_sha256 @ 48 : h
f_gap_dispositions @ 56 : a:gap_record
f_guard_instructions @ 64 : a:guard_instruction
f_lazy_resolver @ 72 : e:unsupported
f_lift_sha256 @ 80 : h
f_limits @ 88 : r:capture_limits
f_omitted @ 96 : a:omitted_site
f_outside_window @ 104 : e:all-sites-outside-frame-capture
f_policy @ 112 : e:main-window-six-v1
f_policy_implementation_sha256 @ 120 : h
f_registers @ 128 : a:registers
f_request @ 136 : r:requested_scope
f_root @ 144 : u
f_routes @ 152 : a:transit_route
f_schema @ 160 : n:1
f_transit_profile @ 168 : e:eager-only
f_users @ 176 : a:uints
```

`45 load_segment`

```text
f_alignment @ 0 : u
f_file_offset @ 8 : u
f_file_size @ 16 : u
f_flags @ 24 : u
f_index @ 32 : u
f_memory_size @ 40 : u
f_va @ 48 : u
```

`46 elf_image`

```text
f_dynamic @ 0 : a:dynamic
f_entry @ 8 : u
f_kind @ 16 : u
f_segments @ 24 : a:load_segment
```

`47 collector_data`

```text
f_address_proof_sha256 @ 0 : h
f_c_data_schema @ 8 : e:phoenix-eager-c-data-1
f_full_plan @ 16 : r:trace_plan
f_full_plan_sha256 @ 24 : h
f_geometry @ 32 : r:geometry
f_image @ 40 : r:elf_image
f_lift_sha256 @ 48 : h
f_original @ 56 : r:original
f_policy_implementation_sha256 @ 64 : h
f_profile @ 72 : e:main-window-six-v1
f_schema @ 80 : e:phoenix-eager-collector-data-1
f_scope @ 88 : r:scope_selection
f_scope_sha256 @ 96 : h
f_transport_limits @ 104 : r:transport_limits
```
