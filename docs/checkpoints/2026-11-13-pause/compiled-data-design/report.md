Phoenix needs independent compiled collector-table inspection under corrected F3. The selected design combines fixed Linux layout profiles, a data-only compiler witness, and a bounded passive ELF reader. It retains the full logical record. It separates inspection consistency from trusted issuance.

The recommended next action is to implement U1 only. Add the bounded pure ELF reader and its synthetic controls in the exact scope in implementation-plan.md. Obtain an independent implementation review before U2 relies on it. No Linux access is needed for U1. Do not describe its synthetic tests as compiled retention proof.

The unit verdicts are as follows.

| Unit | Verdict | Reason and next gate |
| --- | --- | --- |
| U1. Bounded passive ELF view | PASS-to-implement | Its input is immutable bytes. Its parser, symbol, mapping, and relocation rules are explicit. Pure synthetic controls can run before Linux. A later independent implementation review is required. |
| U2. Independent logical readback | PASS-to-implement after U1 review | The complete field map, nested layout, cursor rules, comparison boundary, work limits, and inspection record are specified. This approval does not activate a Linux profile. |
| U3. Fixed witness and compiler test inputs | PASS-to-implement after U2 review | Fixed C data and assertions can be authored and reviewed. Actual compilation remains HOLD until the separate VM lease ends. |
| U4. Actual Linux profile validation | HOLD | No compiler or actual plugin output was inspected in this task. Both native host profiles need exact compiler outputs, full comparisons, corruption controls, resource checks, and independent evidence review. |
| U5. Trusted build and collector integration | HOLD | F1 issuance, actual native traversal, full F4 closure, and the separate build and native reviews remain required. Full capture review stays OPEN. Runtime admission is outside this task. |

The deliverables are [design.md](design.md), [api.md](api.md), and [implementation-plan.md](implementation-plan.md). This report records their evidence and limits.

The concrete findings are as follows.

| Finding | Evidence | Design consequence |
| --- | --- | --- |
| Logical size is not compiled layout. | The source reader's `element_bytes()` sums descriptor sizes. It parses `sizeof` source expressions but does not inspect their ELF results. | A separate installed layout vector and actual output witness are required. No source-size estimate becomes a Linux offset. |
| The schema is complete at the source boundary. | The named source files retain 47 tables, 46 record types, and 214 top-level fields. The source reader requires full cursor exhaustion. | Preserve all fields and the current no-sharing rule. A selected-site comparison is insufficient. |
| Equal total size can hide semantic drift. | The named native scripts check exact types and offsets. Their mutation controls swap geometry fields, swap directory lengths, change a slice type, and change a table tag. | Require complete nested field assertions. Preserve these mutations in later Linux validation. |
| The current native evidence is limited. | The supplied reviews describe Darwin syntax-only checks. I read their scripts and complete assertion files. I did not rerun their compilers. | These assertions define test expectations. They do not establish Linux layout, retention, relocations, or runtime behavior. |
| A witness can be fabricated. | Its bytes and tables can be made mutually consistent without a trusted build. Corrected F1 explicitly separates consistency from issuance. | Compare the whole witness with installed expectations. Keep controller-issued K, B, Q pins mandatory later. |
| A directory reference needs relocation evidence. | The fixed directory uses 47 pointers to static local arrays. A shared object's on-disk pointer word is not a resolved runtime pointer. | Require one ELF64 RELA relative relocation per cell, with machine-specific kinds and exact local-symbol targets. Never load the plugin. |
| Empty logical tables still occupy storage. | The renderer emits one zero element and `count=0`. The directory records the physical `sizeof` values. | Require the zero physical element, symbol, extent, pointer, and relocation. Do not infer absence from count zero. |
| Existing ingest cannot be reused unchanged. | It requires x86-64 executable entry and interpreter evidence and rejects symbol tables. | Add a narrow shared-object parser. Do not turn private ingest helpers into an undocumented API. |
| The current package has no runtime dependencies. | `pyproject.toml` has `dependencies = []`. | Keep the first reader standard-library only. Accept a restricted output profile instead of adding a general ELF or DWARF parser. |
| Recipe scope is incomplete for this feature. | Frozen HEAD tracks the accepted worker and integrity recipes. The named prior architecture cites the public observer recipe at `c76cc598`. That recipe is AArch64, uses QEMU 9.2 and GCC 13, and predates this witness. | Add a dedicated future inspection recipe. Keep the accepted QEMU 8.2.2 and Rosetta oracles unchanged. Pin separate compiler and native host contexts. |
| Passive inspection cannot prove code use. | Complete retained data can coexist with code that reads another list. | Independently review the later installer and operational indexes. Add native mutations that bypass or misdirect table use. |

The alternatives have different costs. Debug metadata adds a large parser or external tool protocol without proving that a described object survived linking. A loaded inspector executes loader behavior and can observe altered memory. Explicit profiles alone lack checked output evidence. A witness alone trusts submitted layout claims. The combined profile and witness contract avoids these gaps while keeping a small byte-input API.

