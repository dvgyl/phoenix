Phoenix needs verified completion through SPEC.md section 9. This review checks only the first U5 structural graph reader. It does not establish completion of U5 or Phoenix.

PASS for this bounded structural reader at `fbcdab586571170a80f7472475100e1083bc74d8`. Production U5 remains HOLD. I found no reproducible source defect that blocks this unit. This verdict follows source inspection and independent controls. A zero exit code alone did not determine the verdict.

| Review identity | Exact value |
| --- | --- |
| Worktree | `/Volumes/PhoenixWork/worktrees/m1-public-profile` |
| Branch | `agent/m2-byte-graph-reader` |
| Revision | `fbcdab586571170a80f7472475100e1083bc74d8` |
| Base | `20402bca8b27ff1d48250d03fce10385164b0c75` |
| Revision manifest | [revisions.json](revisions.json) |
| Final checks | [verification.json](verification.json) |
| Commands | [commands.md](commands.md) |

The local revision matches the manifest. The remote branch returned the same revision through `git ls-remote`. The supplied full-hook record reports `Phoenix quality checks ... Passed`. Its separate exit file contains `0`. These records satisfy the supplied hook and publication prerequisite for this revision. I did not run another full hook or push. The full hook can reach work outside this host-only review. I did not infer its underlying test count from the hook receipt.

I read AGENTS.md, SPEC.md, the requested poteto-mode skill, and the requested comment review reference. I used the Investigation workflow with direct source inspection. The user prohibition replaced every nested-model step. The fixed write boundary replaced repository task and progress writes. I read the approved U5 [design](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/design.md), [API](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/api.md), and [report](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/report.md). `throughput checkpoint: n/a, read-only investigation`.

The actual revision changes five files. It adds [byte_graph.py](/Volumes/PhoenixWork/worktrees/m1-public-profile/phoenix/lift/byte_graph.py), [test_byte_graph.py](/Volumes/PhoenixWork/worktrees/m1-public-profile/tests/test_byte_graph.py), and [ADR 0036](/Volumes/PhoenixWork/worktrees/m1-public-profile/docs/adr/0036-byte-graph-evidence.md). It appends to `docs/STATUS.md` and `docs/LOG.md`. I checked the actual diff and all new file contents. The old implementation remains unchanged. Both progress files are append-only relative to the base. The final worktree is clean.

| New file | Final SHA-256, equal to the approved parent hash |
| --- | --- |
| `phoenix/lift/byte_graph.py` | `f3f20ccbc92ad1cfeadf6912d8943871bf4e852d60008f2652d5f8f62b218bf3` |
| `tests/test_byte_graph.py` | `6b592763a51f7ee3e642cd9480ea725e883aa57bffa3897413398c1abe8a7d1e` |
| `docs/adr/0036-byte-graph-evidence.md` | `7ef43d2b49ce4551f7b5c19bf43d129307ef72079b7d939e68a1c9e07ed4ce38` |

I also inspected the actual old `phoenix/lift/__init__.py`, `index.py`, and `mapping.py`. The ordinary reader supplies the bound operation banks, source text, instruction roster, and storage/definition facts. It does not supply the missing producer facts listed below. The new reader does not change that boundary.

No model, nested agent, target, compiler, Docker process, VM command, or Ghidra process ran. Existing launcher tests used synthetic host scripts or test doubles. All review writes stayed in this audit directory or `/Volumes/PhoenixWork/tmp/m2-byte-graph-review-sol-20261112`. No sealed source, held-out input, archive, run artifact, Author output/history, session history, or pre-existing event/stderr/summary file was read. The guard remained enabled.

The initial pytest command attempted to traverse a sibling worktree despite the required `--rootdir` and `--confcutdir`. The guard blocked that access. The failure is preserved in [affected.log](affected.log). I then copied only the five named public test files into this audit directory. Their bytes match the repository files. The successful run collected those copies and imported production code from the exact worktree. It did not require a guard change.

The structural checks support the verdict as follows.

