# ADR 0036. Structural byte-graph evidence

Date: 2026-11-12.
Status: Implemented reader proposal. Production U5 remains HOLD.

## Scope

The first U5 unit reads one complete ordinary function graph. It adds immutable
records and a pure structural reader in `phoenix/lift/byte_graph.py`. It adds no
caller to the pipeline. It changes no existing reader, schema, exporter, or pin.

The implementation follows step 1 of the approved Astra U5 API contract.
It uses the actual `LiftIndex`, `Location`, `Sequence`, and branded `GhidraVA`.
It uses the existing bounded JSON helpers. Static prototype evidence remains
a proposal. The reader makes no type, pointer, original arity, or ELF inference.

A graph that passes this reader has structural consistency with the supplied
ordinary lift. It is not an authenticated live graph or a supported byte idiom.
No constructor, serializer, digest, or export gap grants authority to emit C.

## Wire choices

The top-level object has exactly the `ByteGraph` fields in the approved API.
Each nested object has exactly the corresponding record fields. Every field
is required, including fields whose value can be null. The wire has no hash
field for its own bytes. `ByteGraph.sha256` hashes the complete `to_bytes()`
result, including its final LF.

The first profile uses these rules.

- JSON uses ASCII bytes, sorted object keys, compact separators, and one final
  LF. The canonical encoding is Python JSON with `ensure_ascii=True`,
  `sort_keys=True`, `separators=(",", ":")`, and `allow_nan=False`.
  Alternative whitespace, key order, escaping, a byte-order mark, and trailing
  data reject. Non-ASCII text uses canonical JSON escapes. Text must have valid
  Unicode scalar values. Duplicate object keys reject before reconstruction.
- Addresses use lowercase minimal hexadecimal strings with a `0x` prefix.
  Zero is `0x0`. Addresses are unsigned 64-bit numbers. A `Location` uses
  `space` and `offset`. A `Sequence` uses `address` and `index`, as in the lift.
  A `FunctionKey.ghidra_entry`, a block start, and each raw instruction site
  use a hexadecimal string. These remain Ghidra addresses.
- Digests use exactly 64 lowercase hexadecimal characters. `pass_id` is an
  opaque digest. Every nested key must have the graph's function and pass.
  Raw and analyzed operation keys remain distinct when sequences are equal.
- `schema=1`, `ram_word_bytes=1`, `address_bits=64`, `byte_bits=8`, and
  `endian="little"` are required. `ram_space_id` is an unsigned 32-bit number.
  The reader preserves that ID. The old lift cannot authenticate its meaning.
- Sequence indices are in `0..1_000_000`, as in the ordinary reader.
  Value IDs are unsigned 32-bit numbers. Block indices are in `0..2**31-1`.
  IDs can have gaps. Their numerical order does not imply execution order.
- Value byte widths are in `1..65536`, within the existing operand bound.
  The later recognizer owns the narrower supported scalar widths. A constant
  uses kind `constant`, storage space `const`, and canonical hexadecimal
  `bits`. The bits equal the storage offset and fit the declared width.
  Wider storage can contain the same zero-extended 64-bit constant offset.
  This profile cannot express a constant offset larger than 64 bits.
- A value is `defined` exactly when it has a non-null analyzed definition.
  Other nonconstant kinds are `input`, `free`, and `unexplained`. They have no
  definition or literal bits. Definitionless values do not become inputs.
  All three flags use exact Boolean values and remain producer proposals.
- JSON integers must be exact integers. Booleans and floats are not integers.
  Unknown fields, unknown value kinds, unknown domains, and unknown gap codes
  reject. Unknown nonempty opcode text remains unsupported evidence for the
  later recognizer. This reader assigns it no semantics.
- Arrays retain their supplied order. The reader sorts no operations, edge
  slots, phi operands, value records, blocks, exclusions, volatile sites, or
  gaps. `raw_instruction_sites` equals the ordinary function's ordered tuple.
  `parse_lift` orders that tuple by ascending instruction address.

`record()` returns a fresh mutable JSON object. The graph itself contains only
frozen slotted records, tuples, and primitive values. No parsed dictionary or
list is retained. Direct construction is ordinary typed Python construction.
It does not run the reader or establish a checked authority.

## Bounds and failures

`ByteGraphLimits` has these maximum defaults. A caller can reduce each one.
Zero, negative, Boolean, float, non-integer, and raised limits reject.

| Field | Maximum | Scope |
| --- | ---: | --- |
| `max_bytes` | 16 MiB | Complete graph bytes, including LF. |
| `max_blocks` | 32 | Analyzed blocks and, separately, ordinary listing blocks. |
| `max_operations` | 256 | Complete analyzed bank, active plus excluded dead. |
| `max_raw_operations` | 256 | Complete raw operation bank. |
| `max_raw_instructions` | 256 | Raw instruction sites, including sites with no p-code. |
| `max_inputs` | 256 | Inputs per operation in both complete banks. |
| `max_values` | 65,792 | Distinct active value records. |
| `max_references` | 65,792 | Active input slots plus non-null output slots. |
| `max_gaps` | 256 | Structured export gaps. |

