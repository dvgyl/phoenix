# Adapter API and wire contract

This is a proposed contract. No type or function in this document exists by virtue of this design. “Reader accepts” means structural acceptance only. It never means semantic or production approval. Producer admission and production remain HOLD.

## 1. Versions and entry points

Profile: `ordinary-byte-adapter/1`. Diagnostic selector: `--byte-adapter-v1`.

The proposed Java invocation has exactly four script arguments:

```text
ExportLift.java <lift-path> --byte-adapter-v1 <adapter-draft-path> <context-path>
```

The current one-argument export, two-argument switch export, and four-argument `--byte-diagnostic` form retain their current behavior. Unknown selectors and argument combinations refuse. The new selector cannot be combined with the old selectors. There is no automatic retry with another profile.

Proposed pure Python entry points:

```text
parse_byte_graph_v2(raw_bytes, *, lift, pass_record, limits) -> ByteGraphV2
parse_byte_source_v2(raw_bytes, *, graph, raw_c_bytes, pass_record, limits)
    -> ByteSourceV2
project_positive_spans(source, *, graph, raw_c_bytes) -> PositiveSpanView
parse_byte_adapter_v1(raw_bytes, *, lift_bytes, mapping_bytes, context, limits)
    -> ByteAdapterObservation
```

The readers accept bytes and already supplied immutable data. They do not open files, run tools, consult environment variables, contact providers, publish, or return emission authority. The adapter reader parses the exact lift and mapping using their existing readers. It verifies their bindings before it parses function members. There is no public function that converts schema 2 to schema 1 by weakening an invariant.

Implement the graph and source readers before Java capture or selector integration. They have separate types and error classes. Their serializers use the rules below. Old readers must reject schema 2. New readers must reject schema 1. Publication versions 1–3 and `evidence-current` remain unchanged. A future publication format needs a separate reviewed version and selector; this design does not assign one.

## 2. Primitive rules and identities

All objects have exactly the fields listed here. Missing fields, extra fields, duplicate JSON keys, invalid UTF-8, trailing data, NaN, infinity, floats in integer fields, and Booleans in integer fields refuse. JSON nesting depth is at most 32. Strings must consist of Unicode scalar values. Reject isolated UTF-16 surrogates before encoding. Do not normalize Unicode or line endings.

Canonical bytes use sorted object keys, compact JSON separators, `ensure_ascii=true`, no non-finite numbers, and one final LF. Canonical output is ASCII. Readers can accept noncanonical JSON with the same strict data model; artifact hashes always use the complete canonical bytes. Raw C hashes use the original UTF-8 bytes, without canonicalization. SHA-256 fields are exactly 64 lowercase hexadecimal characters. No object includes its own hash.

| Type | Exact fields or representation |
|---|---|
| `Address` | `{space, offset}`. `space` is the actual nonempty Ghidra space name, at most 128 UTF-8 bytes. `offset` is canonical unsigned hex, `0x0` or `0x` plus nonzero leading digit and lowercase hex digits; value is below 2^64. |
| `FunctionKey` | `{binary_sha256, ghidra_entry}`. The entry is canonical unsigned hex in the program's RAM space. It is the ordinary listing entry, never a block minimum. |
| `Sequence` | `{address: Address, index}`. `index` is the actual sequence time, 0 through 1,000,000. It is not a block position. |
| `OpKey` | `{function: FunctionKey, domain, pass_id, sequence: Sequence}`. `domain` is `raw` or `analyzed`. The domain is part of identity. |
| `ValueKey` | `{function: FunctionKey, pass_id, local_id}`. `local_id` is the unsigned interpretation of the actual Java `VarnodeAST.getUniqueId()`, 0 through 2^32−1. |
| `BlockKey` | `{function: FunctionKey, pass_id, index}`. `index` is the actual decoded block index, 0 through 2^31−1. |
| `Span` | `{start, end}`. UTF-8 byte offsets, `0 <= start <= end <= raw_c_bytes`. It is a half-open interval. |
| `EdgeSlot` | `{other: BlockKey, reciprocal_slot}`. The reciprocal slot is an integer in the other block's opposite edge array. |
| `SourcePin` | `{path, bytes, sha256}`. `path` is a reviewed repository-relative path of at most 256 UTF-8 bytes, with no empty, `.` or `..` segment. `bytes` is a nonnegative integer at most 64 MiB. Paths are unique and sorted. |

