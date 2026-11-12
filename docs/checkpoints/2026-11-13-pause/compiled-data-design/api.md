This API specifies passive collector-data inspection. Every success type below describes consistency. No type grants build issuance, cache reuse, calibration, deployment, or runtime admission.

Use frozen dataclasses and tuples. Raw values are exact immutable `bytes`. Integer fields reject Boolean and float values. SHA-256 values use 64 lowercase hexadecimal characters. File offsets and ELF virtual addresses are separate types. The plugin remains input bytes throughout.

The only new public inspection call is as follows.

```text
inspect_compiled_data(
    plugin_raw: bytes,
    *,
    expected: ExpectedCollector,
    profile: Literal[
        "linux-aarch64-lp64-le-rela-1",
        "linux-x86_64-lp64-le-rela-1"
    ],
    limits: InspectionLimits = InspectionLimits()
) -> CompiledDataInspection | InspectionRejected

ExpectedCollector = {
    logical_raw: bytes,
    renderer_sha256: Digest,
    native_source_sha256: Digest
}

CompiledDataInspection = {
    logical_raw: bytes,
    inspection_raw: bytes
}

InspectionRejected = {
    reason: InspectionReason,
    detail: str
}
```

`logical_raw` in the result is produced from actual table bytes. It is not copied from `expected`. Require exact byte equality after a complete independent decode. Compute D from that complete byte string. Compare the directory's D, R, and N with these values. A caller can invent matching expectations. This pure call therefore cannot authenticate the source inputs.

The later coordinator obtains expectations through raw-input reconstruction and installed source pins. It separately calls the existing source reader. It compares the complete source-decoded record with the complete reconstructed record and the complete compiled record. No comparison may use only the selected sites, table counts, or D.

The profile argument selects installed code. There is no `layout_raw` argument and no plugin-selected profile. Before Linux validation, the profiles are test-only. Production must require the separate installed profile approval described below.

The module boundaries are as follows.

| Module | Data it owns | Dependencies allowed for this unit |
| --- | --- | --- |
| `phoenix/observe/collector_elf.py` | Bounded ELF view, symbols, file-backed spans, dynamic metadata, relocation index, export lookup. | Python standard library only. No `phoenix.ingest` import. |
| `phoenix/observe/collector_layout.py` | Independent fixed semantic field inventory, profile vectors, limits, and profile lookup. | Python standard library only. No writer or source-reader imports. |
| `phoenix/observe/collector_compiled.py` | Actual field decoding, cursor checks, canonical logical bytes, complete comparison, inspection record. | The two modules above and standard library. Use its own immutable logical representation internally. |
| `native/collector_layout_v1.c` | Data-only compiler witness. | Fixed native declaration and fixed assertion header only. |
| `native/collector_layout_checks_v1.h` | Complete field, type, tag, alignment, and extent assertions. | Fixed native declaration and standard integer and offset headers. |

The native paths above are under `phoenix/observe/`. The new compiled reader does not import `FrozenRecord` through `collector_data.py`. That import would load unrelated reconstruction dependencies. Its internal `LogicalObject` is a tuple of unique sorted `(str, LogicalValue)` pairs. `LogicalValue` is exactly null, bool, int, str, tuple of values, or `LogicalObject`. The result exposes canonical bytes, so it needs no public logical-object type.

The ELF subunit has one internal cross-module call.

```text
read_collector_elf(
    raw: bytes,
    *, machine: Literal[62, 183], limits: InspectionLimits
) -> CollectorElf | InspectionRejected

CollectorElf = {
    raw: bytes,
    machine: Literal[62, 183],
    loads: tuple[LoadSpan, ...],
    sections: tuple[Section, ...],
    symbols: tuple[Symbol, ...],
    dynamic: tuple[DynamicEntry, ...],
    relocations: tuple[Rela, ...],
    needed: tuple[bytes, ...],
    exports: tuple[Export, ...]
}

LoadSpan = {index, flags, offset, va, filesz, memsz, align}
Section = {index, name: bytes, type, flags, va, offset, size,
           link, info, align, entsize}
Symbol = {table_section, index, name: bytes, binding, type,
          visibility, section_index, va, bytes, version_index}
DynamicEntry = {index, tag: signed64, value: unsigned64}
Rela = {table_section, index, file_offset, place_va,
        type, symbol_index, addend: signed64, width: Literal[8]}
Export = {name: fixed ASCII str, dynamic_symbol_index,
          static_symbol_index, section_index, va, file_offset,
          bytes, binding, type, visibility}
```

