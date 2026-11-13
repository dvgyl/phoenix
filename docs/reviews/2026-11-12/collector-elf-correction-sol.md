Phoenix needs independent evidence for the complete corrected passive ELF reader. The code-only verdict is PASS at `11cb51b06ff181209c7a9e23ed9bb6f758cea839`. No actionable defect remains in the reviewed unit. This verdict includes the complete reader, its tests, ADR0041, and the F1 and O1 corrections.

Actual compiled retention is NOT ESTABLISHED. Both Linux profiles and production remain HOLD. Full capture review remains OPEN after provider screening. This review does not retry, replace, or bypass that review. No milestone or SPEC section 9 completion follows.

The complete product module has 1,517 lines. Its test file has 1,567 lines. I read both files in full. I also read AGENTS.md, SPEC.md, ADR0041, the complete stable native data header, both stable header Python modules, the four final design documents, the prior independent HOLD, the final Astra advice, and both required root correction records. The design hashes match ADR0041. [Required record identities](required-records.json) binds those records.

The final findings and their treatment are as follows.

| Item | Prior severity and status | Final treatment |
| --- | --- | --- |
| F1. Rounded mapping checks omitted unsectioned relocation destinations. | Medium. Confirmed defect in `75b42cf`. | Resolved in the reviewed code. All eight original failed rejection controls now pass unchanged. |
| O1. An allocated executable `.got` declaration had a writable non-X load. | Low. Separate contract observation. It was not a second confirmed defect. | Resolved for this conservative test profile by the explicit Astra option 1 rule. Both original conservative rejection controls now pass unchanged. No Linux behavior is inferred. |
| New actionable findings | None. | No product edit is requested by this review. |

F1 uses the exact file offset returned by `file_span(where, 8)` at [collector_elf.py line 1279](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1279). The original alignment, writable-load, and non-executable-load checks remain. [Line 1285](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1285) checks all eight bytes through every existing page map with `executable=False`. The call precedes target-section checks and relocation indexing. It applies to relative, GLOB_DAT, and JUMP_SLOT writes on both machines. It does not depend on section coverage.

The new public byte controls reject conflicting file translations, rounded executable coverage, and rounded zero fill. They test three alias distances. The distances affect all three candidates, only 16384 and 65536, or only 65536. The candidates remain exactly 4096, 16384, and 65536. Coherent aliases pass at each distance. Both section-covered and unsectioned controls run. Explicit valid `sh_info` metadata also runs. The explicit metadata controls use a nonallocated NOBITS target extent that contains the relevant relocation range. They test containment metadata, not runtime section permissions.

The tests cover all accepted relocation kinds. They include JUMP_SLOT in the main RELA range and in the PLT range. Exact file-end success remains valid. Destinations with only zero, one, or seven file-backed bytes refuse. Separate fault controls reach the actual write path, require width eight and `False`, and confirm that unexpected exceptions remain visible.

The full-span helper controls put a conflict or hole at each of the eight byte positions. These controls test `_PageMap.check` directly. They do not claim that every fabricated helper interval can pass the public ELF envelope. An aligned eight-byte write cannot straddle any of the three page granules. The public byte controls and the helper controls therefore have separate roles.

O1 builds one sorted executable-section interval index at [line 1172](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1172). It includes positive-size sections with both SHF_ALLOC and SHF_EXECINSTR. It includes NOBITS declarations. [Line 1286](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1286) queries the predecessor of the write end. The envelope already rejects overlapping positive-size allocated sections. This precondition makes the single-predecessor query sufficient.

The adopted rule rejects every nonempty intersection between `[where, where + 8)` and such a section. It ignores zero-size and nonallocated declarations for this test. Endpoint adjacency passes. An unrelated executable declaration in a non-X load can still pass. The rule does not impose global section-to-load flag agreement. Its reason remains `relocation_contract`. Its fixed detail is `A relocation touches allocated executable section bytes.` This matches the final Astra decision and ADR0041.

The new public O1 matrix has 800 cases. It checks both machines, all four relocation placements, zero and explicit target metadata, ten boundary shapes, and five section type and flag combinations. It covers first-byte and last-byte intersections, containment, exact intersection, endpoint adjacency, empty declarations, and unrelated declarations. Separate controls put several disjoint executable sections inside one write. Other controls cover an unsigned end equal to `2**64`, extent overflow, and the allocated-section disjointness precondition. A bounded direct interval oracle agrees with the indexed predicate in 40,960 comparisons. This helper comparison supplements the public parser controls.

Protected objects and ELF metadata remain protected. The unchanged old controls exercise all 47 fixed local table symbols and pointer cells on both machines. The correction preserves exact relative kinds, symbol zero, exact addends, duplicate refusal, and input order. [Line 1402](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1402) still requires every pointer. [Line 1444](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1444) still checks protected objects and metadata for every relocation.

