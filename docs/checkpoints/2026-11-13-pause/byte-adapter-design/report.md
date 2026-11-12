# Independent adapter architecture report

Date: 2026-11-12 UTC.

**Decision: PASS-to-implement for the bounded observation units. Complete producer admission and production remain HOLD.** This decision does not certify code, runtime capture, or machine semantics.

Deliverables: [design.md](design.md), [api.md](api.md), and [implementation-plan.md](implementation-plan.md). This report records the evidence and the review limits.

## 1. Scope and authority

The task was performed directly. No subagent or nested model was invoked, scheduled, or used. No provider, model CLI, API, plugin, or session reader was used. No compiler, Ghidra job, container, VM, or target ran. No Git mutation occurred. No source implementation changed. The worktree remains at `6d00328bcb2a58cbf340b8275031995b83063aa2` with empty `git status --short` output.

The user requested Standard service. This task did not change a service setting or enable Fast mode. The local evidence does not independently attest the host model routing or service tier. This report does not claim such an attestation.

Only the two assigned output directories received writes. The input copies were not changed. Anonymous HTTPS reads used exact official `NationalSecurityAgency/ghidra` raw paths at the pinned revision. The source URLs, lengths, and SHA-256 values are saved in [primary-sources.json](primary-sources.json). The exact downloaded files are under `/Volumes/PhoenixWork/tmp/m2-byte-adapter-design-astra-20261112/primary/`.

No private audit source, sealed source, held-out input, private run, Author output or history, session history, dispatch-output data, existing event data, stderr data, or summary data was read. The named public `parent-static1` artifacts were the actual fixture evidence. The review's additional static directory was not needed.

## 2. Inputs read

The full `AGENTS.md` and `SPEC.md` were read from the exact worktree. They were read again after context compaction. The installed poteto-mode skill was read at:

```text
/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md
```

The relevant Investigation, tool-mapping, explanation, technical-writing, and unslop guidance was also read. The explicit direct-task rule replaced all nested-model steps. Throughput checkpoint: n/a, read-only investigation.

All 13 source/test/configuration files in [inputs/source-manifest.json](inputs/source-manifest.json) were read in full. Every byte length and SHA-256 matched that manifest. Its source commit is `d1a17795c0a172dbfeebd91057f4ee9808421415`. These frozen copies, rather than the older ordinary exporter in the worktree, were the diagnostic implementation under review.

The complete input set also included `writer-report.md`, `diagnostic-hold-sol.md`, and `parent-static-proof.json`. Their hashes are:

| Input | SHA-256 |
|---|---|
| `writer-report.md` | `3e430c64043783e16bd8d6a42765553bc34b8b24eb8c2b1251a5ba2dc7d32873` |
| `diagnostic-hold-sol.md` | `5fb6d41fd224ca6a0697505f8e7c56c74a6119e1f04e2419517f2084428ebdf0` |
| `parent-static-proof.json` | `08323597b272b9cee0a469e31ccf69bf0d4943ea15a36ced354a066dfaa06cf5` |

ADR0036 and ADR0038 were read from the frozen worktree. ADR0040 was read from the immutable input copy. The exact named public U5 directory existed. Its complete original `design.md`, `api.md`, and `report.md` were read. One truncated display of the design was covered by a subsequent bounded read.

| Original public U5 document | SHA-256 |
|---|---|
| `audit/m2-byte-idiom-design-astra-20261112/design.md` | `1fd92a7a1100c2cfd59df9e75d6ae6dea0db3c53e91a0f4b161de8e72c31f738` |
| `audit/m2-byte-idiom-design-astra-20261112/api.md` | `36bca3036ba63c12cd6aba1fcc497f2593f8fdd90ac4fda2f68f9338d77d383f` |
| `audit/m2-byte-idiom-design-astra-20261112/report.md` | `69955fae8f34f6107ffcd6d91b713679e796b59990e04a8779366c9883f40005` |

No broad Git history or unrelated repository survey was used.

## 3. Pinned primary findings

All upstream file identities below are pinned to Ghidra commit `8ca9077040cc43cd790babcfccf19475622a3e9a`, version 12.2. Line numbers refer to the exact downloaded bytes. [primary-sources.json](primary-sources.json) supplies the full path, exact URL, byte length, and hash for each of the 36 files. The local source copies retain those bytes.

