The user requires verified Phoenix completion through SPEC.md section 9. This independent review covers one prerequisite, the complete pure static collector-data unit.

**PASS for the exact data unit at `63dd98589689276ea6761caa84dadc3ab83f7dee`.** I found no concrete defect under its raw-input contract. This verdict follows source inspection, complete-record comparisons, boundary controls, and repeated tests. A command exit alone does not establish this verdict.

**Full capture review remains OPEN after provider screening. Production remains HOLD.** This separate review does not retry, replace, rephrase, or certify that component. No Phoenix metric or runtime success is supplied. M2 through M4 and SPEC section 9 remain incomplete.

I performed the review directly. The requested GPT-6.1 Sol role and Standard service tier are supervisor launch settings. This report does not attest model routing. I started no model, nested session, agent, model CLI, or model-provider call. I changed no safety or provider setting.

The exact review basis is [revisions.json](revisions.json). The worktree is `/Volumes/PhoenixWork/worktrees/m1-ci-reliable`. Its branch is `agent/m2-collector-data`. Its base is `e7c9450bd7f2a891c905048fa46064c684ea05ad`. The `server_verified` field is supplied metadata. I made no network check.

[before.json](before.json) and [after.json](after.json) are equal. All 209 tracked files match their committed bytes at both checks. Git reports a clean checkout. Exactly these five paths differ from the base.

| Path | Verified condition |
| --- | --- |
| `phoenix/observe/collector_data.py` | New complete module. SHA-256 `d5005ac55660660be160181ff89f985e6b02e754bc16a8b9a9c286a5e8cef309`. |
| `tests/test_observe_collector_data.py` | New complete test file. SHA-256 `80cad4b9a32a37e8060dde02aea4d2438d534a1e000dad5bc40e5e30e6a214a0`. |
| `docs/adr/0035-eager-collector-data.md` | New decision record. SHA-256 `1b5667c0fbbed84c935ada56471fb9be3ed51bef6b98117fcb28cf1082c74ba2`. |
| `docs/STATUS.md` | The complete base prefix remains unchanged. |
| `docs/LOG.md` | The complete base prefix remains unchanged. |

Every pre-existing implementation, test, schema, configuration, and pin file remains unchanged from the base. These are endpoint checks. They do not attest continuous activity by another process.

I read AGENTS.md, SPEC.md, the required Poteto skill, the complete 369-line implementation, all 970 test lines, and ADR0035. I read the writer report and its named source-identities.json. I read the corrected Astra design-verdict.md and report.md in full. I read the candidate design and API sections that define the exact data shape, canonical form, bounds, and authority limits. I read the full pure-frame integration report. [input-identities.json](input-identities.json) binds these named inputs and the parent logs. Their writer hashes match. The two progress documents have later parent appends and therefore different hashes.

The corrected F1 through F4 requirements take priority over the earlier candidate. Their build, calibration, compiled-retention, launch, and source-closure requirements remain open. The earlier candidate HOLD and the separate full capture HOLD remain intact.

The concrete review findings are as follows. No finding below requires a source correction for this data unit.

