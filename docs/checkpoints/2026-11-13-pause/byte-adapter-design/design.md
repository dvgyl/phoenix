# Ordinary byte adapter: bounded design

Date: 2026-11-12. Decision: **PASS-to-implement for the observation adapter only.** Producer admission and all semantic and production gates remain **HOLD**.

This is a design review. No implementation, Ghidra job, compiler, VM, target, provider, or production path ran. `api.md` defines the proposed contract. `implementation-plan.md` defines the work units and their gates. `report.md` identifies the evidence and the limits of this review.

## 1. Decision and scope

Add one separately versioned observation profile: `ordinary-byte-adapter/1`. Select it only with `--byte-adapter-v1`. Give its graph and source records schema number 2. Implement their strict, pure readers first. Keep graph schema 1, source schema 1, the old diagnostic selector, and publication versions 1 through 3 exact.

The adapter observes one ordinary decompiler result. It keeps the ordinary function entry, the actual decoded entry block, all decoded operation and value records, and all post-printer items. It records missing native evidence as missing. It does not change Ghidra. It does not produce an idiom certificate or C replacement.

The smallest safe change needs a new graph contract. Graph schema 1 requires entry-address equality and classifies some operations as `excluded_dead`. Neither rule can carry the pinned observations without a change in meaning. A schema 1 object with different validation rules would be a hidden compatibility break.

Use source schema 2 for a single complete printer inventory. Derive a checked positive-span view from it. The view has the old `SourceToken` field shape. Its explicit ordinal map retains the connection to every complete item. It is not an old source artifact unless the caller also has a genuine, independently valid schema 1 graph and satisfies the old reader. Never make such a graph by changing an address or removing a flag.

The native bank is outside the observable scope of this adapter. The scope is the complete decoded Java bank, complete decoded block list, complete listing inventory in the bound ordinary lift, and complete post-`PrettyPrinter` inventory. These scopes must be named separately. The word “complete” must never mean native optimization history or machine-effect closure.

## 2. Actual public control

The approved saved E1 output contains 19 functions. Nine fail the old graph entry equality. Ten keep structural graphs but refuse source capture at an empty printer item. Those ten graphs contain 13 block-owned operations. Every one retains Java `isDead=true` and an explicit `cfg_unclosed` gap. There are zero complete source observations.

The parent proof reports an exact repeat of six saved artifacts. This review checked the saved artifact hashes and inspected their inventories. It did not repeat the Ghidra job. The counts are static diagnostic observations. They are not Phoenix evaluation results.

The nine rejected graphs are absent from the saved output. The output does not give their analyzed block starts. Thus, this review cannot identify each address difference or prove its cause. A later public recapture must do that. No graph or printer inventory can be recovered from these refusals by relabeling their records.

## 3. Entry identity and the binding still needed

The pinned `HighFunction` constructor saves `Function.getEntryPoint()` in `entryPoint`. Its decoder checks the encoded function address against that value. This binds the high function to the ordinary function. It does not require a block cover minimum to equal that address. See `HighFunction.java:61–71,247–293`.

Native `Funcdata::encode` writes the function base address separately from the block tree (`funcdata.cc:735–759`). Native `setStartBlock` puts the entry block first (`block.cc:1627–1660`). The spanning-tree code preserves the original entry first when it assigns indices (`block.cc:1019–1148`). Java imports the native block indices directly (`PcodeSyntaxTree.java:482–503`). The pinned profile can therefore name decoded block index 0 as the analyzed entry block. This is a pinned producer convention. It is not a Java entry-flag observation or a machine proof.

`PcodeBlockBasic.getStart()` returns the minimum of the cover. Native `BlockBasic::getEntryAddr()` has different logic for multiple ranges (`block.cc:2317–2353`). Therefore, the adapter records `cover_min`, `cover_max`, and the ordered operation list. It does not label `cover_min` as the original entry instruction. It records the native entry-instruction address and full native cover ranges as unavailable. A minimum and maximum must not be treated as one continuous range.

Native flow construction starts block ranges from p-code-bearing instructions (`flow.cc:978–1016`). It can also create an empty entry block when required (`flow.cc:823–844`). These are possible mechanisms behind different addresses. They do not diagnose the nine absent E1 graphs. Keep an empty block that Ghidra actually supplies. Never add one in the adapter.

The entry record therefore contains three different facts:

1. The ordinary function entry, which remains the `FunctionKey` identity.
2. The observed analyzed entry block identity, selected by the pinned index-0 convention.
3. The actual cover endpoints and first operation, each with its own meaning.

All graphs carry `entry_effect_binding_unproved`, even when the two addresses are equal. Before a later effect checker uses the graph, it must bind the binary identity, ELF-to-Ghidra mapping, listing function entry, same decompiler call, raw instruction roster, and analyzed entry block. It must then prove the initial state relation at that block. This includes every raw path from function invocation to the analyzed entry, its guards, its register and memory effects, and the origin of every live input. It must exclude or account for alternate entries, calls, exceptions, and omitted effects under the accepted input contract.