| Finding | Exact primary location | Consequence |
|---|---|---|
| High-function entry is the ordinary function entry | `HighFunction.java:61–71,247–293` | Preserve ordinary function identity; it is separate from block cover minima |
| Native function base and block tree are separate fields | `funcdata.cc:735–759` | Do not require a block minimum to stand in for the function base |
| Native entry block is first; index assignment preserves it | `block.cc:1019–1148,1627–1660` | Pinned index-0 convention can identify the analyzed entry block; it is not a raw-entry effect proof |
| Java imports actual block indices and can have null slots | `PcodeSyntaxTree.java:482–503` | Preserve IDs; refuse holes instead of filtering or renumbering |
| Minimum cover address and native original entry instruction differ in meaning | `PcodeBlockBasic.java:42–59,128–146`; `block.cc:2317–2353` | Store cover endpoints honestly; native entry address remains unavailable |
| Native flow can start a range at a p-code-bearing instruction and can create an empty entry | `flow.cc:823–844,978–1016` | These are possible mechanisms, not a diagnosis of absent E1 graphs |
| Native serializer emits block operations, not the full native bank | `funcdata.cc:683–725` | Full Java bank is not full native bank or removed-operation history |
| Operation encoding has no native flags | `op.cc:412–465`; Java `PcodeOp.java:476–492` | Java dead Boolean cannot be a decoded native flag |
| Java AST starts dead; bank creation puts it on the dead list | `PcodeOpAST.java:35–55`; `PcodeOpBank.java:60–68` | Retain actual Java `true`; do not clear it |
| Java block insertion sets parent and iterator only | `PcodeSyntaxTree.java:456–468,493–496`; `PcodeBlockBasic.java:89–94` | Block ownership can coexist with Java `true` without proving native death |
| Java and native `markAlive` differ | `PcodeOpBank.java:83–93`; `op.cc:1056–1076`; `funcdata_op.cc:150–173` | Do not substitute Java list bookkeeping for native state |
| Native operations can leave the bank | `op.cc:983–1041` | Current decoded bank does not expose all removed operations |
| Java full-bank and full-value APIs have bounded observable scopes | `PcodeSyntaxTree.java:151–156,230–257` | Capture complete Java inventories; do not infer native completeness |
| Decode can create Java varnodes for special operands | `Varnode.java:388–413,469–472` | Local IDs are Java/pass identities; equal storage is not identity |
| Phi computation uses matching input/edge slots | `op.cc:770–784`; `PcodeBlock.java:282–322` | Preserve ordered edge slots and ordered operands, including parallel edges |
| Empty-line padding adds syntax items, sometimes empty | `PrettyPrinter.java:49–66`; `ClangToken.java:264–269` | Empty items need identities and zero-width intervals |
| Printer emits indentation, all items, then a separator on every line | `PrettyPrinter.java:84–113`; `ClangLine.java:31–64`; `StringUtilities.java:69` | Exact partition must include indentation and final separators |
| Ordinary C uses a name transformer | `DecompileResults.java:202–209`; `IllegalCharCppTransformer.java:69–118` | A null-transform reconstruction is not generally the same printer |
| Printer consumes breaks and merges comments | `DecompilerUtils.java:754–840`; `ClangCommentToken.java:29–37` | Inventory scope is post-printer; do not claim original markup-leaf completeness |
| Variable links can be direct; a high-function argument enables fallback | `ClangVariableToken.java:119–164` | Use direct objects and `getHighSymbol(null)`; never join by storage |
| Case value getter searches predecessors | `ClangCaseToken.java:67–99,121–136` | Preserve the item and direct operation; leave value/formal/storage unobserved with an explicit rule and gap |
| Field value is the direct operation output; bit-field class is separate | `ClangFieldToken.java:26–58`; `ClangBitFieldToken.java:23–53` | Label field-output association; do not apply field rendering to bit-field tokens |
| Java volatility setter discards that native property | `PcodeSyntaxTree.java:345–347` | Absence of a Java indication does not prove nonvolatile memory |