| Area | Finding and evidence |
| --- | --- |
| Exact raw input types and byte bounds | [collector_data.py line 274](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:274) validates both limit records first. Line 285 checks every raw object and length before parsing or hashing. Maxima remain 16 MiB for the original, 64 MiB each for lift and mapping, 512 KiB for the full plan, and 8 MiB for scope. Lower supplied byte limits remain binding. Existing controls reject empty values, subclasses, bytearray, memoryview, and text. Fresh controls reject each default maximum plus one with hashing and reconstruction disabled. They also accept exact lower byte boundaries and reject one byte below them. |
| Limit types and snapshot width | [Line 186](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:186) requires the exact limit record type and an exact positive integer for every field. Values cannot exceed the installed maxima. Boolean and float aliases fail. Snapshot width is exactly eight. The 121 source controls exercise every field of both limit records. |
| Raw reconstruction and installed policy | [Line 295](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:295) reparses lift and mapping, proves addresses, and rebuilds the complete plan. Lines 310 and 320 require exact canonical plan and scope bytes. Scope compilation uses installed source. The unchanged nine-file policy identity is `51b6e8997390608328232495dcfd4c82b4b422c80cbacc3d5151cfb796780c9e`. The coherent old-policy control fails under current policy. Duplicate keys, changed artifacts, removed nested fields, and extra canonical suffixes fail. |
| Complete logical shape | [Line 143](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:143) retains every approved CollectorData field. Its children are the complete TracePlan, ScopeSelection, and ElfImage. The encoder traverses dataclass fields rather than a selected projection. Fresh whole-record controls compare the complete plan, scope, image, geometry, identities, schema markers, and transport limits against independently prepared source records. |
| Roles, imports, gaps, and omissions | The complete nested records retain every entry and transfer role, continuation user, import gap, and omission. ImportBinding retains all 12 fields declared by its installed source. ImportId retains all four fields, including `needed_library=None`. The writer report calls this 13 fields, but its test explicitly lists the correct 12. This is a report counting error, not lost data. Gap records retain original index, Ghidra domain and address, optional ELF address, reason, and disposition. Unknown active guards remain explicit Reject data. |
| Routes and requests | Complete routes retain call site, binding digest, entries, full instruction path, terminal, slot, and request. Shared terminals and suffixes retain every separate route and position membership. The 121 source controls check these cases. Fresh controls accept exact route, omission, path-position, and membership limits and reject one below them without dropping records. Both root-evidence variants remain complete. Ordered registers remain RDI, RSI, RDX, RCX, RAX, and RSP. Empty contracts, eager-only transit, and lazy-unsupported markers remain exact. |
| ELF geometry | [Line 250](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:250) uses the same executable-file envelope as the existing observation mapper. All PT_LOAD memory extents contribute to memory geometry. Complete segment indices, file offsets, file sizes, memory sizes, flags, alignment, and dynamic records remain present. Existing controls retain nonexecutables and memory-only spans. Fresh controls preserve an exclusive end of `2**64` for executable and nonexecutable file-backed spans. No address wraps to zero. Signed dynamic tags at both signed 64-bit extremes and unsigned values at `2**64 - 1` remain exact. |
| Frozen representation and canonical bytes | [Line 131](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:131) creates recursive FrozenRecord objects with tuple children. Fresh recursive checks require sorted unique object names and immutable scalar or tuple children. Their decoded value equals the complete canonical data. Keys are sorted. JSON uses ASCII escapes and compact separators. One final LF participates in the byte limit and SHA-256. Source controls test the exact output boundary. |
| Errors | [Line 366](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:366) catches only the unit's closed refusals and MappingError. Details have at most 512 characters. Fresh malformed integer, Boolean, float, deep nesting, invalid encoding, and oversized integer inputs return data rejections. Fresh coding-error sentinels in mapping, address proof, plan construction, and scope compilation remain visible exceptions. |
| Pure consistency contract | The prepared record supplies static consistency. Its constructor, digest, and FrozenRecord are not authority credentials. The exact top-level control confirms no runtime bias, process identity, provider identity, launch record, or admission authority. A fresh control disables process creation, network sockets, and Path writes during preparation and record conversion. It passes. Later trusted boundaries must reconstruct source and validate authority separately. |

One resource distinction needs an explicit limit. [Line 115](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:115) creates a JSON token before [line 124](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:124) checks its length. Thus the output-byte check is not a pre-allocation check for an individual token. The fresh control at [test_independent_controls.py line 117](/Volumes/PhoenixWork/audit/m2-collector-data-review-sol-20261112/test_independent_controls.py:117) demonstrates a 24,578-byte token under a 2,048-byte data limit. The producer returns `render_limit` and appends no oversized output.

This observation is not a demonstrated contract defect for the accepted source domain. Retained variable import strings pass through the existing strict UTF-8 dynamic reader. [imports.py line 120](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/recover/imports.py:120) bounds each string to 4,096 source bytes. A maximally escaped 4,096-byte control-character string produces the demonstrated 24,578-byte token. Other retained labels are fixed schema text, bounded digests, or fixed source diagnostics. Integers have checked source ranges. Large ignored lift text does not enter CollectorData. A fresh 2 MiB lift-string control verifies this separation. The record method checks canonical length before it allocates its full recursive FrozenRecord.

