# Bounded implementation plan

No work in this plan ran during this design review. PASS-to-implement permits only the named bounded work. It does not admit a producer, approve an effect proof, or enable production. The root must retain the separate resource and review gates.

## 1. Units and exact file scope

Use an isolated implementation worktree under `$PHOENIX_ROOT/worktrees/`. Do not edit the frozen inputs or the read-only worktree used for this review. Do not use a native Ghidra patch for this adapter.

| Unit | Decision | Files that may change | Exit evidence |
|---|---|---|---|
| A. Graph schema 2 | PASS-to-implement | New `phoenix/lift/byte_graph_v2.py`; new `tests/test_byte_graph_v2.py` | Strict pure reader, canonical serializer, complete bank and identity controls; old graph tests unchanged |
| B. Source schema 2 and positive view | PASS-to-implement after A | New `phoenix/lift/byte_source_v2.py`; new `tests/test_byte_source_v2.py` | Complete byte partition, empty-item preservation, exact association rules, independent projection controls |
| C. Same-call Java capture | PASS-to-implement after A and B | New `ghidra_scripts/OrdinaryByteAdapter.java`; narrow changes in `ghidra_scripts/ExportLift.java` | New explicit selector; ordinary export unchanged; object identity and actual inventory controls |
| D. Pure draft conversion | PASS-to-implement after A and B | New `phoenix/lift/byte_adapter.py`; new `tests/test_byte_adapter.py` | Strict context, pins, roster, draft/final distinction, ordinary lift and mapping bindings |
| E. Diagnostic test fixtures and design record | PASS-to-implement with A–D | New `tests/fixtures/byte_adapter_v1/` text JSON fixtures; new `tests/test_byte_adapter_public.py`; new `docs/adr/0041-ordinary-byte-adapter-v1.md` if that number is still unused | Public source provenance, no private material, explicit fixture purpose and expected refusals |
| F. Process supervision or shared launcher refactor | HOLD | No file authorized by this design | Separate narrow design and failure-injection review; do not copy the old launcher's F1 defect |
| G. Producer admission | HOLD | No admission registry or production path change | Independent review and actual pinned controls after A–E |
| H. Semantic consumers and publication | HOLD | No recover, generate, package, runtime-provider, or publication file change | Separate effect, grammar, interface, pointer, emission, and publication reviews |

Reserve ADR 0041 only at implementation time. If it is taken, use the next free number and record that choice. This is a filename allocation, not a change to the contract.

Keep `byte_graph.py`, `byte_source.py`, `byte_export.py`, `mapping.py`, and `OrdinaryByteEvidence.java` exact for these units. Read-only reuse of stable primitive validation is acceptable. Do not refactor the old graph/source reader through a common “lenient” reader. Do not change `ByteLiftGeneration`, old selectors, old canonical bytes, or publication versions 1–3.

`ExportLift.java` may add the new argument branch, a nullable new capture parameter, one same-result capture call, and diagnostic draft output. It may not change ordinary decompiler options, function ordering, ordinary lift contents, switch capture, or timeout. No second decompile call is allowed. Avoid a new general plugin architecture or callback framework for this single hook.

Unit D is pure conversion. It accepts supplied bytes and produces observation bytes. It does not run a process. The existing authorized public headless harness may invoke Unit C for controls when the root has resources. If a reusable launcher is needed, Unit F must close first. This keeps process I/O work separate from the three API/profile changes.

## 2. Order of work

1. Freeze the expected old-format fixtures and reader behavior. Record the exact implementation base and source manifest. Do not update an expected result merely because a new reader disagrees.
2. Implement Unit A. Start with independently constructed graph records whose expected structure is written before reader code.
3. Implement Unit B. Start with literal source bytes and manually enumerated line/item intervals, including empty items.
4. Review A and B before integrating a producer. Include an adversarial review of spoofed, internally consistent records. Confirm that no accepted record yields emission authority.
5. Implement Unit D against supplied draft and ordinary artifact bytes. Keep draft acceptance separate from final acceptance.
6. Implement Unit C using the exact pinned Java APIs. Capture both direct flags and object identities. Record the complete banks before source links are resolved.
7. Run independent pinned-Java printer and decode controls. Then run the named public E1 fixture under authorized resource control. Compare complete artifacts and all gaps.
8. Request the specified independent capture/producer review through the root's normal process only when that process is available. This delegate must not retry or replace the open full capture review.

Run ruff, formatting, strict mypy, and the relevant pytest tiers for each implementation change. Use property tests for schema round trips, strict rejection, byte partitions, and projection invariants. Keep the required coverage and pre-commit gates. Do not report a test count as producer or semantic approval.

## 3. Independent synthetic graph controls

Expected results must come from small hand-written cases and primary API rules. Do not use the new producer as the sole test oracle. Do not derive both the expected and actual record with the same helper.