ELF arrays preserve input index order. Symbol names remain bounded bytes. Required-name comparisons use fixed ASCII bytes. Never decode arbitrary ELF names with replacement. The returned view stores spans into `raw`, not copies of every section. `read_collector_elf` owns `struct.error` prevention through range checks. It does not catch unrelated programming faults.

Private operations `file_span(va, size)`, `required_export(name)`, `local_table(name)`, and `relocation_at(place)` use validated indexes. They return one result or refuse. They never select the first of several candidates. The inspector uses sorted interval scans and maps. It must not compare each relocation with every table row.

The installed layout shape is as follows.

```text
LayoutProfile = {
    schema: "phoenix-collector-layout-profile-1",
    id: fixed profile ID,
    machine: 62 | 183,
    c_data_schema: "phoenix-eager-c-data-1",
    declarations_sha256: Digest,
    witness_source_sha256: Digest,
    checks_source_sha256: Digest,
    types: tuple[TypeLayout, ...],
    members: tuple[MemberLayout, ...],
    tables: tuple[TableLayout, ...],
    witness_words: 5021,
    witness_bytes: 40168,
    elf_contract: "collector-elf-sysv-rela-1"
}

TypeLayout = {id, name: fixed str, bytes, alignment}
MemberLayout = {id, owner, path: fixed str, offset, bytes,
                alignment, type_code, extent}
TableLayout = {tag, name: fixed str, element_type,
               logical_element_bytes, record_kind,
               fields: tuple[{logical_name, native_name, descriptor}, ...]}
```

The manifest has 100 type entries, 653 member entries, and 47 table entries. `uints` and `strings` decode as scalar rows. `registers`, `plan_gaps`, `positions`, `dispositions`, and `dynamic` decode as ordered pair rows. All remaining record tables decode as objects with sorted logical keys. The bytes table is storage, not a logical object. These rules fix `record_kind`. Type IDs are fixed. IDs 1 through 4 mean `uint8_t`, `uint32_t`, `uint64_t`, and `const void *`. IDs 5 through 51 are the slice types in table-tag order. ID 52 is `phoenix_signed_v1`. IDs 53 through 98 are the 46 record types in table-tag order. IDs 99 and 100 are the directory entry and directory types.

Member IDs start at 1. Process owner types in ID order. Primitive types have no members. Process declared fields in native declaration order. Emit the field first, then its nested members in depth-first declaration order. Expand slices to `offset` then `count`. Expand signed pairs to `negative` then `magnitude`. Expand options to `tag` then `payload`. Expand variants to `tag` then all payload slices in their declared order. Arrays are one member with an element type and exact extent. Do not emit one member for each array element. This rule yields 653 entries, including composite fields. `path` uses C member syntax, such as `f_transfer.payload_call.count`.

An anonymous option or variant struct has `type_code=0` and extent 1. Its children carry their exact native types. A named struct or scalar uses its type ID. An array uses its element type ID and its exact extent. For each member, `bytes` is the size of the entire member, including an array. Its offset is relative to its owner type. The manifest is immutable installed data. A submitted ELF cannot alter this order or these meanings.

The witness has exactly 5021 little-endian uint64 words, or 40168 bytes. It has no padding, strings, pointers, or relocation cells. Its exact order is as follows.

```text
9-word prefix:
    0x50484f454e49584c, 1, machine, 8, 8, 1, 100, 653, 47
    magic, version, machine, CHAR_BIT, pointer_bytes,
    little_endian_marker, type_count, member_count, table_count

100 type rows, 3 words each:
    type_id, sizeof(type), alignof(type)

653 member rows, 7 words each:
    owner_type_id, member_id, offsetof(owner, path),
    sizeof(member), alignof(member), type_code, extent

47 table rows, 3 words each:
    native_table_tag, element_type_id, sizeof(element_type)
```

The machine value comes from a fixed compiler-target conditional. Unsupported targets fail compilation. `CHAR_BIT`, pointer width, and byte order have compile-time assertions. The endian marker is 1 only in the checked little-endian branch. Type IDs and member IDs are fixed literals. Size, alignment, offsets, and table tags come from the actual C declarations. `_Generic` assertions check every named scalar, slice, signed pair, pointer, and array type. Anonymous aggregate checks cover size, alignment, all child types, and all child offsets. The fixed source cannot take witness values from the generated header or an external manifest at compile time.

The source witness contains no manifest digest. This avoids a source-to-manifest-to-source cycle. The external build context binds the source hashes, manifest hash, assertion-source hash, and complete witness bytes from the output.

The two profiles can have equal type layouts. They cannot share an architecture approval. The installed manifest must match the selected machine and the compiled witness exactly. The temporary `proposed-layout.json` records this design's expansion. It is design evidence, not an installed or approved production manifest.