Every key in one graph or source must have its function and pass. A sequence address or equal storage does not join domains, passes, or values. Java object identity must agree with key identity during capture. Two distinct objects with the same key cause a refusal. Repeated references to the same object retain the same key. Distinct values with equal address and size remain distinct.

The source-pin list is an explicit reviewed allowlist, not a file-discovery result. For the first implementation it must include the four producer scripts (`ExportLift.java`, `OrdinarySwitchEvidence.java`, `OrdinaryByteEvidence.java`, `OrdinaryByteAdapter.java`), the three new Python modules named in the plan, `phoenix/lift/index.py`, `phoenix/lift/mapping.py`, `phoenix/lift/evidence.py`, `tools.lock`, and `uv.lock`. Include another local dependency if these modules execute it. Such a change requires a revised manifest and review. The final hashes cannot be assigned before implementation. The manifest of frozen inputs is a baseline, not the identity of a future producer.

## 3. Pass and tool binding

`PassRecord` has exactly these fields:

| Field | Value and rule |
|---|---|
| `schema` | Integer 1, the pass-record schema for this new profile. |
| `profile` | `ordinary-byte-adapter/1`. |
| `function` | Ordinary `FunctionKey`. |
| `call_ordinal` | 0-based position in the complete ordinary function roster, at most 31. |
| `ghidra_version` | Actual runtime version; this profile requires `12.2`. |
| `ghidra_revision` | Actual runtime revision; exactly `8ca9077040cc43cd790babcfccf19475622a3e9a`. |
| `java_runtime_version` | Actual runtime value; first profile requires the pinned Temurin `25.0.5+8-LTS`. Verify the runtime's exact property in the implementation control. A different spelling or runtime requires an explicit profile decision, not silent coercion. |
| `language_id` | Actual value, exactly `x86:LE:64:default`. |
| `compiler_spec_id` | Actual value, exactly `gcc`. |
| `simplification_style` | Actual value, exactly `decompile`. |
| `configured_options` | JSON null. It means no explicit options object was installed. It does not enumerate native defaults. |
| `timeout_seconds` | Integer 60. |
| `printer_transformer` | `ghidra.program.model.symbol.IllegalCharCppTransformer`. |
| `line_separator` | Exact `StringUtilities.LINE_SEPARATOR`; first profile allows LF or CRLF only. |
| `source_manifest_sha256` | Hash of canonical `SourcePin[]`. |
| `tool_manifest_sha256` | Hash of canonical `ToolManifest`. |

`pass_id = SHA256(canonical(PassRecord))`. This is a content identity, not proof that a call happened. The producer must take the high function, markup, ordinary analyzed roster, and ordinary C from one `DecompileResults` object. It must verify that `HighFunction.getFunction()` is the ordinary function. It may construct a printer from that result's markup. It must not decompile again or reconstruct links from a later result.

`ToolManifest` has exactly `{tools_lock_sha256, ghidra, jdk}`. `ghidra` has `{version, revision, archive_sha256}`. `jdk` has `{vendor, version, archive_sha256}`. The first values are `12.2`, the revision above, and `2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67`; JDK values are `Temurin`, `25.0.5+8`, and `36dc14d797aaff6d89aab302cd053fdba6207dfdcf772052fa7b023a94b0e857`. The frozen `tools.lock` hash is `72ad852e83058857db2b3a0336d3fc522fb4dd5f152d35fe105f3a9bc9538686`.

A runtime property is not an installation attestation. Before producer admission, independently verify the archive-to-installation chain, the source manifest, and the actual Java/native components used. Refuse changed or unmeasured installations. A matching string alone is insufficient. The pure reader only checks supplied data against the reviewed expected pins.

