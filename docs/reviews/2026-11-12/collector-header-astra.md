Phoenix requires verified completion through SPEC.md section 9. This independent critical review covers the fixed typed collector representation, its bounded renderer, and its independent source reader.

**PASS for this bounded unit at `501c937b4bb6348a5a7daf575493779c188712f8`.** I found no reproducible source defect that requires a correction before this unit can proceed. This verdict uses source inspection, complete logical comparisons, adversarial controls, and native layout checks. Exit 0 alone is not approval.

**Full capture review remains OPEN after provider screening. Production remains HOLD.** This review does not retry, replace, rephrase, or certify that review. It does not certify the separate source-token reader. It supplies no Phoenix score, milestone result, runtime authority, recovery permission, or localization permission.

I performed the review directly. I started no model, agent, nested session, model CLI, or provider call. The requested model and Standard tier are supervisor settings. I did not inspect session histories to attest those settings. No safety or service setting changed.

The exact basis is [revisions.json](revisions.json). The branch is `agent/m2-collector-header`. The base is `63dd98589689276ea6761caa84dadc3ab83f7dee`. The worktree is `/Volumes/PhoenixWork/worktrees/m1-ledger-identity`. The named commit hook reports `Phoenix quality checks` passed. Its exit file and the push exit file both contain 0. The parent record reports server verification. I did not repeat that network check or run a repository hook that might exceed this review's execution scope.

[Before](before.json) and [after](after.json) source records are equal. All 214 tracked files match their committed bytes. The worktree remains clean. Exactly seven paths differ from the base. Five are the new implementation, test, and ADR files listed below. The other two are `docs/STATUS.md` and `docs/LOG.md`. Both retain their complete base bytes as unchanged prefixes. The static data dependency remains unchanged. All five new file hashes match the worker's final-scope.json. The later parent append accounts for the different LOG hash.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `phoenix/observe/collector_header.py` | 29131 | `fa5d25fb5c910796127bb29a17f5f111b6555beb9dc02a82ad75611747578684` |
| `phoenix/observe/collector_header_read.py` | 28134 | `087c9e62fa56ffbca7757c50577368fa0370eed744dd4aa47325e3ed7164d669` |
| `phoenix/observe/native/collector_data_v1.h` | 18853 | `2e278603d75d6cd436aedc72af3f1903334dadc37d6d8847dfd3dd825018acb3` |
| `tests/test_observe_collector_header.py` | 37022 | `e5755cafffda9ea5879f2db723891638d34ca50f8e385acc7d34e2c3a96b506c` |
| `docs/adr/0037-eager-collector-header.md` | 6377 | `2f275cb3cc668aa730e79fbb6cf5b5d184bcafb40d25d79f4a8e8eef7111399d` |
| Unchanged `phoenix/observe/collector_data.py` | 12488 | `d5005ac55660660be160181ff89f985e6b02e754bc16a8b9a9c286a5e8cef309` |

The renderer manifest identity is `66231c5a0bae898c8ce3c0d7ec77f4bce32fad73864e8340112584071603fcf4`. The native identity is the header hash above. [source-identities.json](source-identities.json) preserves these values. [input-identities.json](input-identities.json) identifies the named review documents and parent evidence.

I read AGENTS.md, SPEC.md, the required poteto-mode skill, and its comment-sicko reference. I read both approved Astra architecture documents, the candidate design and API, the complete worker report and scope record, the new source, tests, and ADR. I also read the unchanged data module and relevant public fixture helpers. Corrected F1 through F4 take priority over the candidate. The fresh independent data PASS applies to the unchanged base dependency. The worker report's older open-review statement is stale.

The review found the following properties. None is a replacement for the later trusted boundary.