Lower record limits also need precise interpretation. [Lines 298 and 303](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_data.py:298) check segments after proof construction and plan counts after legacy plan construction. Scope inventory checks follow scope reconstruction. Legacy reconstruction can do work above a caller's lower output count before the unit refuses the result. It still uses bounded raw inputs and the existing static-reader and planner maxima. Fresh controls accept exact full-plan and guarded-instruction counts, reject one below them, and confirm that segment, gap, and full-plan inventory failures stop before scope construction. No accepted result exceeds a supplied lower limit.

The declared data-byte limit bounds the canonical artifact. It does not define total Python resident memory. This review supplies no worst-case peak-memory or wall-time measurement. The later renderer must independently check table storage and generated-header size before materialization. The worker and compiler resource gates remain open. I do not infer those guarantees from the incremental data encoder.

[commands.jsonl](commands.jsonl) contains actual argument vectors, working directories, log paths, and exits. Later records also contain dedicated environment paths. All Python checks use `PYTHONDONTWRITEBYTECODE=1`. The initial 1,130-test run used the inherited external bytecode prefix. I then used a dedicated nonexistent bytecode prefix and repeated the affected suite. That prefix remains absent. This prevents these later test runs from loading a pre-existing cache at that prefix. It is test isolation, not production source attestation.

The command results are as follows.

| Command group | Actual exit | Result and log |
| --- | --- | --- |
| Existing collector controls | 0 | 121 passed. [data.log](data.log). |
| Collector, scope, frames, mapping, plan, wire, and transfer compatibility | 0 | 1,130 passed initially. [affected.log](affected.log). The dedicated-prefix repeat also passed 1,130. [affected-fresh.log](affected-fresh.log). |
| Initial independent controls | 0 | 34 passed. [independent.log](independent.log). |
| Expanded independent controls | 0 | 43 passed. [independent-expanded.log](independent-expanded.log). |
| First high-address expansion | 1 | 3 failed and 44 passed. [independent-final.log](independent-final.log). The repeat before the fixture correction had the same result. [independent-repeat.log](independent-repeat.log). |
| Corrected independent controls | 0 | 47 passed. [independent-corrected.log](independent-corrected.log). The final confirmation also passed 47. [independent-confirmed.log](independent-confirmed.log). |
| Source Ruff lint and format check | 0 each | Passed for the unchanged module and its source tests. [source-ruff.log](source-ruff.log), [source-format.log](source-format.log). |
| Source strict mypy | 0 | No issues in two files. [source-mypy.log](source-mypy.log). |
| Audit-test first lint | 1 | One unused import and two long diagnostic lines. [audit-lint.log](audit-lint.log). |
| Audit-test final lint and format check | 0 each | Passed after audit-only cleanup. [audit-lint-2.log](audit-lint-2.log), [audit-format-final.log](audit-format-final.log). |
| Exact committed diff whitespace | 0 | Passed. [diff-whitespace.log](diff-whitespace.log). |
| Before and after identity checks | 0 each | All 209 committed files match. Exact changed paths and documentation prefixes match. Endpoint records are equal. |

The three high-address failures occurred in my fixture builder before it called `prepare_collector_data`. The public mapping helper added the normal Ghidra rebase to a segment near `2**64`. That synthetic address exceeded 64 bits. The corrected companion omits this unlifted high span. The complete checked ElfImage still retains the span. The corrected controls now reach the producer and verify its exact endpoint geometry. No product source changed. Both failed logs remain intact.

The audit lint failure also remains intact. I removed its unused import and shortened its two diagnostic strings. These changes affect only the new audit test file. No product test failed in this review.

The parent evidence was read in full. Its affected test log reports 1,130 passes. Its diff record reports the exact allowed paths and preserved prefixes. The named commit-hook log reports `Phoenix quality checks` passed, and the named exit file contains `0`. The hook log does not supply expanded test counts. I did not invent a count or rerun runtime-dependent repository checks. The writer report's earlier lint and mypy failures remain in that report.

The final independent controls are in [test_independent_controls.py](test_independent_controls.py). The reproducible command is below. External audit tests use this exact root and confcutdir. They do not scan sibling audit or private directories.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-ci-reliable
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  /Volumes/PhoenixWork/tmp/m2-collector-data-review-sol-20261112/checks.py repeat \
  .venv/bin/python -B -m pytest \
  --rootdir=/Volumes/PhoenixWork/audit/m2-collector-data-review-sol-20261112 \
  --confcutdir=/Volumes/PhoenixWork/audit/m2-collector-data-review-sol-20261112 \
  /Volumes/PhoenixWork/audit/m2-collector-data-review-sol-20261112/test_independent_controls.py \
  -q -o cache_dir=/Volumes/PhoenixWork/tmp/m2-collector-data-review-sol-20261112/pytest