## 4. Graph schema 2

`ByteGraphV2` has exactly:

```text
schema, profile, binary_sha256, lift_sha256, function, pass_id,
raw_c_sha256, ram_space_id, ram_word_bytes, address_bits, byte_bits,
endian, entry, blocks, operations, values, raw_instruction_sites,
raw_operation_keys, explicit_volatile_sites, native_inventory, gaps
```

`schema=2`; `profile=ordinary-byte-adapter/1`. Binary, function, lift, pass, and raw C hashes must agree with the bound ordinary artifacts and pass. `ram_space_id` is the actual signed 32-bit Ghidra RAM space ID. `ram_word_bytes=1`, `address_bits=64`, `byte_bits=8`, and `endian=little`. No default value substitutes for a missing field.

`entry` has exactly `{ordinary_entry, analyzed_block, selection, native_entry_address}`. `ordinary_entry` is an `Address` equal to the listing function entry in the actual RAM space. `analyzed_block` is the actual `BlockKey` for index 0. `selection=pinned_native_index_zero`. `native_entry_address=null`, because this API path does not export native `getEntryAddr()`. This null is mandatory in adapter version 1. Neither cover endpoint replaces it. If no actual block 0 exists, the graph member is refused.

`blocks` contains every decoded basic block in native index order. Each `BlockV2` has exactly:

```text
id, cover_min, cover_max, incoming, outgoing, operations
```

`cover_min` and `cover_max` are actual `Address` results or both null for an empty cover. One null and one address refuse. Non-null endpoints must use the same space and ordered offsets. They are inclusive cover extrema, not half-open source spans. No complete cover range is inferred. `incoming` and `outgoing` contain every `EdgeSlot` in actual API slot order. `operations` contains the block's ordered analyzed `OpKey` list, possibly empty.

Block indices need not be remapped to a dense new identity. However, this profile requires that the decoded Java list have no null holes and that its slot and block index agree. A null hole refuses the graph with `block_inventory_unavailable`. Do not filter the list. Preserve unreachable blocks and empty blocks. A derived reachability set can use recorded edges from entry; it is never a reason to omit a block.

For each outgoing slot `(A, i)` naming `(B, j)`, `B.incoming[j]` must name `(A, i)`. Check the reverse direction too. Keep parallel edges and self-loops. Predecessor identity alone is insufficient for a phi input. Pair `MULTIEQUAL.inputs[k]` with its owning block's incoming edge slot `k`. Preserve that order and require the arities to match. If the API gives a different arity, retain the operation and add `phi_binding_unproved`; do not reorder or trim. Branch interpretation is derived later from the ordered outgoing list and actual terminal opcode. The pinned API calls slot 0 false and slot 1 true for a two-way block (`PcodeBlock.java:312–322`). This is not a raw-branch proof. A graph record does not add guessed branch labels to other edges.

`operations` contains the entire Java operation-bank iteration in its actual sequence order. Each `OperationV2` has exactly:

```text
id, opcode, output, inputs, java_is_dead, parent, java_order
```

`id` is analyzed-domain `OpKey`. `opcode` is the actual mnemonic, a nonempty ASCII identifier of at most 64 bytes. `output` is a `ValueKey` or null. `inputs` is the full ordered value-key array; repeated slots remain repeated. Null inputs refuse this profile. `java_is_dead` is the actual Boolean. `parent` is the exact same-call `BlockKey` or null. `java_order` is the signed 32-bit sequence order from Java. A block-owned operation must appear exactly once in its parent's list, with matching zero-based order. An unowned operation must appear in no block list and carries `unowned_operation`. Every block member must exist in the bank. No operation is excluded for its dead Boolean.

For every bank operation, opcode, sequence, storage widths, output, and ordered operand storage must match the ordinary analyzed roster. Exact object associations are established in Java before serialization. The pure reader checks the stored relation against the bound lift. Do not resolve an ambiguous match by choosing the first storage match. The bank roster and ordinary analyzed roster must have equal key sets and equal records under this projection.