| Area | Evidence and conclusion |
| --- | --- |
| Complete logical data | Six fresh whole-record controls compare decoded output with every dataclass field. They replace the expected plan and scope with the original canonical input records. They independently calculate the original-byte identity and complete logical digest. Default, shared-route, omitted-site, and both root-evidence forms pass. The 1,396-test affected suite adds guard, import, thunk, and shared-suffix cases. No selected-site projection replaces the complete record. |
| Native agreement | [native_checks.py](native_checks.py) derives expected field types and offsets from logical descriptors. It does not use the production size or width helpers. [layout.c](layout.c) has 1,306 static assertions. They check all 214 top-level fields in 46 record types, every option and variant payload, signed fields, all 47 slice types, table tags, record alignment, and the complete directory. `_Generic` checks exact native types. `offsetof` checks semantic field positions. These checks passed for arm64 and x86-64 Darwin target layouts. |
| Detection of native drift | Four altered native declarations retain plausible structure sizes. They swap geometry fields, substitute a different typed variant slice, change a table tag, or swap directory lengths. Each syntax-only control fails its relevant assertion. Thus this check detects errors that total-size tests can miss. The mutations remain in this audit directory. |
| Directory completeness | The fixed external `phoenix_collector_data_v1` references all 47 tables. Each entry carries its tag, count, logical element and total lengths, physical `sizeof` lengths, and address. The directory has three 32-byte identities and 47 entries of 56 bytes in the checked profiles. Independent mutations cover every table and every physical storage-length expression. The affected suite covers each other directory field. |
| Empty storage | Empty tables have one zero physical C element and zero logical rows. The reader enforces that distinction. The termination-contract tables remain inactive under this profile. Checking their declarations and empty storage does not enable termination contracts. This review does not claim that all 47 tables can be nonempty in one admitted record. |
| Data syntax | Generated C contains fixed declarations and numeric initializers. Text uses UTF-8 byte slices. It does not become a C identifier, quoted text, include, or function. High bytes, NUL, empty text, source-like text, and Unicode boundary values round-trip exactly. Surrogates refuse. Null options remain distinct from zero and empty strings. |
| Integer representation | Signed extremes survive through sign and magnitude. Negative zero and out-of-range magnitudes refuse. Geometry stores start and size. An exclusive end of `2**64` survives when its size fits. A size of `2**64` explicitly refuses. The data dependency remains unchanged. |
| Canonical traversal | The source reader checks each offset before subtracting it from the table length. It requires canonical cursor order. Reused byte slices, excessive offsets or counts, missing or duplicate tables, extra names, unreferenced rows, inactive payloads, and bad tags refuse. Fresh unused-row controls update directory counts and lengths coherently. They still fail before digest validation. |
| Canonical grammar | The reader accepts only the fixed include, order, declarations, numeric syntax, directory, and final LF. Trailing whitespace, NUL, comments, and executable source refuse. Invalid UTF-8, digest text, and schema text fail before hashing. Each directory identity is independently checked. |
| Reader independence | The reader imports no writer code. Fresh controls disable the writer's table builder, measurer, member projection, cell formatting, and public renderer. Source decoding still matches the complete expected record. Sharing the schema is acceptable here because native agreement was checked separately. |
| Error handling | Fixed-source `OSError` failures become bounded refusals. Fresh sentinels inject `RuntimeError`, `TypeError`, `ValueError`, and `AssertionError` at six internal points. All 24 remain visible exceptions. The implementation has no broad exception conversion to a valid header or partial success. The separate source-token reader was not tested or certified. |

The source decoder is implemented at [collector_header_read.py line 746](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/collector_header_read.py:746). Its canonical traversal starts at [line 584](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/collector_header_read.py:584). The native declarations were inspected in full. The native checks cover the actual C declarations, not a copied Python structure description alone. They do not inspect compiled bytes or linker output.

The renderer's [measurement pass](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/collector_header.py:181) reserves a complete array before it walks its children. It checks logical storage, 32-bit table indexes, exact emitted source size, and strict UTF-8 lengths. The [public renderer](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/collector_header.py:707) completes this pass before it constructs tables or generated source. Exact source and logical-storage limits pass. One byte below each limit refuses with table construction and canonical hashing disabled.

The source reader checks raw length before ASCII decoding. It checks each declared table's logical storage before parsing its rows. Fresh controls disable the corresponding row parser and submit oversized extents. Each refuses before that parser runs. Fixed source reads request at most 2 MiB plus one byte. Fresh controls check that read size and require refusal for oversized or missing writer, reader, and native files.

These guarantees have specific limits. The 64 MiB cap bounds generated source. The 32 MiB cap bounds logical constants. Empty physical elements and C padding do not count as logical rows. Python objects, table construction, source copies, independent decoding, and `CollectorData.record()` can use more memory than logical storage. Inherited count checks can follow a bounded measurement or hash traversal. They still precede table materialization. This is not a claim that every lower count limit prevents all earlier traversal. Actual plugin size, compiler memory, compiler time, and worst-case Python memory remain unmeasured.

Internal identities are also bounded claims. [The renderer](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/collector_header.py:424) checks the canonical plan and scope hashes, their evidence links, installed policy, request, register order, geometry, gaps, route bindings, route positions, continuation users, dispositions, omissions, and roles. Fresh and affected controls reject inconsistent retained references.