A numeric interval between two addresses is not that path. A first operation address is not that path. Matching addresses are not that proof. If the initial relation is absent, raw/analyzed effect closure refuses the candidate.

## 4. Java bookkeeping and native operation state

The actual decode chain is:

1. Native `Funcdata::encodeTree` emits blocks and the operations in each block (`funcdata.cc:683–725`). It does not emit the entire native operation bank or its dead list.
2. Native `PcodeOp::encode` emits opcode, sequence number, and operands (`op.cc:412–465`). It does not emit native operation flags.
3. Java `PcodeOp.decode` calls `PcodeSyntaxTree.newOp` (`PcodeOp.java:476–492`). That calls `PcodeOpBank.create` (`PcodeSyntaxTree.java:456–468`).
4. Java `PcodeOpAST` starts with `bDead=true` and `parent=null` (`PcodeOpAST.java:35–42`). Java bank creation adds the object to `deadList` (`PcodeOpBank.java:60–68`).
5. Java block decoding calls `bl.insertEnd(op)` (`PcodeSyntaxTree.java:493–496`). Insertion sets the parent and iterator (`PcodeBlockBasic.java:89–94`). It does not change `bDead`.

There is a further distinction: Java `PcodeOpBank.markAlive` moves a list item but does not clear `bDead` (`PcodeOpBank.java:83–93`). Native `PcodeOpBank::markAlive` does clear its native dead flag (`op.cc:1056–1065`). Native `Funcdata::opInsert` calls that method before block insertion (`funcdata_op.cc:150–173`). These implementations do not give the same meaning to the Java Boolean and the native flag.

The new operation record retains the actual Java Boolean and parent. It never converts `true` to `false`. It records native state as `not_exported`. Block ownership proves only decoded membership under this source pin. It grants no authority to assume a memory effect, remove an operation, or accept a machine-to-analyzed transformation.

Store the complete Java operation bank once. Blocks refer to its keys in actual iterator order. An unowned operation stays in that bank with `parent=null` and a gap. There is no `excluded_dead` field in schema 2. Reconcile the bank exactly against the ordinary analyzed roster from the same result. A missing, repeated, or foreign object is a refusal. Do not create a reduced “live” bank.

Keep the full Java value bank from `locRange()`, including unreferenced and source-only values. Use object identity during capture. Keep distinct IDs for equal storage. Native serialization and Java decode do not make every Java value ID a native identity: `Varnode.decode` can create values for `SPACEID` and `IOP` operands (`Varnode.java:388–413`). The key is a local Java value identity, scoped to this pass.

The ordinary listing remains the raw inventory. It includes instructions with zero p-code operations. The adapter binds every raw instruction and operation to that lift. It does not assert that Java analyzed operations account for every raw effect. Native removed and dead operations are not available through this export. Direct storage operands, stack traffic, calls, implicit state, volatile effects, and raw operations removed by optimization still need explicit treatment in the later effect proof. No native-dead claim can discharge them.

This raw inventory is complete relative to the bound ordinary listing. It does not prove that Ghidra found every machine instruction, function extent, or possible entry. The later proof must establish those boundaries from the binary and mapping. It cannot use listing completeness as a substitute for execution-path closure.

This adapter does not add native instrumentation. A future request for a full native bank, dead flags, removed-operation history, or a transformation certificate requires a separate native producer design and review. In its absence, retain the native-inventory gap. A later raw-effect proof must establish its claims independently or refuse.

## 5. Printer inventory and exact source bytes

`PrettyPrinter` flattens lines and pads empty lines. The padding item is a `ClangSyntaxToken`; zero indentation can give it empty text (`PrettyPrinter.java:49–66`; `ClangToken.java:264–269`). Filtering it loses an item and changes all later ordinals.

The printer writes indentation, every token in order, and a line separator for every line (`PrettyPrinter.java:84–113`). Empty indented lines can contain both the line indentation and a spacer with indentation text. Preserve both. Do not deduplicate whitespace.

There is a second printer compatibility requirement. `DecompileResults.getDecompiledFunction()` uses `IllegalCharCppTransformer` (`DecompileResults.java:202–209`). Passing `null` to `PrettyPrinter` uses the identity transformer. The new collector must use the same transformer and class/syntax rules as the ordinary producer. It must compare its complete output with the exact ordinary C bytes. Store original token text and rendered token text separately. Never find intervals with substring search.

The source record contains all post-printer items, all line records, the exact indentation spans, and all separator spans. Item intervals can be empty. Ordinals, rather than offsets, distinguish repeated empty items. UTF-8 byte offsets cover the entire ordinary C string without a gap or overlap. Empty items do not consume bytes. The inventory does not split a token merely because its text contains a newline.

The exact scope is post-`PrettyPrinter`, not original native markup leaves. `DecompilerUtils.toLines` consumes break items and can merge comments and whitespace (`DecompilerUtils.java:754–840`). Line records preserve the resulting line boundaries and indentation. This adapter does not claim a one-to-one map to consumed markup leaves. A native markup inventory would need a separate contract.