`values` is the full Java `locRange()` inventory in actual iteration order. Each `ValueV2` has exactly:

```text
id, storage, size_bytes, definition, bits, is_constant, is_input,
is_free, address_tied, persistent, unaffected
```

`storage` is `Address`; `size_bytes` is 1 through 65,536. `definition` is the exact analyzed `OpKey` or null. Every non-null definition must be in the bank and have this exact value as its output. Each non-null operation output must name its matching definition. `bits` is canonical unsigned hex for a constant and null otherwise. A constant must fit its width; this profile represents only constants exposed in the API's 64-bit offset. Other widths do not create high bits. All six flags are actual Java Booleans. Do not infer a flag from storage or a missing definition. A flag combination that does not support a unique input/constant/defined interpretation retains its actual flags and gets `ssa_unbound`. It does not receive an invented definition. Compare the full count to `getNumVarnodes()` during capture. Preserve unused values; the set is not limited to operation operands.

`raw_instruction_sites` contains every listing instruction address in ordinary lift order, including zero-operation instructions. `raw_operation_keys` contains every raw operation in instruction/slot order. Both must equal the bound lift roster. Do not substitute analyzed sequence sites. Complete instruction sizes, p-code, function ranges, listing blocks, and flow edges remain in the bound lift; the adapter does not duplicate them. Apply the graph's raw/listing bounds to those referenced records too.

`explicit_volatile_sites` contains unique raw or analyzed operation keys with direct positive volatility observations. It is not an exhaustive negative volatility certificate. Preserve the old producer's direct memory-block observations under their source pin. An empty list does not mean nonvolatile. Java `setVolatile` is a no-op at the pin (`PcodeSyntaxTree.java:345–347`).

`native_inventory` has exactly four fields, all fixed strings:

```text
operation_flags = not_exported
operation_bank = not_exported
removed_operations = not_exported
block_cover_ranges = not_exported
```

These facts require global gaps `native_state_unavailable`, `native_inventory_unavailable`, and `native_cover_unavailable`. `entry_effect_binding_unproved` and `memory_effects_unproved` are also mandatory global gaps. They prevent a structurally well-formed graph from appearing semantically closed. Version 1 has no field that can assert these proofs passed.

## 5. Gap records and refusals

`GapV2` has exactly `{code, block, operation, value, item_ordinal}`. The four references are nullable. Non-null references must resolve in this record's scope. `item_ordinal` is allowed only in a source record and must resolve there. Global gaps have all four references null. Gap arrays are unique, sorted by canonical record bytes, and bounded. Limits do not permit dropping a gap.

The exact code set is:

```text
native_state_unavailable, native_inventory_unavailable,
native_cover_unavailable, entry_effect_binding_unproved,
memory_effects_unproved, unowned_operation, ssa_unbound,
phi_binding_unproved, cfg_unclosed, unsupported_opcode,
volatile_or_unknown_memory, source_unbound, interface_unproved
```

The reader checks all mandatory structural gaps. Producer-specific positive observations can require additional gaps, but cannot delete mandatory ones. Unknown opcodes can be retained as observations with `unsupported_opcode`; they cannot enter an effect checker. A source grammar or interface consumer must independently refuse unsupported structure, even if the gap list is empty at its own level.

Malformed JSON, duplicate identities, foreign keys, broken reciprocal edges, contradictory parent/list membership, definition mismatch, mismatched bound lift data, or byte partition errors are format refusals. They are not recoverable by adding a gap. An unobservable API value, absent decompile result, unsupported profile, or exceeded bound produces an explicit unavailable member at the adapter envelope. It never produces a truncated “complete” member.

## 6. Source schema 2

`ByteSourceV2` has exactly:

```text
schema, profile, function, pass_id, lift_sha256, graph_sha256,
raw_c_sha256, raw_c_bytes, source_status, inventory_scope,
lines, items, gaps
```