The first ELF profile is intentionally restrictive. It requires unstripped symbol tables, SysV dynamic hashing, ordinary section numbering, file-backed data, a complete RELA inventory, and local table symbols. It permits only relative directory-pointer relocations. It rejects packing, folded table objects, unsupported relocation forms, and ambiguous mappings. This can reject valid general-purpose ELF files. Those files are outside this fixed collector build contract.

The witness contract has 100 type entries, 653 member entries, and 47 table entries. Its fixed encoding has 5021 words and 40168 bytes. The 653 entries include each aggregate and nested semantic member. The complete top-level map and recursive expansion are in design.md. The expanded proposed map is saved in [proposed-layout.json](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/proposed-layout.json). It is not an installed production profile.

The static assertion scan read every line of both public `layout.c` files. It classified every assertion and compared every recorded offset. The Astra file has 1306 assertions and 356 unique offset expressions. The Sol file has 3278 assertions and 651 unique offset expressions. The files share 354 offset expressions with no conflicting value. Their union has 653 unique semantic offsets. Every proposed member offset matches that union. These are static inventory counts, not Phoenix evaluation results.

The complete expressions and comparison evidence are in [assertion-scan.json](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/assertion-scan.json) and [static-check.json](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/static-check.json). The scan did not compile C or infer Linux behavior. The review also read both assertion-generation scripts directly. Neither script ran.

The exact source basis is `501c937b4bb6348a5a7daf575493779c188712f8` at `/Volumes/PhoenixWork/worktrees/m1-ledger-identity`. Both identity checks returned that revision. The final named-file diff against HEAD was empty. No source or Git state changed.

The principal source identities are as follows.

| Source | SHA-256 |
| --- | --- |
| `phoenix/observe/collector_data.py` | `d5005ac55660660be160181ff89f985e6b02e754bc16a8b9a9c286a5e8cef309` |
| `phoenix/observe/collector_header.py` | `fa5d25fb5c910796127bb29a17f5f111b6555beb9dc02a82ad75611747578684` |
| `phoenix/observe/collector_header_read.py` | `087c9e62fa56ffbca7757c50577368fa0370eed744dd4aa47325e3ed7164d669` |
| `phoenix/observe/native/collector_data_v1.h` | `2e278603d75d6cd436aedc72af3f1903334dadc37d6d8847dfd3dd825018acb3` |
| `tests/test_observe_collector_header.py` | `e5755cafffda9ea5879f2db723891638d34ca50f8e385acc7d34e2c3a96b506c` |
| `docs/adr/0037-eager-collector-header.md` | `2f275cb3cc668aa730e79fbb6cf5b5d184bcafb40d25d79f4a8e8eef7111399d` |

[Input identities](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/input-identities.json) records lengths and hashes for all 24 named source, design, review, script, and assertion inputs. The final byte check found no change in those inputs. Corrected F1 through F4 in the named architecture verdict take priority over the old candidate API. ADR0037's open header-review note is older than the supplied Sol and Astra PASS reports. Those reports apply to the source unit. They do not close compiled inspection.

The public observer recipe was read as a tracked file at `c76cc598add3e5e74ca208fcceb95badafab13fc`. No source archive was opened. Its Dockerfile hash is `e35f12b0f0e3e6b413d52a90c2deb67f16da42c1c601c6e240f03b63932eb0d8`. Its dockerignore hash is `b4a36e034414c6134abb1b5dbdc5823c3f73be80146593fc9c5330d25debde3d`. Its trace.lock hash is `7f67d78beff60aa2f153c4c0f528fa7581ec4fb04b8c28f157f4cb06da47b0b0`. [Recipe identities](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/recipe-identities.json) records the exact paths and lengths. These are historical public recipe inputs. They are not new production toolchain pins.

The command record is as follows. Every shell began with `source '/Volumes/Extreme Pro/Phoenix/env.sh'`. All listed commands completed. No command below ran a model, compiler, container, or target.