The inspection record is canonical and contains no authority claim.

```text
InspectionRecord = {
    schema: "phoenix-collector-compiled-inspection-1",
    status: "consistent",
    plugin: {bytes, sha256},
    reader_source_manifest_sha256: Digest,
    layout_profile_id: str,
    layout_profile_sha256: Digest,
    elf_contract: "collector-elf-sysv-rela-1",
    elf_machine: 62 | 183,
    logical_data: {bytes, sha256},
    renderer_sha256: Digest,
    native_source_sha256: Digest,
    directory: ObjectInspection,
    witness: ObjectInspection,
    tables: tuple[TableInspection, ...],
    exports: tuple[Export, ...],
    dynamic_metadata_sha256: Digest,
    relocation_inventory_sha256: Digest,
    limits: InspectionLimits
}

ObjectInspection = {
    va, file_offset, bytes, section_index,
    dynamic_symbol_index, static_symbol_index, raw_sha256
}

TableInspection = {
    tag, name, count, logical_element_bytes, logical_bytes,
    element_bytes, storage_bytes, va, file_offset,
    section_index, static_symbol_index, raw_sha256,
    pointer_relocation: Rela
}
```

The two metadata digests identify canonical arrays of the complete `DynamicEntry` and `Rela` records. Save those arrays beside the inspection. Include their exact lengths and hashes in the later artifact manifest. The plugin itself remains mandatory. A metadata array cannot replace actual output bytes. `exports` is sorted by fixed export name. `tables` is in tag order. No numeric size includes an invented logical row for empty storage.

Use sorted JSON keys, compact separators, ASCII escapes, and one final LF for all new records. Preserve tuple order. Reject duplicate keys, extra fields, floats, noncanonical bytes, invalid exact types, and invalid digests when parsing saved records. Do not normalize a saved record before checking its exact digest. H means SHA-256 of exact canonical bytes. Existing receipt-parser behavior remains unchanged.

The limits are explicit. Lower values are permitted where noted. Raised values, zero, negative, Boolean, and float values refuse.

| Field in `InspectionLimits` | Maximum | Before-work rule |
| --- | ---: | --- |
| `plugin_bytes` | 33554432 | Check byte type and length before hashing or parsing. The file adapter later reads at most limit plus one. |
| `program_headers` | 1024 | Check the declared count and total span before iteration. |
| `sections` | 4096 | Check before section allocation. |
| `symbols` | 131072 total | At most 65536 per symbol table. Check sizes before name lookup. |
| `string_table_bytes` | 4194304 per table | Check before bounded NUL indexing. |
| `symbol_name_bytes` | 4096 | Check before copying or comparison. |
| `dynamic_entries` | 4096 | Check before iteration. |
| `relocations` | 262144 total | Check before indexing or sorting. |
| `hash_words` | 262144 | Check SysV hash products before traversal. |
| `physical_data_bytes` | 33554432 | Sum directory, witness, and all physical tables before row decode. |
| `logical_data_bytes` | 16777216 | Apply while emitting canonical output. The retained lower `data_bytes` also applies. |
| `nonbyte_rows` | 4194304 total | Reserve all declared counts before materialization. A table count is also below `2**32`. |
| `scalar_visits` | 8388608 | Charge every decoded scalar, slice component, tag, and zero-storage scalar. |
| `scanned_bytes` | 268435456 | Charge byte scans, including names, table strings, canonical emission, and hashes. No unbounded rescans. |
| `nesting` | 32 | Check before entering a nested logical value. |
| `inspection_bytes` | 65536 | Apply incrementally during canonical encoding. |

The type, member, table, and witness counts are exact schema constants. They are not caller limits. The layout manifest has a 256 KiB bound. Dynamic and relocation evidence records together have a 64 MiB bound. Check that bound during their serialization. Refuse before adding a field that exceeds it.

The existing 64 MiB header cap and 32 MiB logical-initializer cap remain in force at source preparation. They do not permit a larger plugin or override the physical cap. The original remains bounded to 16 MiB at the worker. All lower capture and transport limits remain binding. A new work limit can reject a source-valid record. Record that refusal instead of dropping metadata or raising a cap.

Use bounded memory views for binary data. Build NUL indexes once per string table. Use sorted interval scans and a relocation map. Hash the plugin once per inspection. Decode table strings once in canonical traversal. Work is linear in bytes and rows, plus sorting bounded metadata. Do not promise total Python memory from a file-byte cap. The later worker must measure peak memory and enforce its separate 1 GiB process limit. Inspection time and worst-case memory remain validation gates.