`schema=2`; profile and scope keys must match the graph and pass. `graph_sha256` hashes the accepted graph's canonical bytes. `raw_c_bytes` is the actual byte length. `source_status=exact_printer_bytes`. `inventory_scope=post_pretty_printer`. This type represents a full successful capture only. An unavailable source is represented outside it, not by an empty `items` array with a success label.

`LineV2` has exactly `{ordinal, api_line_number, indent, indent_span, first_item, item_count, separator_span}`. `ordinal` is 0-based and contiguous. `api_line_number` is the actual API value and must equal `ordinal+1` at this pin. `indent` is the actual nonnegative number of single ASCII spaces. `indent_span` is a `Span` containing exactly that many spaces. `first_item` is the first global item ordinal. `item_count` is the actual item count, at least one after the pinned padding step. `separator_span` contains the exact pass `line_separator`. It is nonempty, including on the last line.

`ItemV2` has exactly:

```text
ordinal, line_ordinal, ordinal_in_line, kind, syntax_type,
original_text, rendered_text, render_rule, association_rule, span, text_sha256,
operation, value, formal_ordinal, symbol_storage
```

The three ordinals are actual positions after printer flattening and padding. Global ordinals and per-line ordinals are contiguous and 0-based. `kind` is the actual simple Java class name, a nonempty ASCII identifier at most 128 bytes. It is not a guessed token class. `syntax_type` is the actual integer 0 through 10. The exact allowed classes are `ClangVariableToken`, `ClangOpToken`, `ClangSyntaxToken`, `ClangFuncNameToken`, `ClangTypeToken`, `ClangCommentToken`, `ClangLabelToken`, `ClangFieldToken`, `ClangBitFieldToken`, and `ClangCaseToken`. `ClangBreak` is consumed into line records by the printer. An unknown subclass or a break left in the item list requires `printer_class_unavailable`.

`original_text` is the exact `token.getText()`. `rendered_text` is the exact string used by the pinned rendering rule. `render_rule` is `identity` or `illegal_char_cpp`. The latter applies precisely to the five classes in `PrettyPrinter.java:98–100`, except `CONST_COLOR=5`. Use the pinned transformer itself in Java. Do not substitute a Python Unicode character predicate for Java `Character.isLetter(char)`.

The pure reader checks the class/syntax choice, exact equality for `identity`, and the rendered-byte partition. For `illegal_char_cpp`, it retains the original/rendered pair as a producer observation. It does not claim that a cross-language reimplementation authenticated that transformation. Producer admission requires independent pinned-Java controls for it. A later grammar consumes the checked rendered bytes. It cannot use unverified original text as an identifier or infer a semantic name.

`span` can be empty. Its exact byte slice must equal strict UTF-8 of `rendered_text`. `text_sha256` is SHA-256 of that slice, including SHA-256 of empty bytes for an empty item. Preserve empty items with their actual `kind`. Do not claim that every empty item was a pad spacer: no such origin tag is exported. Do not merge neighboring whitespace or comments.

`association_rule` is one of three fixed rules. `direct_api` applies to all allowed classes except field and case tokens. Use their direct reference getters; base-class nulls remain null. `field_output` applies only to `ClangFieldToken`. Its value is the actual output of its directly referenced operation, as implemented by `getVarnode()` at `ClangFieldToken.java:50–58`. An absent field operation refuses the source member rather than causing an unchecked null dereference. `case_op_only` applies only to `ClangCaseToken`. Keep its direct operation reference, set value and formal to null, keep storage empty, and require an item-specific `source_unbound` gap. Do not call its value or symbol getters: `ClangCaseToken.java:67–99,121–136` derives those through the first matching predecessor. The null in this explicit rule means no direct value observation, not an observed null return from that search. `ClangBitFieldToken` extends `ClangToken`, not `ClangFieldToken`; it uses `direct_api` and identity rendering.

`operation` is an analyzed `OpKey` or null, from the permitted direct `getPcodeOp()` reference. `value` is a `ValueKey` or null under the rule above. Non-null keys must name the same-call bank objects. A source-only value is allowed because the graph retains the full Java value bank. A foreign non-null referent refuses the source member. No address, spelling, proximity, or adjacent item supplies a replacement link.