Keep token operation and value links only when the getters return the exact same-call objects. Keep a formal ordinal only from a directly associated parameter symbol. Use `getHighSymbol(null)` to disable the address-based fallback. Storage is a direct symbol-storage observation. It does not identify a value by equality of addresses. Null links remain null. A foreign non-null link causes a source refusal. Do not replace it with null.

Inspect the getter before calling it. `ClangCaseToken.getVarnode()` searches predecessors and takes the first matching switch operation (`ClangCaseToken.java:67–99,121–136`). That is not a direct decoded value reference. The adapter keeps the item and its direct operation link. An explicit `case_op_only` rule leaves its value/formal/storage association unobserved and adds `source_unbound`. Field tokens use their direct operation's output and label that rule separately. `ClangBitFieldToken` is not a subclass of `ClangFieldToken`; it does not inherit the field render rule. The API contract records these distinctions.

## 6. Alternatives

| Alternative | Benefit | Defect or cost | Decision |
|---|---|---|---|
| Change schema 1 entry equality and ignore Java dead flags | Small diff | Changes the old meaning; hides evidence; lets old consumers accept new claims | Reject |
| Rewrite block start or insert an entry block | Satisfies old equality | Fabricates a graph fact and loses the actual observation | Reject |
| Clear `bDead` or remove all flagged operations | Simple downstream graph | Changes actual Java data; can remove every retained E1 operation | Reject |
| Patch native Ghidra to emit flags, full covers, and native banks | More direct native evidence | New tool build and protocol; larger trust and review scope; still no automatic raw-effect proof | Defer |
| Keep schema 1 source and add a complete printer/trivia companion | Keeps positive token objects usable where a real v1 graph exists | Requires two coordinated artifacts, two completeness rules, and a projection map; v1 graph still cannot carry the new entry/state facts | Safe alternative, not selected |
| New source schema 2 with all items, lines, and a checked positive view | One complete inventory; explicit empty items; no fake v1 graph | Requires a new reader and explicit consumer selection | Select |
| Store only active-operand values | Smaller usual record | Omits source-only or unused decoded values; weakens inventory claims | Reject for this profile |
| Full Java bank plus explicit native gaps | Small change to the observable boundary; keeps every decoded item | Does not expose native optimization history | Select |

For the companion alternative, an acceptable pair would bind both hashes, raw bytes, pass, and function. The companion would have the same complete lines/items defined in `api.md`. Its projection would require exactly one v1 token for each nonempty item and none for empty items. No consumer could accept the v1 member alone as complete. This is safe but stores the same positive items twice. Source schema 2 avoids that second stored truth. Its projection is computed and checked on demand.

## 7. Authority and remaining gates

Record constructors, canonical JSON, hashes, and self-consistency do not authenticate a producer. A caller can make a consistent false record. Admission needs the exact producer source and tool pins, actual controls, bounded execution, and independent review. Semantic acceptance needs separate checked evidence.

| Bounded unit or gate | Decision |
|---|---|
| Pure graph schema 2 reader and serializer | PASS-to-implement |
| Pure complete source schema 2 reader and checked projection | PASS-to-implement |
| New same-call Java collector, after the readers pass | PASS-to-implement |
| Diagnostic-only conversion and explicit selector, after reader checks | PASS-to-implement |
| Existing F1 I/O correction | HOLD for this review; separate work, not inspected or certified |
| Complete producer admission | HOLD pending implementation, actual controls, and independent review |
| Full capture review | OPEN after provider screening; not retried or replaced here |
| Native bank and native state completeness | HOLD; current API does not export it |
| Entry relation and raw/analyzed effect closure | HOLD |
| Exact source grammar and callable interface | HOLD |
| Pointer proof, deterministic emission, and production publication | HOLD |
| Actual compiled byte-loop positive and Linux portability evidence | HOLD |
| Phoenix milestones and SPEC §9 | HOLD; this design satisfies none of those completion claims |

The original U5 design remains the semantic scope. It covers bounded scalar counted byte fill and forward copy. It does not permit a general symbolic executor, guessed aliases, or replacing a forward overlap-sensitive copy with `memcpy` or `memmove` without the required proof. All effects, exact source structure, callable formals, and pointer conditions must close before emission. The generated definition must be active in the rebuilt project and protected from later unproved edits.

Phoenix must still complete M4; publish T0–T3 results against every baseline with costs and failures; publish the harness, benchmark binaries, held-out inputs, and committed source tarballs at the specified stage; and reproduce every headline with `phoenix-eval --replay`. The adapter cannot replace any part of that definition of done.

## 8. Recommended next action

Implement the two pure readers in an isolated worktree after the bounded design is accepted into the root plan. Start with independent synthetic controls and old-format regression fixtures. Then implement the same-call collector. Re-run the named public E1 control only when authorized resources are available. E1 must demonstrate faithful capture and honest gaps. A real compiled byte-loop positive remains a later Linux gate. Keep production HOLD throughout these steps.