| Contract | Source and independent evidence | Result |
| --- | --- | --- |
| Frozen fields and exact wire schema | Frozen slotted records have the approved fields. Parsed children contain only records, tuples, and primitive values. `record()` returns fresh mutable containers. Controls add or remove a field at every object position. | PASS. Unknown and missing fields reject. Direct typed construction remains ordinary Python construction. |
| Canonical bytes and digest | `_canonical` uses ASCII, sorted keys, compact separators, `allow_nan=False`, and one final LF. The reader compares canonical bytes with the complete input. Independent wire bytes determine expected output and digest. | PASS. Alternative whitespace, key order, escapes, BOM, UTF-16, missing/extra LF, duplicate keys, NaN, infinity, deep nesting, and invalid Unicode reject. Valid Unicode scalar text uses canonical escapes. |
| Profile and exact types | Schema, RAM word width, address width, byte width, and endian are fixed. Numeric fields use exact integer validation. Flags require exact Booleans. | PASS. Independent controls cover integer/Boolean/float substitutions, numeric maxima, invalid limits, and invalid text. |
| Binary, lift, function, pass, and source identity | The outer function must exist at the exact lift entry. Binary and lift digests must agree. Raw C must be available and hash as exact UTF-8 bytes. Every nested key must agree with the graph function and pass. | PASS for consistency with supplied lift facts. Controls change every nested key scope, source bytes, source status, and outer identity. The pass digest is not authenticated. |
| Operation domains | Raw and analyzed keys retain distinct domains at equal sequences. Active operations and value definitions require analyzed keys. Gap and volatile keys resolve against their declared domain. | PASS. Equal raw/analyzed sequences do not collapse. Domain substitutions reject where they contradict the contract. |
| Complete analyzed operation bank | Active operations and excluded operations form a disjoint, complete partition of the ordinary analyzed bank. Duplicate ownership and missing records reject. Unreachable blocks and excluded records count toward limits. | PASS for the old bank. The reader cannot authenticate whether an exclusion is actually dead. |
| Ordered operands and output identity | Active opcode, sequence, input count, ordered storage, width, and definition sequence must agree with the ordinary operation. Every defined value must be the exact active producer output ID. The value roster is exactly the union of active inputs and outputs. | PASS. Missing values, extra values, reordered operands, wrong storage/width/definition, equal-storage output substitution, and dead-producer use reject. Distinct IDs can retain reused storage. |
| Blocks, edges, and phi operands | Block IDs are unique. The entry start equals the function entry. Block starts are in function ranges. Edges resolve and have exact reciprocal slots. Parallel edges reject. Phi operations form a prefix and have one output and one operand per incoming slot. | PASS for supplied structure. Phi operand reversal alone rejects against the old ordered operands. A coherent predecessor/operand permutation with matching lift facts preserves order. Actual analyzed membership and edge order remain producer proposals. |
| Conditional shapes | A block with CBRANCH has one terminal CBRANCH, two inputs, no output, and two outgoing slots. False and true slots are zero and one. Other blocks have null polarity slots. | PASS. Independent controls make each malformed shape agree with the old operation bank before testing rejection. General control-flow semantics remain a later check. |
| Complete raw instruction roster | The graph roster must equal the complete ordered ordinary instruction tuple. Raw operations remain in the old bank. Sites without p-code still count. | PASS. Missing, additional, duplicated, and reordered sites reject. Raw/analyzed sequence collisions remain distinct. |
| Volatile and gap references | References must exist. Duplicate references and duplicate gaps reject. A gap that names both a block and operation must name that block's active operation. The finite gap codes carry no emission authority. | PASS. Raw and excluded operation references work with null blocks. Empty arrays do not authenticate absence of volatility or gaps. |
| Limits and failures | Byte size is checked before JSON parsing. Complete bank, value, reference, input, instruction, block, edge, volatile, and gap bounds are finite. Caller reductions remain effective. Format and limit exceptions derive from ByteGraphError. | PASS. Controls cover inclusive lower limits, invalid/raised limits, 32/33 blocks, 256/257 operations, instructions, active inputs, and gaps. Omitted wire records cannot hide oversized ordinary banks. Both operation domains can retain their separate full budgets. |

The independent controls are in [test_independent.py](test_independent.py). They construct a separate ordinary lift document and graph wire object. They call the real `parse_lift` on synthetic public bytes. They do not use the worker's graph fixture, typed record constructors, or serializer to construct expected wire objects. Their fixture includes repeated storage with distinct definitions, phi backedges, a conditional, an unreachable empty block, a dead operation, and raw/analyzed sequence collisions.

The final independent suite passed 651 pytest cases. It includes 171 foreign-scope cases and 380 closed-object cases. One additional test makes 7,632 JSON-node replacements across all 636 nodes of its independent wire object. The replacement test accepts only a checked round trip or ByteGraphError. No other exception escaped in these controls. These internal replacements are not 7,632 additional pytest cases. None of these counts is a Phoenix evaluation result.

The following failures remain preserved. They are not source findings.

| Attempt | Actual result and exit | Cause and correction |
| --- | --- | --- |
| Initial affected collection | No tests ran. One collection error. Exit 4. | Pytest attempted sibling traversal. The guard denied it. Byte-identical public test copies kept collection inside the audit directory. |
| [Independent run 1](independent-1.log) | 621 passed, 7 failed. Exit 1. | Five controls encoded graph bytes before their helper updated the lift digest. Two controls supplied invalid data to the old reader before reaching the new reader. I corrected evaluation order and kept those invalid values in the graph-only controls. The initial test source remains in `independent-initial.py`. |
| [Independent run 2](independent-2.log) | 643 passed, 1 failed. Exit 1. | A one-byte malformed JSON input equaled its one-byte limit. The reader correctly returned a format error. I changed the control to use two bytes, so it tests byte-limit precedence. The second test source remains in `independent-second.py`. |
| [Independent run 3](independent-3.log) | 651 passed. Exit 0. | All final controls passed. Additional controls were retained after the earlier failures. |