`formal_ordinal` is null or an actual parameter symbol category index from 0 through 127. For `direct_api`, use `getHighSymbol(null)`; for field tokens the pinned base implementation returns null. Do not call it for `case_op_only`. A direct symbol can exist without an operation or value link. That does not justify adding one. `symbol_storage` is an ordered array of direct symbol-storage pieces. Null symbol means null formal and an empty array. A non-null symbol with bad, void, unassigned, absent, or oversized storage refuses the source profile. Do not infer a signature from these observations.

Each `StoragePiece` has exactly `{address, size, register, stack_offset}`. `address` is `Address`; `size` is 1 through 8192 bytes. The interval must not wrap 2^64. `register` is null or the exact direct `program.getRegister(address,size)` name, 1 through 256 UTF-8 bytes. `stack_offset` is null or a signed 64-bit integer. In stack space it is required, congruent to the unsigned address modulo 2^64, and cannot cross zero or the signed upper bound. A stack piece has no register name. Non-stack pieces have null stack offset. Keep ordered pieces, including repeated storage. Storage equality grants no value identity or alias proof.

The byte partition is strict. Start at offset zero. For every line, consume its indentation, every item in order, and its separator. The next segment starts at the preceding end. Finish at `raw_c_bytes`. Every source byte belongs to exactly one nonempty segment. Zero-width segments are permitted only for items and indentation. Ordinals preserve zero-width multiplicity. Zero lines and zero items are permitted only when the actual printer lists are empty and `raw_c_bytes=0`; require a global `source_unbound` gap because no function source exists. This is different from an empty line with a spacer and a separator. Do not add a line to empty markup. Do not fill a missing prefix, suffix, separator, or indentation with guessed trivia.

UTF-8 offsets must be scalar boundaries. CRLF counts as two bytes. A supplementary Unicode scalar counts as four UTF-8 bytes, not two UTF-16 code units. The transformer can change the rendered length; offsets use rendered bytes only. Keep combining characters and normalization forms exact. Embedded newlines in token text stay in that item; API line boundaries come from the line inventory. Original and rendered token text are each bounded, independently of raw output size.

## 7. Checked positive-span view

`PositiveSpanView` has exactly `{source_sha256, tokens, projection}`. It is a computed immutable value, not another trusted source. `tokens` use the existing positive `SourceToken` shape: `{ordinal, span, kind, text_sha256, operation, value, formal_ordinal, symbol_storage}`. Every span is nonempty. Its ordinal is contiguous in this view.

`projection` has one `{item_ordinal, positive_ordinal}` row for every complete item. An empty rendered item has `positive_ordinal=null`. Every nonempty rendered item has exactly one positive ordinal. Those ordinals increase by one in item order. Copy every other token field exactly from the complete item. This includes whitespace and comments with positive spans. Indentation and separator segments are line trivia, not invented tokens. They remain in the source record and are checked by its hash and partition.

The projection checker first revalidates the supplied source and graph against the bound bytes. A directly constructed typed object does not bypass validation. It then recomputes this map and all token fields. It rejects a missing empty row, missing positive item, duplicate ordinal, reordered item, altered link, altered storage, or altered interval. The view retains its binding to the complete source, including `association_rule` and gaps. It cannot stand alone. Never silently reindex an old token file. Never write schema 1 merely because this view has the old field shape. The old parser's graph requirement and all its other rules still apply to an actual old artifact.

## 8. Diagnostic envelope and context

`AdapterContextV1` has exactly `{schema, profile, binary_sha256, sources, tools, limits}`. `schema=1`; profile is fixed. `sources` is the full `SourcePin[]`; `tools` is `ToolManifest`; `limits` has every named bound below. It contains no caller-supplied success flags. The producer measures its sources and runtime and compares them to this reviewed context. Merely accepting a caller's context is not source verification.