Representative exact official sources are [HighFunction.java](https://raw.githubusercontent.com/NationalSecurityAgency/ghidra/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/pcode/HighFunction.java), [PcodeOpAST.java](https://raw.githubusercontent.com/NationalSecurityAgency/ghidra/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Framework/SoftwareModeling/src/main/java/ghidra/program/model/pcode/PcodeOpAST.java), [funcdata.cc](https://raw.githubusercontent.com/NationalSecurityAgency/ghidra/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Features/Decompiler/src/decompile/cpp/funcdata.cc), and [PrettyPrinter.java](https://raw.githubusercontent.com/NationalSecurityAgency/ghidra/8ca9077040cc43cd790babcfccf19475622a3e9a/Ghidra/Features/Decompiler/src/main/java/ghidra/app/decompiler/PrettyPrinter.java). The manifest binds all other cited files to the same revision.

Important frozen implementation locations are `ExportLift.java:284–306` for the single ordinary decompile result; `OrdinaryByteEvidence.java:343–434` for graph capture; `:367` for the Java-dead gap; `:371–372` for entry equality; `:455–508` for printer capture; and `:466` for empty-item refusal. The old graph reader's equality is at `byte_graph.py:504–507`. None of those old rules is silently redefined by the new profile.

## 4. Actual public E1 evidence

Public artifact directory:

```text
/Volumes/PhoenixWork/audit/m2-byte-export-producer-root-20261112/parent-static1
```

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `lift.json` | 262032 | `74939e9fd429f31e9060d23b4de8733415f88dfdb041c00ebc1107be0229fec8` |
| `mapping.json` | 9912 | `3802a0d54d1868a03b5cd09b99924523594dfbf47a4823bc6c5abd06206205bc` |
| `byte-draft.json` | 69636 | `5f38c17692d34b560bbc32dd80c7e659310bbe36b9008a9f5d998741de759108` |
| `context.json` | 6189 | `d6e2d129ee7fcbcafe6796c13af822759bfaf2a2f2aaab81d69270434b6d19e4` |
| `result.json` | 71586 | `641462c904c4f9aa55e5caf4de769dd38cb65c162ba62505d77c612fc21df823` |
| `inspection.json` | 3182 | `48da0793a2c3fc23bd68670ea087a3c0c195b97c0155c094d300f026a70e8e4a` |

The bound public binary hash is `8b4316d8f2975fe6a0ff61876c483d8089309c3b6371c32b6da9de9d5db96bca`. This task did not read or execute the binary.

The saved lift contains 19 functions, 472 raw operations, and 101 ordinary analyzed operations. The retained ten graph records contain 13 block-owned analyzed operations. Those are different scopes. Do not report 13 as the full program's analyzed count.

The nine entry-refusal function identities are:

```text
0x101000 0x101050 0x101060 0x101070 0x101080
0x1010e0 0x101180 0x1011c0 0x1011e0
```

Their graph, facts, and source members are absent. Actual differing analyzed starts are not recoverable from these files. This review does not assign guessed starts or explain each refusal as a specific optimized prefix.

The ten printer-refusal functions are `0x101110`, `0x101140`, `0x1011d0`, and `0x105000`, `0x105008`, `0x105010`, `0x105018`, `0x105020`, `0x105028`, `0x105030`. All retained operations have parent block index 0 and Java `isDead=true`:

| Function | Analyzed sequence address in `ram` | Sequence index |
|---|---|---:|
| `0x101110` | `0x101138` | 28 |
| `0x101140` | `0x101178` | 128 |
| `0x1011d0` | `0x1011d0` | 2 |
| `0x1011d0` | `0x1011db` | 106 |
| `0x1011d0` | `0x1011db` | 108 |
| `0x1011d0` | `0x1011dd` | 66 |
| `0x105000` | `0x105000` | 0 |
| `0x105008` | `0x105008` | 0 |
| `0x105010` | `0x105010` | 0 |
| `0x105018` | `0x105018` | 0 |
| `0x105020` | `0x105020` | 0 |
| `0x105028` | `0x105028` | 0 |
| `0x105030` | `0x105030` | 0 |

The retained graphs have explicit gaps. No operation was certified semantically live or dead. No complete source observation exists. A repeatable refusal is still a refusal. E1 remains a public producer control, not the required compiled byte-loop positive.

## 5. Commands, exits, and verification

[commands.json](commands.json) records the exact retained shell commands and exits, beginning with the original U5 reads. It is a task command ledger, not a session-history export. Earlier startup and skill reads are described above. All shells sourced `/Volumes/Extreme Pro/Phoenix/env.sh` before other commands.

The following commands were also repeated near completion, with exit 0:

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
GIT_OPTIONAL_LOCKS=0 git rev-parse HEAD
GIT_OPTIONAL_LOCKS=0 git status --short
df -h / '/Volumes/Extreme Pro'
```

The exact Python hash checks are in the ledger. They verified all 13 frozen source files and all 36 saved primary source files. The public artifact inspection checked the six hashes and the retained operation states. The read-only source inspection commands used `cat`, `sed`, `nl`, `rg`, and small Python readers. Named installed native source paths were absent; that was why exact upstream sources were fetched. No general web survey was used.

The three foreground HTTPS fetch sessions were `18723`, `14715`, and `52458`. Each was polled to completion with process exit 0. No fetch process remains. One `functions.exec` call had a JavaScript syntax error before shell execution. It had no process exit or filesystem effect. The corrected call completed normally. Some long read displays were split or reread to cover truncation. These are process exceptions, not hidden test failures.

The first document check failed its requirement that each document contain an explicit HOLD label. The API document stated the restriction but lacked that label. The label was added. That shell later ran `git status`, so its final exit was 0 despite the Python assertion failure. The failed assertion was inspected directly. Final validation runs the document check as its own command. This is another reason not to treat a shell exit code alone as approval.

At the completion check, the internal drive had 14 GiB available and the external drive had 39 GiB available. These matched the rounded startup values. This review did not inspect unrelated storage or claim a precise long-term baseline comparison.

No pytest, ruff, mypy, compilation, headless export, or runtime test was run in this task. Reported earlier test or job outcomes remain claims in the frozen input reports. They are not newly executed evidence. An exit code proves only that the specific inspection command ended normally. It does not approve a producer or a proof.

## 6. Process exceptions and unresolved facts

The task's specific restrictions replaced the general instructions to read broad progress/history files, update repository memory, use nested reviewers, run long autonomous milestone work, and commit or push. Decisions and conflicts are recorded here because repository writes were forbidden. No background `caffeinate` or other child was left behind. The named Author-owned VM was not accessed.

The root may correct routine F1 I/O handling in the changing diagnostic worktree. This review did not inspect that worktree or certify that correction. The frozen review remains HOLD on that work. The new adapter plan separates pure conversion from process supervision so that this architecture result cannot be misread as I/O approval.

Full capture review remains **OPEN after provider screening**. It was not retried or replaced. This report is an architecture design, not that full capture review.

Remaining unproved facts include the actual analyzed starts for the nine absent E1 graphs; complete actual printer inventories; native dead flags and full native operation history; exhaustive machine instruction and function boundaries; the raw/analyzed entry-state relation; all effect closure; exact C grammar; callable formals; pointer provenance and ranges; deterministic active emission; Linux behavioral controls; producer authenticity; and every production admission requirement.

Constructors, source pins supplied by a caller, canonical hashes, and internally consistent records grant no authority. The proposed data model carries observations and gaps. Actual capture and independent review are required before trusting its origin. Separate proofs are required before using it for emission.

The task checked `/Volumes/PhoenixWork/audit/continue-v1/DRAINING` and `PAUSED` during work. Both were absent at the recorded 23:20:15 UTC check on 2026-11-12. The design was prepared before the 2026-11-13 00:56:47 UTC drain deadline. No new work is scheduled for or after the required 01:11:47 UTC pause. Final document checks record the last sentinel state in `final-check.json`.

## 7. Unit decisions and next action

| Unit | Decision |
|---|---|
| Strict graph schema 2 reader | PASS-to-implement |
| Complete source schema 2 reader and checked positive projection | PASS-to-implement |
| Same-call observation collector and explicit selector | PASS-to-implement after the pure readers pass |
| Pure diagnostic conversion and public controls | PASS-to-implement after its reader dependencies |
| Process supervision and F1 certification | HOLD for separate work and review |
| Complete producer admission | HOLD |
| Full capture review | OPEN, after provider screening |
| Native inventory/state closure and entry/effect proof | HOLD |
| Source grammar, callable interface, pointer proof, and emission | HOLD |
| Compiled Linux positive, publication, and production | HOLD |
| M4 and all SPEC §9 completion claims | HOLD |

Next action: implement the two pure readers with independent synthetic controls. Keep the old contracts exact. Then implement the separately selected collector and measure the actual public E1 output. Do not enable production. Preserve all SPEC §9 work in the root plan.