The other executed checks have these results. Exact commands and output files are in [commands.md](commands.md) and [verification.json](verification.json).

| Check | Actual count or output | Exit |
| --- | --- | --- |
| [Affected host tests](affected-copied.log) | 542 passed, 2 deselected. | 0 |
| Observer test collection | 17 collected. These are the extra cases beyond the parent's 525-test group. | 0 |
| [Ruff check](ruff-check.log) | All checks passed for both new Python files. | 0 |
| [Ruff format check](ruff-format.log) | 2 files already formatted. | 0 |
| [Strict mypy, reader](mypy.log) | No issues in 1 source file. | 0 |
| [Strict mypy, reader and tests](mypy-affected.log) | No issues in 2 source files. | 0 |
| Final revision, branch, clean state, diff check, and remote checks | Exact reviewed revision. Clean worktree. Remote branch agrees. | All 0 |
| Final SHA-256 and append-only comparisons | All three parent hashes and all five copied test files agree. Both progress files retain their complete base prefix. | 0 |

The affected command explicitly excluded `test_headless_bitstats` and `test_public_phase_grid_storage`. No live test was treated as passed. The full hook receipt is separate supervisor evidence. It does not replace the host controls or source review.

No concrete defect with a reproducible control remained after review. Thus there is no severity-ranked correction request for this unit. I found no claim in ADR 0036 or the changed progress text that gives a parsed graph semantic authority. Their stated limitations agree with the implementation. The recorded 99 percent coverage is worker/parent evidence. I did not independently measure coverage and do not use it as approval evidence.

Maintainability is acceptable for this unit. The records, wire readers, count checks, and cross-reference checks have separate roles. The code uses existing lift types and bounded JSON helpers. There is no new pipeline path, global mutable state, bare exception handler, or target execution. Preflight and record parsing repeat some schema checks so bounds apply before record and index construction. This repetition serves the stated boundary. The docstrings define the public contract and its authority limit. I found no misleading explanatory comment or correctness suppression that needs removal. No comment or source file changed. There are no cosmetic requests.

Several acceptance controls deliberately show what this reader cannot prove. A coherent pass rename passes. A coherent unused-operation dead reclassification passes. Free/input status and the three flags remain proposals. Removing an empty analyzed block can pass because the old lift has no analyzed block roster. A different RAM space ID can pass. Clearing volatile and gap arrays can pass. These outcomes agree with the documented limit. They must remain explicit constraints on later consumers. A constructor, matching hash, or parsed graph cannot authenticate them.

The following gates remain open.

| Remaining gate | Required evidence |
| --- | --- |
| Producer | Export actual ordinary analyzed block membership and ordered edges. Retain varnode object identity, input/free flags, actual dead status, pass record, RAM identity, and known volatility. Check the pinned APIs with an actual public export. Bind a new companion publication atomically. |
| Recognizer | Check reachability, dominance, same-block order, predecessor availability, permitted recurrence, exact scalar widths, zero path, result, and complete raw/analyzed effects. Check aliases and input invariance. Structural parsing supplies none of these proofs. |
| Source and interface | Retain exact printer bytes and token/value/operation links. Parse the complete finite function grammar. Prove source correspondence and supported callable storage roles. Establish the required pointer and ordinary-memory contract. Prototype strings do not prove arity, pointer provenance, object capacity, or erased qualifiers. |
| Emitter and pipeline | Independently recreate checks before emitting a distinct protected byte definition. Bind the opt-in setting, source snapshot, resume, and replay. Preserve defaults and the raw baseline. Reject bypasses and alternate active definitions. |
| Actual public behavior | Prove compiled mechanism presence in the frozen GCC/Clang matrix. Run fill/copy, zero, overlap, return, sentinel, changed-effect, and inactive-definition controls. Run accepted independent oracles and required architecture/compiler builds. Run native CI and exact replay. The private Author still owns the VM. |
| Other independent work | The full capture review and collector production gates remain separate and open. This review neither retries provider-screened work nor certifies capture. |
| Milestones and SPEC section 9 | Complete and verify M2 through M4. Publish required baselines, ablations, corpus artifacts, costs, and failure taxonomy. Reproduce every headline with phoenix-eval replay. None of these gates closes here. |

This PASS permits reliance on the bounded reader's structural contract at the exact reviewed revision. It grants no C emission authority, interface proof, recurrence proof, effect proof, live U5 result, or milestone result. Production U5 remains HOLD.