`AdapterObservationV1` has exactly `{schema, profile, binary_sha256, lift_sha256, mapping_sha256, context_sha256, functions}`. `schema=1` is this new envelope's version. The first draft uses null `lift_sha256` and `mapping_sha256`, because final ordinary files do not yet exist. Its graph/source `lift_sha256` and source `graph_sha256` are also null. No other final-required field becomes optional in the draft. A strict draft parser accepts only that draft form. The pure conversion step binds the completed ordinary files, fills the lift hashes, computes each final graph hash, binds its source to that graph, and then passes the final reader. Pass identity does not depend on those later file hashes.

Each function member has exactly `{function, pass, pass_id, graph_status, graph_reason, graph, source_status, source_reason, source}`. Functions match the complete ordinary roster, in the same order, with no duplicates or omissions. A present graph has `graph_status=observed_with_gaps`, null reason, and an accepted schema 2 graph. An absent graph has `graph_status=unavailable`, a refusal reason, and null graph. Source status is `observed` or `unavailable`; observed requires an accepted schema 2 source, null reason, and a present graph. Source absence does not erase a valid graph. Neither status permits production use.

Refusal reasons are the finite strings `decompile_unavailable`, `profile_mismatch`, `entry_unavailable`, `block_inventory_unavailable`, `operation_inventory_unavailable`, `value_inventory_unavailable`, `source_link_unavailable`, `printer_bytes_differ`, `printer_class_unavailable`, `invalid_unicode`, `region_limit`, and `graph_unavailable`. Whole-bundle format, pin, hash, roster, or I/O failures are structured errors, not successful function gaps. Error classes are `format`, `limit`, `pin`, `binding`, and `io`; each has a bounded human-readable message. Do not copy process logs into an error artifact.

The draft is not a final observation. Never accept draft null bindings in the final reader. No partial file is a published generation. No old publication selector points to these files.

## 9. Bounds and resource behavior

These are hard maxima. A caller may lower a positive bound. It cannot raise one, use zero, use a Boolean, or omit a bound. Apply aggregate byte limits before parsing. Apply JSON depth and array limits during decoding where possible. Do not advertise these wire limits as a complete process-memory limit.

| Bound name | Maximum |
|---|---:|
| `max_program_bytes` | 16 MiB |
| `max_lift_bytes`, `max_mapping_bytes` | 64 MiB each |
| `max_companion_bytes` | 16 MiB for the whole draft or final envelope |
| `max_bundle_bytes` | 160 MiB, sum of program, lift, mapping, and companion |
| `max_functions` | 32 |
| `max_graph_bytes`, `max_source_record_bytes` | 16 MiB each, also subject to the whole-envelope cap |
| `max_blocks`, `max_listing_blocks` | 32 per function each |
| `max_operations`, `max_raw_operations` | 256 per function per domain |
| `max_raw_instructions` | 256 per function |
| `max_inputs` | 256 per operation |
| `max_values`, `max_references` | 65,792 each per function |
| `max_edges` | 1024 directed edge occurrences per graph; reciprocal storage counts as the same edge |
| `max_gaps` | 256 per graph or source |
| `max_source_bytes` | 1 MiB per function |
| `max_items`, `max_lines` | 65,536 each per function |
| `max_original_text_bytes`, `max_rendered_text_bytes` | 1 MiB each in aggregate per function |
| `max_storage_pieces` | 4 per item |
| `max_context_bytes` | 64 KiB |
| `max_source_pins` | 32 |
| `max_json_depth` | 32 |

Indentation is at most `max_source_bytes` spaces and must also fit the source partition. All arrays, counts, and accumulated widths use checked arithmetic. Per-domain reference totals count repeated input slots and outputs. Graph bank values are independently bounded; unused values do not escape limits. The full-envelope cap includes original and rendered text duplication.

On a per-function capture limit, return an unavailable member with `region_limit`; do not return a prefix inventory. If the full function roster, context, or bundle exceeds a bound, refuse the whole bundle. Bounded raw bytes do not alone bound Ghidra memory, logging, or runtime. Process supervision, I/O failure handling, and log caps need their own implementation and independent controls. The existing F1 correction is outside this design's certification.