| Control | Required result |
|---|---|
| Ordinary entry differs from actual block-0 cover minimum | Both values remain exact; graph parses with mandatory entry gap; no entry is fabricated |
| Equal entry and cover minimum | Entry gap still present; no automatic semantic certificate |
| Empty entry block supplied by producer | Block retained with its actual cover state and no invented operation |
| Missing entry block or null Java block slot | Graph unavailable; no list filtering or index shift |
| Disconnected and unreachable blocks | Every block and operation retained; reachability is derived separately |
| Multiple native cover ranges | Only observed extrema stored; no inferred continuous interval or `getEntryAddr` value |
| Block-owned Java `isDead=true` | Boolean retained; ownership accepted structurally; native state still unknown |
| Block-owned Java `isDead=false` | Boolean retained; no stronger native or semantic claim |
| Unowned bank operation | Full record retained, parent null, explicit gap; no `excluded_dead` conversion |
| Missing or duplicate operation; foreign parent; repeated ownership | Refusal |
| Two values with equal storage | Distinct keys retained and links remain distinct |
| Repeated input value in two slots | Both ordered slots retained |
| Unused or source-only Java value | Value retained in the complete bank |
| Foreign value definition or wrong output identity | Refusal |
| Raw and analyzed operations with equal sequence | Separate domains; no effect matching by sequence alone |
| Listing instruction with zero p-code operations | Instruction remains in the raw roster |
| Diamond phi, loop phi, two edges from one predecessor, self-loop | Inputs bind by incoming edge slot and reciprocal slot, not by sorted predecessor key |
| Permuted phi slots with the same value set | Stored ordering changes; semantic checker cannot treat the graph as identical |
| Phi/input count mismatch | Actual lists retained with `phi_binding_unproved`; no guessed slot |
| Missing reciprocal edge or wrong reverse slot | Refusal |
| Empty volatility list | No nonvolatile conclusion; mandatory memory gap remains |
| Coherent fabricated record and matching hashes | Reader may accept structure; no trusted producer or emission authority exists |

Exercise exact bounds and one-over bounds independently: blocks, both operation domains, raw instructions, references with repeated slots, unused values, directed edges, gaps, recursion, and bytes. Test integer overflow, signed and unsigned address edges, zero widths, duplicate JSON keys, invalid hex, wrong pass, wrong binary, foreign function, and all fixed profile constants.

## 4. Independent synthetic printer controls

The smallest literal control is a zero-indent empty line. Its raw bytes are one LF. It has one line, one empty syntax item at `[0,0)`, empty indentation at `[0,0)`, and separator `[0,1)`. The positive token view is empty, but the projection has one row with null positive ordinal. Deleting that row must fail.

Use a second control with an indented empty line. At this pin, the printer emits the line indentation and the spacer's indentation text. Preserve both contributions. Check the exact output with the pinned Java printer; do not assume a single indentation copy.

Additional required cases:

- Multiple empty items at one byte offset; empty items before and after a positive item; empty final line; spaces and comments as positive items.
- Empty markup with zero lines and zero source bytes. Preserve that distinct empty inventory and its `source_unbound` gap. Do not invent the one-line spacer case.
- LF and CRLF; missing final separator; changed indentation; a token containing an embedded newline; a line boundary that does not come from scanning bytes.
- ASCII, a two-byte scalar, a four-byte scalar, combining characters, two normalization forms, and isolated surrogates. Verify byte offsets by an independent UTF-8 encoder and literal expected byte arrays.
- Legal and illegal identifier characters; `CONST_COLOR` exemption; the five transformed classes; bit-field tokens that do not inherit field transformation; changed rendered lengths.
- Comment merging and consumed breaks. Claim post-printer completeness only. Do not expect a leaf-to-item bijection.
- A zero-width item with a direct link. Preserve its link in the full record even though its positive ordinal is null.
- An actual null link, a foreign non-null object, equal-storage distinct objects, a source-only value, a direct parameter symbol, bad storage, and compound storage with repeated pieces.
- A case token with two possible predecessor switch operations. Preserve its direct operation link. Do not call the predecessor-derived value/symbol getters. Require `case_op_only` and its item gap.
- A field token without a direct operation. Return a controlled source refusal. Do not swallow a null dereference and label the item exact.
- Source-span gaps, overlaps, split UTF-8 scalars, wrong digests, reordered ordinals, missing empty items, changed associations, changed projection map, and a positive-only list that looks plausible but omits trivia.

The pure reader tests cannot prove that Java emitted an item. Use a separate pinned-Java test fixture to construct or decode known markup and compare the actual printer's output, class list, syntax types, line numbers, and item count. That fixture is a future test, not a command to run in this design task.