| Commands actually used | Outcome |
| --- | --- |
| `pwd` and `git rev-parse HEAD` | The required worktree and exact frozen revision matched. |
| `cat`, `sed -n`, and `wc -l` on the named inputs and necessary public skill files | Reads succeeded. Some combined tool displays truncated output. I used smaller explicit reads for the affected source and review files. |
| `rg --files docs/adr containers` with the specified filename filters | Located ADR0037 and the tracked container recipes. No file contents outside the selected public inputs were traversed. |
| `git ls-files '*Dockerfile*' '*trace.lock.toml'` | Found the accepted worker and integrity Dockerfiles at frozen HEAD. |
| `git ls-tree` restricted to recipe-name discovery | Located the cited public `experiments/m2_trace` recipe at the supplied historical revision. This was Git filename metadata, not a private-source traversal. |
| `git show c76cc598...:experiments/m2_trace/Dockerfile` and the corresponding dockerignore and trace.lock paths | Read the exact public recipe bytes. Later copies went only to this task's temporary directory. |
| `df -h / '/Volumes/Extreme Pro' /Volumes/PhoenixWork` | Both external volumes were mounted. Rounded available space was 15 GiB internal, 39 GiB on the external volume, and 18 GiB in PhoenixWork. No storage change followed. |
| `.venv/bin/python -B .../inspect_inputs.py` | Exit 0. Hashed the 24 inputs, read all assertion lines, checked expression categories, compared shared offsets, and extracted the complete semantic field inventory through bounded AST evaluation. It imported no product module. |
| `.venv/bin/python -B .../expand_layout.py` | Exit 0. Expanded the proposed layout to 100 types and 653 members. Wrote only this task's design evidence and document appendix. |
| Direct `.venv/bin/python -B` static comparison | Exit 0. All 24 input byte identities were unchanged. All 653 proposed member offsets matched the assertion union. No Linux or compiler result was created. |
| `git diff --exit-code HEAD --` with the exact named source paths, then `git rev-parse HEAD` | No named-source diff. The revision remained `501c937b4bb6348a5a7daf575493779c188712f8`. |

No product test suite ran in this design task. The supplied reviews' test and syntax results are attributed evidence only. This task did not repeat or certify those results. The new scripts performed static document and input checks only. Actual compilation and retention validation remain open.

The required future gates remain as follows.

- Independently review each implemented pure unit and its tests. Passing synthetic input is not evidence of retained compiler output.
- After VM release, compile the frozen public representatives with GCC and Clang at O0 and O2 on native AArch64 and x86-64. Retain exact output identities and complete readbacks. Run actual byte corruptions and size-preserving declaration mutations.
- Measure output size, parser work, peak memory, compiler time, and deterministic repeated builds. Refuse a limit failure or a different Q for the same K. Keep unsupported profiles visible.
- Inspect the actual collector plugin after the fixed native installer exists. Independently review complete directory traversal and use of the same arrays by operational indexes.
- Bind I into B only after trusted worker completion. Use controller-owned issuance and execution registries. Recompute inspection from immutable actual bytes for cache reuse.
- Freeze the full new source and import closure, bytecode policy, toolchain inputs, runtime dependencies, launch profile, exact launch specification, accepted case, and full outcomes. Do not expand the old nine-file or ten-file digest algorithms.
- Preserve F2 per-trial identities and the installed applicability rule. Public implementation calibration does not become exact-artifact calibration for another binary.
- Keep full capture review OPEN after provider screening. Keep live collection, freshness calibration, deployment, recovery, localization, and milestone acceptance outside this verdict.
- Complete every SPEC.md section 9 requirement. M4, the T0 through T3 report, every baseline, costs, failures, publication, commitments, and `phoenix-eval --replay` remain required.

The process exceptions are explicit. The direct task rule replaced the skill's nested-model exploration, synthesis, and review steps. I used the [Poteto skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md), its Investigation workflow, the how guide, Boundary Discipline, and the prose guides. Boundary Discipline led to the bytes-only consistency API and separate trusted issuance. The task list is [todo.md](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/todo.md). The throughput checkpoint is not applicable to this read-only investigation.

The direct task's named-input restriction replaced the general session-history, STATUS, LOG, and recent-commit checklist. I did not read those histories or the internal-space baseline. Therefore I make no baseline-change claim. The general requirements to update repository progress files, use other audit paths, commit, push, or seek additional agents did not apply to this task. All decisions and exceptions are recorded here because only the assigned audit and temporary directories were writable.

The requested model and Standard tier are supervisor settings. This report does not independently attest model routing. No model, agent, nested session, model CLI, API, provider, scheduling mechanism, or subprocess wrapper for a model was invoked. No service setting changed.

I read no sealed source, held-out input, private run, Author output, Author log, source archive, session history, prior task event, prior stderr, or summary file. I read only the named public reports where explicitly requested. No credentials were read. No Docker, Colima, Ghidra, compiler, target, network provider, commit, push, tag, or branch change ran. Ordinary shell and Python children all completed synchronously. No background child was started or left running.

Only `/Volumes/PhoenixWork/audit/m2-compiled-data-design-astra-20261112` and `/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112` received writes. The pre-existing options.md input was unchanged. This report supplies architecture decisions and static evidence. It supplies no Phoenix success measurement or project-completion claim.

The final command `.venv/bin/python -B /Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/verify_outputs.py` passed. It checked all four deliverables, their local links, code fences, proposed layout counts and member bounds, and unchanged identities for all 24 inputs. [final-check.json](/Volumes/PhoenixWork/tmp/m2-compiled-data-design-astra-20261112/final-check.json) records the output lengths and SHA-256 values. This is document verification only. It does not close any Linux or production gate.