A direct constructor still supplies unverified assertions. `test_consistent_fabrication_is_not_provenance` changes the retained image entry without changing the original-byte identity. The renderer accepts that typed record and produces a different logical digest. This is expected under this pure representation contract. It proves that a matching header and logical digest cannot authenticate the original ELF facts. The later trusted boundary must rebuild data from raw inputs. It must not treat `GeneratedHeader` or `DecodedHeader` as an authority token. The renderer infers no provider, library, type, or additional argument fact.

Source identity controls change bytes returned from each fixed source path. Old headers then refuse. Newly rendered headers change their source identities and header hash while retaining the logical data identity. The renderer manifest covers exactly its two Python files. The native hash covers exactly the fixed declarations. Neither hashes generated output. There is no header, plugin, receipt, or runtime identity cycle. These hashes do not attest loaded Python bytecode, imports, or an executing process. The later source-closure gate remains mandatory.

The architecture trade-offs and next actions are as follows. These are later integration requirements, not defects in the reviewed unit.

| Choice | Benefit and cost | Action |
| --- | --- | --- |
| Fixed typed tables | Each logical record has a native type. Source injection is excluded by the grammar. Separate schema and C declarations can drift. | Retain the field-level layout checks and negative mutations in future native-schema verification. A total-size test is insufficient. |
| Strict canonical traversal without storage sharing | Duplicate references and unused data are easy to detect. Repeated strings consume more space. | Keep this rule for schema 1. If storage sharing becomes necessary, define a new canonical rule and schema before changing acceptance. |
| Reader owns the shared schema | The reader remains independent of writer projection. Schema errors can still affect both Python paths. | Keep complete comparisons against raw canonical plan and scope. Keep the native layout check independent of production width calculations. |
| Fixed-width slices and start/size geometry | Arithmetic and native layout stay simple. A span of size `2**64` cannot be represented. | Keep the explicit refusal. Do not wrap or silently substitute a different envelope. |
| Source-bound reader | Changed source invalidates stale headers. Old artifacts require their matching implementation for reproduction. | Keep exact schema and source identities in later build records. Define an explicit migration before changing tags, field meanings, or canonical storage. |
| Exported retained directory | Every table has a reference from one fixed export. Source attributes alone do not prove plugin retention. | Complete F3 with actual plugin-byte inspection, a separate compiled-data reader, and a receipt-bound inspection record. |

Corrected F1 through F4 remain compatible with this unit.

| Requirement | This unit and remaining gate |
| --- | --- |
| F1. Trusted issuance | This unit creates no `CheckedBuild`, issued build pin, cache permission, or execution receipt. Later code must separate consistency from issuance. Require controller-owned build and execution registries. An artifact directory cannot supply its own trusted pin. |
| F2. Calibration | This unit creates no calibration approval. Record each trial's actual binary, plan, scope, build, runtime, launch, and output identities. Apply the installed common-context rule. Preserve the distinction between implementation calibration and exact-artifact calibration. |
| F3. Complete retention | The source directory and complete logical source decoder pass this review. The native installer, table traversal, operational indexes, independent compiled-data reader, and actual plugin inspection remain open. Bind inspection to actual plugin bytes and the trusted receipt. Validate the target layout from the actual authorized build. |
| F4. Source and launch association | These two Python hashes and one native hash are component identities only. Freeze the complete source and import allowlist later. Bind interpreter, dependencies, bytecode policy, compiler, linker, headers, and libraries. Preserve the existing policy and admission algorithms. Bind the fixed launch profile, actual expanded launch specification, accepted case, complete outcome, and trusted execution transaction. |

The following command results are retained. [commands.jsonl](commands.jsonl) records actual argument vectors, working directories, environment overrides, and exits. All external pytest calls use this exact audit root and confcutdir. Eighteen named public files were copied to this audit directory. Six are public test files. The other twelve supply file-byte checks. [copies.json](copies.json) records their hashes. The final check verifies every copy against the unchanged committed source. Product imports use the actual worktree.