## 5. Actual public controls

Use only the named public E1 fixture and its approved artifact set. Preserve its old six saved artifacts as reference data. The original hashes are in `report.md`. Do not read a private run to make the control easier.

The later capture must establish:

1. The ordinary lift and mapping remain unchanged under the new observation hook, apart from any explicitly reviewed provenance field outside their existing contract. If they differ, investigate before admission. Do not update the baseline silently.
2. The function roster remains the same 19 entries. A new profile refusal must name the exact missing fact or bound. Do not assume that all 19 will satisfy the new profile before measuring them.
3. For each of the nine old entry refusals, capture the actual ordinary entry, analyzed block key, and observed cover endpoints. Do not use this review's possible mechanisms as the expected actual values.
4. For the ten retained old graphs, every one of the 13 named operation identities still has its actual Java `true` flag and matching parent. The old `cfg_unclosed` artifacts remain unchanged. The new profile records the accurate native-state limitation instead of pretending that a flag was repaired.
5. Enumerate every post-printer item, line, indentation segment, and separator. Record actual counts and source bytes. The old output has no complete source observation and cannot serve as the full expected printer inventory.
6. Compare the new complete source to an independently inspected pinned printer output. Include zero-width item ordinals. Check all same-call references against the actual captured Java objects, not only serialized key equality.
7. Repeat the authorized public job and compare canonical artifacts, excluding no unexplained field. A reproducible result can still be wrong; retain the independent source and API checks.

E1 is a producer compatibility control. It is not a compiled byte-loop positive. Do not turn E1's graph acceptance or source capture into an idiom admission count.

## 6. Separate semantic and Linux gates

The original U5 design, ADR0036, and ADR0038 remain in force. This adapter only makes their evidence boundary representable.

| Gate | Evidence still required | Status |
|---|---|---|
| Entry relation | Invocation-to-analyzed-entry paths, raw prefix effects, initial live state, mapping and same-pass binding | HOLD |
| Raw/analyzed effects | Every raw instruction and effect accounted for; complete analyzed inventory; no unmatched reads, writes, calls, direct memory operands, stack traffic, or implicit effects | HOLD |
| Native facts | Direct native state/bank evidence if a proof depends on it; absent facts stay unavailable | HOLD |
| Loop and scalar semantics | Guards, zero-trip path, widths, count recurrence, dominance, ordered phi inputs, exits, and exact operation semantics | HOLD |
| Source grammar | Complete finite C grammar over exact bytes; declarations, qualifiers, casts, body, and all side effects accounted for | HOLD |
| Callable interface | Actual callers and callee uses; return behavior; every formal including extra formals; no guessed prototype from storage or printed text | HOLD |
| Pointer proof | Object provenance and explicit valid-range conditions; correct overlap behavior; no guessed capacity, disjointness, or `restrict` | HOLD |
| Emission | Deterministic scalar fill/forward-copy replacement; active definition in the project; protected bytes; no unproved provider rewrite | HOLD |
| Public compiled positive | Real byte loops compiled with GCC and Clang at the required optimization and executable-format settings; no fabricated p-code substitute | HOLD |
| Linux execution | Authorized Linux environment; four compiler/architecture builds; original/rebuilt differential tests; emulator agreement where required; native CI cross-check | HOLD |
| Integrity | No original code embedding, runtime original execution, output memorization, or hidden-source access; active-definition mutation controls | HOLD |
| Replay and production | Replay with no provider call; reviewed publication contract; explicit production admission | HOLD |

The public positive should include fill and forward copy, zero and boundary counts, and overlap-sensitive copy cases. Preserve the actual forward-copy behavior. A test that only uses disjoint buffers does not justify `memcpy` or `memmove`. Reject extra side effects and unsupported forms in independent negative controls. The compiled positive and any execution belong to the later Linux gate. The private Author retains ownership of the current VM.

## 7. Review and completion rules

Ask the independent reviewer to find ways that inventories, source completeness, or semantic claims could be false while all JSON hashes still match. In particular, review Java object identity, native/Java flag confusion, null holes, duplicate storage, phi slots, printer transformation, zero-width items, and the checked positive projection.

A producer review must also cover file I/O, bounded logs, timeout and cancellation, no partial publication, stale outputs, pin verification, and interrupted cleanup. The separate F1 correction is not approved by this design. Full capture review remains OPEN after provider screening. Do not interpret this architecture document as a replacement review.

Preserve every SPEC §9 requirement in the root plan. M4, T0–T3 held-out reporting against every baseline, costs and failure taxonomy, staged publication, and `phoenix-eval --replay` all remain required. This adapter does not reduce them. No design count is a headline result.

Recommended next action: implement A and B only, with independent synthetic controls. Keep producer admission and production HOLD. Then complete the dependency gates in order.