The failure order is fixed.

1. Input types and limits.
2. ELF header, tables, segments, sections, and mappings.
3. Dynamic metadata, hash lookup, required symbols, versions, and relocations.
4. Installed profile and complete witness match.
5. Directory identities, tags, dimensions, pointer cells, object spans, and physical table storage.
6. Complete logical decode, exact cursor exhaustion, and retained lower limits.
7. Complete expected-record comparison and D, R, N comparison.
8. Canonical inspection encoding and evidence-byte limits.

Within a stage use file index order, then table tag, row, and field order as applicable. Return only the first bounded error. No failure returns a logical record or partial success.

```text
InspectionReason =
    input_type | input_limit | unsupported_elf | malformed_elf |
    ambiguous_mapping | symbol_missing | symbol_ambiguous |
    export_contract | dynamic_contract | relocation_contract |
    layout_mismatch | directory_contract | storage_overlap |
    table_bounds | logical_shape | logical_mismatch | source_identity |
    work_limit | record_limit
```

Details are fixed text with bounded numeric context, at most 512 characters. Do not echo arbitrary symbol strings or raw table data. Expected format errors become refusals. Internal `RuntimeError`, `AssertionError`, and unrelated `TypeError` remain visible faults. Do not catch all exceptions. The production adapter later maps these reasons into its existing outer rejection family. This unit does not add capture-stream gap codes.

The later approval and issuance shapes are separate.

```text
LayoutValidationTrial = {
    case_id: str,
    fixture_class: "compiled_representative" | "actual_collector",
    profile_id: fixed profile ID,
    compiler_context_sha256: Digest,
    source_manifest_sha256: Digest,
    generated_header_sha256: Digest,
    actual_plugin_sha256: Digest,
    mutation: NoMutation | ChangedArtifact,
    expected_result: ExpectedConsistent | ExpectedRejected,
    actual_result: ConsistentTrial | RejectedTrial,
    artifact_manifest_sha256: Digest
}

NoMutation = {kind: "none"}
ChangedArtifact = {kind: "changed", baseline_plugin_sha256: Digest,
                   mutation_spec_sha256: Digest}
ExpectedConsistent = {kind: "consistent"}
ExpectedRejected = {kind: "rejected", reason: InspectionReason}
ConsistentTrial = {kind: "consistent", inspection_sha256: Digest}
RejectedTrial = {kind: "rejected", reason: InspectionReason,
                 rejection_record_sha256: Digest}

LayoutProfileApproval = {
    schema: "phoenix-collector-layout-approval-1",
    profile_sha256, inspector_source_manifest_sha256,
    frozen_test_manifest_sha256, trials_manifest_sha256,
    approved_build_context_sha256, independent_review_sha256
}
```

A rejection variant has no inspection digest. It has the exact rejection-record digest. No fake digest represents a missing value. `fixture_class` separates actual compiler representatives from actual collector output. Synthetic tests cannot enter this schema or satisfy a compiled-representative requirement. The fields above describe compiler-backed trials. U1 and U2 synthetic tests use ordinary test records and cannot fabricate a compiler context to enter this trial schema.

A trial binds its actual command, environment, compiler and linker binaries, headers, flags, native host evidence, output bytes, and source inputs through its artifact manifest. Approval belongs to the installed controller. A suite cannot appoint its own reviewer or select its applicability rule.

The later build receipt adds `inspection_sha256`, `layout_profile_sha256`, and `layout_approval_sha256`. Store the exact inspection bytes and all output artifacts. Preserve corrected F1's `ConsistentBuild` and `CheckedBuild` distinction. `TrustedIssuedBuildPin` still comes only from the controller registry. Recompute inspection from freshly read plugin bytes on cache reuse. A submitted inspection record is not a substitute.

No new digest depends on its own serialized digest. The witness contains no Q, I, B, runtime, calibration, or deployment identity. The inspection contains Q and input implementation identities, but no receipt identity. The receipt binds I afterward. Later calibration records keep per-trial B, Q, T, launch, and artifact identities. This API does not replace the full capture review.

The future build request uses output contract `native-elf-collector-inspected-1`. It adds `layout_profile_sha256` and `inspector_source_manifest_sha256` to the proposed request. These fields enter K before compilation. The request does not contain Q, I, B, or its own hash. U4 compiler trials use a distinct test-only transaction type without a production layout approval. U5 requires an installed layout approval before production receipt issuance. The trial record and approval therefore cannot depend on a future production receipt. These additions apply to the proposed collector build records. They do not reinterpret an existing accepted oracle receipt.