New controls test ordinary writable version storage, directory scalars, dynamic metadata, section-header metadata, and complete string-table spans. Feasible one-byte metadata intersections reject. Exact metadata endpoint adjacency passes. Exact protected-object adjacency also passes. An attempted file alias of the ELF header refuses earlier because positive-length load file ranges must be disjoint. These earlier refusals remain explicit in the controls. They are not counted as evidence that the later metadata predicate ran.

The new maximum-count controls parse actual literal ELF bytes with 4,096 sections and 262,144 relocations on each machine. They retain all 47 directory cells. They verify all main relocation row indexes and the separate PLT row index. A counting list observes section traversal only while the actual relocation method runs. It records exactly `3 * 4096` section visits on each machine. The method and its mapping and interval queries execute normally. No per-write section traversal occurs. Lower section and relocation limits still refuse.

Source inspection supports added O1 work of `O(S log S + R log S)` and extra index storage of `O(S)`. The F1 queries use the existing three sorted page maps. An eight-byte query can visit at most eight positive-length integer-address intervals per candidate. Other existing metadata and protected-object queries remain indexed. These are structural work bounds. No timing benchmark, peak memory measurement, or total Python memory guarantee is claimed.

The observed checks are as follows. These are local review counts, not Phoenix evaluation results.

| Check | Result |
| --- | --- |
| Corrected checkout tests for ELF, header, collector data, frames, and scope | 2,472 passed. Child exit 0. |
| Unchanged old independent behavioral controls and inventory edges | 2,169 passed. One historical identity control deselected. Child exit 0. |
| Final additional independent controls | 1,344 passed. Child exit 0. |
| Original old identity control, run separately without edits | One expected failure. It reports only the old-to-new source-hash difference. Child exit 1. |
| Initial new control run | 1,204 passed and 48 failed. All failures concern the new metadata alias fixture or its expected reason. Child exit 1. Preserved. |
| Ruff lint and format on the two product Python files | Passed. |
| Strict mypy on the two product Python files | Passed. |
| ELF statement coverage from checkout tests | 668 of 672 statements. |
| ELF statement coverage from unchanged old controls | 670 of 672 statements. |
| ELF statement coverage from final new controls | 659 of 672 statements. |

The original prior suite had 2,148 passes and ten failed rejection expectations. Eight failures were F1. Two were O1. In this review, all ten original rejection expectations pass unchanged. The one old identity test still expects `a4ceff84e6dd3a7762fb6115d46c644bc72add234c083d1d7f09a0c53b380487`. It remains unchanged and historical. Running it separately shows the exact hash disagreement in [historical-identity.log](historical-identity.log).

The final old behavioral run contains the prior 2,147 other passing controls, the ten prior failed rejection controls, and the twelve later literal inventory edge controls. This gives 2,169 passes. [The new identity control](test_independent_corrected_v2.py) checks the current exact module path, new digest, import closure, candidate set, and absent bytecode prefix separately. No source-identity change weakens an old behavioral expectation.

The first new metadata controls used overlapping load file ranges for ELF header aliases. They also omitted file padding for new section-table mappings. The reader correctly refused those files before the intended later check. [control-corrections.md](control-corrections.md) records the fixture corrections. The initial test file, its copy, failure log, command, result, and coverage database remain. The final v2 file is separate. No old test, fixture, report, or failed log was edited. No pytest collection or setup failure occurred in these runs.

The exact test commands are in [existing.command.json](existing.command.json), [old.command.json](old.command.json), [new-v2.command.json](new-v2.command.json), and [historical-identity.command.json](historical-identity.command.json). Each record includes argv, working directory, scoped environment, and its retained log and result. [run_checks.py](run_checks.py) reproduces those commands after [review-env.sh](review-env.sh) is sourced.

The affected checkout command runs `.venv/bin/python -B -m coverage run` against the five exact test paths. It uses the checkout as both rootdir and confcutdir. The old command uses the old audit root for both. The final new command uses this assigned audit root for both. Every run has a distinct external basetemp and coverage database. Pytest cache writes and automatic plugin discovery are disabled. Hypothesis is explicitly registered. The deterministic seed is 20261113.

Temporary files and cache locations remain under the assigned temporary root. `PYTHONDONTWRITEBYTECODE=1` and `-B` are set. The task-specific bytecode prefix was absent before every test command and at the final check. The actual frozen checkout module was imported. No product serializer, source reader, or native loader supplies the independent expected bytes. The retained independent builder uses literal ELF fields. New tests reuse that unchanged independent builder and make explicit byte mutations.

The source identities before and after are as follows.