| Check | Exit | Actual result |
| --- | ---: | --- |
| First affected pytest run | 3 | The audit guard blocked pytest's default log output before collection. [affected.log](affected.log). No product test ran. |
| Affected pytest with confined log path | 0 | 1,396 passed. [affected-confined.log](affected-confined.log). |
| First independent controls | 0 | 260 passed. [independent.log](independent.log). |
| Expanded independent controls | 0 | 276 passed. [independent-expanded.log](independent-expanded.log). |
| Native input preparation | 0 | Prepared 1,306 assertions, three generated public headers, and four declaration mutations. [native-inputs.log](native-inputs.log). |
| arm64 syntax and layout | 0 | Fixed declarations and three generated headers passed. [native-layout-arm64.log](native-layout-arm64.log). |
| x86-64 syntax and layout | 0 | The same four translation units passed. [native-layout-x86_64.log](native-layout-x86_64.log). |
| Geometry field swap | 1 expected | Offset assertions failed. [native-negative-swapped-geometry.log](native-negative-swapped-geometry.log). |
| Wrong variant slice type | 1 expected | Exact type assertion failed. [native-negative-wrong-slice-type.log](native-negative-wrong-slice-type.log). |
| Wrong table tag | 1 expected | Tag assertion failed. [native-negative-wrong-tag.log](native-negative-wrong-tag.log). |
| Directory field swap | 1 expected | Directory offsets failed. [native-negative-swapped-directory.log](native-negative-swapped-directory.log). |
| Source Ruff check | 0 | All three Python source and test files passed. [source-lint.log](source-lint.log). |
| Source Ruff format check | 0 | All three files already formatted. [source-format.log](source-format.log). |
| Strict source mypy | 0 | No issues in three files. [source-types.log](source-types.log). |
| Exact diff whitespace | 0 | No diagnostics. [diff-whitespace.log](diff-whitespace.log). |
| Final source and copy check | 0 | All 214 tracked files and 18 copies match. Exact diff and append-only progress checks pass. [final-state.json](final-state.json). |

The first pytest failure was a review setup error. I redirected its log into the permitted temporary directory. I did not relax the guard. All four nonzero native controls are expected detections of audit-only mutations. No independent product control failed. Early path searches used repository-relative audit and temporary paths and found no files. Subsequent reads used `$PHOENIX_ROOT`. These path errors are not source findings.

A reproducible independent test command follows. The checked wrapper also records the complete environment and output.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-ledger-identity
.venv/bin/python -B \
  /Volumes/PhoenixWork/tmp/m2-collector-header-review-astra-20261112/checks.py repeat \
  .venv/bin/python -B -m pytest \
  --rootdir=/Volumes/PhoenixWork/audit/m2-collector-header-review-astra-20261112 \
  --confcutdir=/Volumes/PhoenixWork/audit/m2-collector-header-review-astra-20261112 \
  /Volumes/PhoenixWork/audit/m2-collector-header-review-astra-20261112/test_independent.py \
  -q \
  -o cache_dir=/Volumes/PhoenixWork/tmp/m2-collector-header-review-astra-20261112/pytest \
  -o log_file=/Volumes/PhoenixWork/tmp/m2-collector-header-review-astra-20261112/pytest-file.log \
  --basetemp=/Volumes/PhoenixWork/tmp/m2-collector-header-review-astra-20261112/repeat-temp
```

The native commands use `clang -std=c11 -Wall -Wextra -Werror -fsyntax-only -fno-modules`. Positive commands add `-target arm64-apple-darwin` or `-target x86_64-apple-darwin` and the fixed native include directory. Exact files and flags are in the command record. No object, executable, shared library, link, or build was produced. These target layouts do not establish Linux toolchain behavior or compiled retention.

The pytest [guard](conftest.py) blocks process creation, network connections, private paths, prior dispatch output, and writes outside the two audit roots. The dedicated bytecode prefix remains absent. This isolates these checks from an existing cache at that prefix. It does not prove production import provenance. The private Author retained the VM. I read no sealed source, held-out input, source archive, run, Author output or history, session history, or pre-existing event, stderr, or summary file.

The comment review found no concrete incorrect contract comment or unsafe suppression in scope. Public docstrings state the representation and authority limits. Test type suppressions support deliberate invalid-input controls. No cosmetic deletion or source edit is requested. The comment deletion count is zero.

I used the requested [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md), its Investigation workflow, and its comment and prose guides. The user's direct-review rule replaced nested-model steps. Boundary Discipline kept representation consistency separate from authority. I read that principle's leaf skill. ASD-STE100 Issue 9 governs this report. The [task list](todo.md) records the review scope. `throughput checkpoint: n/a, read-only investigation`.

The native state machine, launch adapter, installer, trusted build issuance, cache, source closure, compiled reader, plugin inspection, full capture review, public calibration, and production binding remain required. Public live tests must retain complete outcome comparisons, mutation controls, failure accounting, repeated execution, both accepted oracle engines, and native x86-64 and AArch64 evidence. Source decoding and these syntax checks cannot substitute for them.

SPEC section 9 remains open. Complete M2 through M4. Publish the required T0 through T3 results, all baselines, costs, failure taxonomy, benchmark artifacts, and commitments. Replay every headline result through `phoenix-eval`.

Only this audit directory and its matching external temporary directory received review output. No source edit, commit, push, tag, or branch change occurred. No Docker, VM, target, Ghidra, actual build, or real model-provider call ran. All child commands completed. No background child remains.