```

All later gates remain required.

| Gate | Remaining requirement |
| --- | --- |
| Native declarations and renderer | Define fixed native types. Render every logical field as typed data. Independently decode generated output. Check every string, integer, tag, slice, table, byte limit, and lower limit. |
| F3 compiled retention | Retain the complete exported `phoenix_collector_data_v1` directory. Traverse every table. Independently read complete logical data from actual compiled output. Bind inspection to the actual plugin and receipt. Source-byte retention alone is insufficient. |
| F1 build consistency and issuance | Separate ConsistentBuild from CheckedBuild. Require controller-owned issued build pins and fresh artifact checks for cache reuse. Test source closure, pins, architecture, toolchain, links, missing exports, changed inputs, bounds, and deterministic output. |
| F4 source and process association | Freeze the implemented source and import closure. Control interpreter, bytecode, compiler, linker, headers, and libraries. Preserve the existing nine-file policy and ten-file admission algorithms. Bind the fixed launch profile, exact expanded launch spec, accepted case, actual process, complete outcome, and trusted execution receipt. |
| Native collector | Independently review instruction witnesses, immediate transfer confirmation, shared role order, six fields, guards, routes, counters, root entry read, return read, closure, reentry, omissions, callbacks, and failure retention. Every rejection must export no local facts. |
| Full capture review | Remains OPEN after provider screening. This data-unit PASS grants no capture, tree, recovery, or localization admission. |
| Live and public controls | Run the full frozen public compiler and optimization matrix. Retain both operations, all required lengths, every emitted main call, invalid inputs, stdio errors, recursion, four argument registers, distinct RAX, stack storage, shared roles, direct and indirect calls, eager routes, and default lazy rejection. |
| Read, guard, and lifecycle controls | Test real prior-store reads, independent root anchors, changed and unreadable return words, page boundaries, scratch reuse, next PC, dormant translations, retranslations, route crossings, holes, all limits, timeout, kill, missing finalization, write failure, duplicate response, second vCPU, and root reentry. Keep partial artifacts and failures. |
| Mutation and complete outcome controls | Mutate missing activations, role order, snapshots, root anchors, and guards. Recompute coherent synthetic checksums where required. Compare stdout, stderr, termination, all final paths, contents, and modes with both accepted independent oracle engines. Repeat supported comparable cases three times. |
| F2 calibration and deployment | Record each trial's actual binary, scope, build, runtime, launch, outcome, and artifact identities. Apply an installed common-context rule. Keep implementation calibration distinct from exact-artifact calibration. Require independent review and native x86-64 and AArch64 evidence before production deployment. |
| Preservation | Retain archived v1 controls and oracle identities. Keep withdrawn empty-translation and local-retention expectations withdrawn. Keep every earlier HOLD and failure record. Original-code witnesses and collector artifacts stay outside reconstructed C and package archives. |
| Phoenix completion | Complete M2 through M4. Publish the required T0 through T3 results against all baselines, costs, failure taxonomy, and artifacts. Verify commitments and replay every headline result through `phoenix-eval`. |

The old broad scope and frame suites were not rerun or edited. Their reported failures remain historical evidence in the named pure-frame review. This report does not convert their withdrawn capability expectations into passes.

I used the required [Poteto skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md) and its Investigation workflow with the user's limits. The prohibition on nested models replaced all delegation steps. Boundary Discipline led to separate raw-data consistency from later authority. I read that principle's leaf skill. The technical-writing and unslop guides informed the report. ASD-STE100 Issue 9 governs new prose. The task list records these constraints. The throughput checkpoint is not applicable because this is a read-only investigation.

Only this audit directory and `/Volumes/PhoenixWork/tmp/m2-collector-data-review-sol-20261112` received new files. No source edit, commit, push, tag, compiler, target, Ghidra command, Docker command, or real provider call occurred. I read no sealed source, held-out input, source archive, private run, Author output or history, or session history. I did not read or hash pre-existing event, stderr, or dispatch artifacts. The private Author retained the VM. The corpus remains agent-sealed on an honor system.