| File | SHA-256 before and after |
| --- | --- |
| `phoenix/observe/collector_elf.py` | `dae95a30f96c556a1731a59edada95e4622991889ffcfdfa576bf773a17929eb` |
| `tests/test_observe_collector_elf.py` | `676c42f4ee0e59aa55f9ecbc6728298fc7de6952242196a67b49ebf352403f1d` |
| `docs/adr/0041-passive-collector-elf.md` | `64cd2506a23174b0248349d904b276b0d02fee957aa1c80bb06989d09fa2d7db` |
| `phoenix/observe/collector_header.py` | `fa5d25fb5c910796127bb29a17f5f111b6555beb9dc02a82ad75611747578684` |
| `phoenix/observe/collector_header_read.py` | `087c9e62fa56ffbca7757c50577368fa0370eed744dd4aa47325e3ed7164d669` |
| `phoenix/observe/native/collector_data_v1.h` | `2e278603d75d6cd436aedc72af3f1903334dadc37d6d8847dfd3dd825018acb3` |

HEAD remained `11cb51b06ff181209c7a9e23ed9bb6f758cea839`. The tree remained `f0bb72fd716b86ef01d5b8b7a2e64c33ee02a2f5`. The checkout was clean. All 235 tracked file byte hashes match HEAD and the initial snapshot. [source-before.json](source-before.json), [source-final.json](source-final.json), and [source-comparison.json](source-comparison.json) record these checks. They also bind unchanged prior test, fixture, and report bytes.

Only five paths differ from `d736ef8`. They are the reader, its tests, ADR0041, STATUS, and LOG. All 230 other base tracked files are unchanged. The same five paths contain the correction from `75b42cf`. All older progress-file prefixes remain intact. No prior parallel addition, policy hash, source reader, schema, native declaration, recipe, dependency, or tool changed. [complete-unit.patch](complete-unit.patch) and [correction.patch](correction.patch) retain the exact comparisons. Root retains all edit and Git authority. This reviewer made no product or Git mutation.

The parser still preserves complete header, program, section, symbol, dynamic, dependency, export, and relocation inventories in the specified order. The unchanged independent controls also verify frozen nested records, exact limits, lower limits, finite refusal reasons, bounded details, malformed input objects, deterministic mutations, and visible programming errors. The new tests supplement those controls. A successful test exit alone did not determine this verdict.

This PASS proves only bounded passive representation checks under the stated test contract. A coherent fabricated ELF can pass. U1 does not decode the complete logical record, compare the compiler witness, or authenticate D, R, N, source provenance, build issuance, or actual table use. Stale pointer words can change input identity without changing the passive relocation interpretation. A result constructor grants no authority.

Root must still complete the separate full repository quality gate. This review ran the relevant affected tests, Ruff, and strict mypy. It did not run `scripts/check` or certify repository-wide coverage. U2 complete logical readback, U3 fixed witness checks, U4 actual GCC and Clang retention and Linux page-granule approval, and U5 trusted issuance and native traversal remain separate gates. Calibration, deployment, live capture, production, all milestones, M4 publication, and replay remain outside this verdict.

I used the installed [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md) and its read-only Investigation workflow. Prove It Works led to direct frozen-tree imports and complete byte identity checks. Test Behavior, Not Implementation led to literal byte controls and public result assertions. Model the Domain led to explicit interval and mapping case tables. The work-bound probe is separately identified as instrumentation. The user prohibited nested models and product edits. Those limits replaced the skill delegation and edit steps. The throughput checkpoint is not applicable to this read-only investigation. [todo.md](todo.md) records the workflow.

Standard service and GPT-6.1 Sol were requested. No service setting changed and Fast mode was not enabled. Host model routing was not independently attested. No nested model, agent, model API, model CLI, session, or dispatch wrapper ran. No network, credential, compiler, linker, target, Ghidra, input-plugin load, container, or VM operation ran. The installed sandbox guard was not inspected, changed, probed, or nested.

No sealed source, held-out input, source archive, private run, Author material, Codex session, archived session, dispatcher event, dispatcher stderr, or dispatcher summary was read. Directory listings exposed filenames only. All writes stayed in the two assigned roots. General instructions to edit project progress files, commit, push, or dispatch a reviewer did not apply to this read-only task. The original HOLD remains unchanged.

DRAINING and PAUSED were checked at the task roots, checkout, workspace root, and `audit/continue-v1` before new check batches and at final verification. No such sentinel was present at those locations. No separate sentinel path was supplied. This is a check of those named locations, not a search of private directories. No pause instruction arrived.

The bounded review ends before 2026-11-13 00:56:47 UTC. All owned test processes have ended. No background child or scheduled continuation remains. [final-check.json](final-check.json) binds the final source identities, commands, evidence, scope, and completion time. All later gates remain open.