The value and reference maximum is `256 * (256 + 1)`. The reader also limits
the value count to `max_operations * (max_inputs + 1)`. Repeated input slots
count separately. Raw input references have the separate finite upper bound
`max_raw_operations * max_inputs`. Each incoming or outgoing edge list has
at most `max_blocks` slots. Parallel edges reject. Volatile references have
at most `max_operations + max_raw_operations` entries.

The separate instruction limit is a conservative routine profile choice.
It prevents an unbounded roster of instructions with no p-code. It does not
change the separate raw operation budget. Both raw and analyzed banks can
contain 256 operations in the same graph. Nothing is silently truncated.
The source byte and token limits belong to the future source reader.

The byte bound runs before JSON parsing. Array lengths and complete bank
counts run before graph records and reference indexes are built. The JSON
syntax tree itself remains bounded by the byte limit. All counts include
unreachable blocks and excluded dead operations where applicable.

`ByteGraphLimitError` reports invalid limits or exceeded count or byte bounds.
`ByteGraphFormatError` reports invalid encoding, invalid fields, and structural
contradictions. Both derive from `ByteGraphError`. Neither is a semantic
recognizer refusal. Neither returns a partial graph or source.

## Source comparisons and structural checks

Every function key must equal the graph's function key. That key must name
an exact function entry in the supplied lift and its binary digest.
`lift_sha256` must equal `LiftIndex.lift_sha256`. `raw_c_sha256` must hash the
ordinary function's exact UTF-8 raw C bytes. An unavailable source rejects.
The reader does not compare prototype strings to infer the interface.

Active operation IDs and excluded IDs form a complete, disjoint partition of
the ordinary analyzed bank. Duplicate ownership and missing records reject.
Active operations must match the ordinary opcode, sequence, output presence,
input count, and every operand's ordered storage, width, and definition.
Each defined value must name its exact active producer and output ID.
No active input can depend on an excluded definition. Distinct value IDs can
retain equal storage. Two IDs cannot both claim the same producer output.

The value roster is exactly the union of active inputs and outputs. It retains
unused active outputs but has no unreferenced records or dead-only values.
Excluded operations remain available in the bound ordinary bank. Their
operands and raw effects are not erased by the graph partition.

Block IDs are unique. The entry must exist and start at the function entry.
Each block start must be inside a function range. Every active operation has
one block owner. Every edge names an existing block and an in-range reciprocal
slot. Both slot directions must name each other exactly. Unreachable blocks
and empty blocks remain present. The old lift has no analyzed block roster,
so this reader cannot authenticate additional or omitted empty blocks.

A `MULTIEQUAL` occurs in the phi prefix. It has an output and one ordered
operand per incoming edge. A block with a `CBRANCH` has exactly one such
operation, at its end, with two inputs, no output, and two outgoing edges.
It explicitly declares false slot zero and true slot one. This is the pinned
API's conditional convention. A nonconditional block has null polarity slots.
The reader never derives polarity from block numbering or source layout.

## Structured export gaps

`ByteGap` has four required fields.

```text
ByteGap = {code, block: BlockKey | null,
           operation: OpKey | null, value: ValueKey | null}
```

The finite codes are `ssa_unbound`, `cfg_unclosed`, `unsupported_opcode`,
`volatile_or_unknown_memory`, `source_unbound`, and `interface_unproved`.
These codes describe missing producer evidence. They contain no source,
executable expression, policy, or permission field. References must resolve.
If both block and operation are present, the block must own that active
analyzed operation. A raw operation or an excluded operation can be referenced
with a null block. Duplicate gaps and duplicate volatile references reject.
Nonempty arrays remain data. Empty arrays do not prove an absence of gaps
or erased source qualifiers.

## Open semantic and production gates

The old lift cannot authenticate the pass record, actual varnode object IDs,
block membership, edge order, input/free flags, dead flags, or all volatility.
A coherent pass rename or dead reclassification can pass this reader. Tests
retain these limitations explicitly. The reader detects contradictions with
available facts. It cannot recover facts that the old export did not retain.

The recognizer still owns reachability analysis, dominance, same-block use
order, predecessor availability, recurrence validity, general opcode arity
and width rules, complete raw and analyzed effect relations, and result checks.
An ordered phi list alone does not prove that each value is available on its
predecessor. A valid conditional shape does not prove its branch predicate.
No liveness, alias, pointer provenance, object capacity, memory qualifier,
calling convention, or original arity claim follows from parsing.

The producer, exact source observations, finite source grammar, interface
checker, checked emitter, protected definition, and pipeline option remain
unimplemented by this unit. Independent source review and actual compiled
public tests remain required. The private Author retains the VM. Capture
review remains separate and open. M2 through M4 and all SPEC section 9
conditions remain open.

## Workflow choices

The fixed task scope replaces nested-agent and shipping steps from the
engineering skill. No other model or agent runs. The supervisor owns the
fresh independent Sol review, full quality checks, commits, and publication.
The Model the Domain principle selects the frozen key and graph records.
Boundary Discipline keeps validation at the reader boundary. The source
comparison remains a pure operation with no target execution.
