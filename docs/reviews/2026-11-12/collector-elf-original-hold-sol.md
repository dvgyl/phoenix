Phoenix needs a passive ELF reader before complete compiled-table readback can proceed. This independent review found a rejection gap. The code-only verdict is HOLD at `75b42cf8b1da83b2090be8a7031216826986ba1f`.

Compiled retention is NOT ESTABLISHED. Production remains HOLD. The full capture review remains OPEN after provider screening. This review does not replace that review. SPEC.md section 9 remains open.

The bounded review is complete. It used public synthetic bytes only. It did not compile or execute a target. All owned check processes have ended. The review ended before 2026-11-13 00:56:47 UTC.

**F1. Medium. Rounded mapping checks omit unsectioned relocation destinations.**

[collector_elf.py, line 1271](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:1271) checks only the exact PT_LOAD for an eight-byte runtime write. Lines 1272 through 1276 check alignment, PF_W, and PF_X. They do not call `page_mapping`. Section validation calls that operation at [line 687](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:687). A destination without an allocated section misses those checks.

The independent fixture has a writable load at ELF virtual address `0x800000`. Its file offset is `0x30000`. Its file and memory sizes are `0x28000`. The relocation destination is `0x821000`. Exact translation gives file offset `0x51000`.

A second read-only load starts at virtual address `0x828800`, with file offset `0x68800` and size `0x800`. The exact load intervals are disjoint. For the reader's existing 65536-byte test granule, the second load covers the destination after rounding. It maps that destination to different file bytes at `0x61000`.

The reader returns `CollectorElf` for this conflict on machines 62 and 183. It also accepts two related controls. One adds executable coverage over the destination. The other adds zero fill over the destination. Adding a data section at the same destination makes each control reject with `ambiguous_mapping`. Thus, the rejection depends on section coverage rather than the complete runtime write inventory.

The six controls in [destination-mapping-controls.log](destination-mapping-controls.log) reproduce this result. Their six section-covered controls reject. Two coherent mapping controls pass. [page-model-initial.log](page-model-initial.log) adds two accepted writes on the rounded installer page. These are eight failed rejection controls for F1.

This finding uses the reader's own candidate granules and mapping rules. It does not assert an approved Linux page size or observed loader behavior. The current unit is passive and issues no authority. The defect still blocks code acceptance because the declared write validation is incomplete.

Apply the same full-span page check to every runtime relocation destination before adding it to the relocation index. Keep the exact load, alignment, protected-object, and metadata checks. Preserve these controls as permanent tests for both machines. Review the corrected revision before U2 relies on it.

**O1. Low. Executable section permissions remain an open contract observation.**

Changing the literal `.got` section flags to `SHF_ALLOC | SHF_EXECINSTR` also returns `CollectorElf`. Both relocations still write to that section in a PF_R | PF_W load. [test_additional_controls.py](test_additional_controls.py) preserves both failed conservative rejection controls.

At [line 379](/Volumes/PhoenixWork/worktrees/m1-ci-reliable/phoenix/observe/collector_elf.py:379), an executable section bypasses the data-only executable-page exclusion. The later relocation check uses segment flags only. The design explicitly requires stronger checks for consumed objects. Its rule for other executable section declarations is less explicit. I record this observation separately. I do not count it as a second confirmed defect. Profile approval must resolve this rule without using Darwin as Linux evidence.

The independent builder is [literal_elf.py](literal_elf.py). It uses literal ELF fields and separate file and virtual address values. It does not use a product serializer, writer schema, source reader, or product expected object. Its section order, addresses, nonempty table contents, and relocation order differ from the supplied fixtures. It covers all 47 fixed table names and dimensions on both machines.

The independent controls check complete header, program, section, symbol, dynamic, and RELA observations in input order. They check immutable nested records and exact raw bytes. They check required export mirrors, unversioned exports, SysV bucket membership, collisions, cycles, dependencies, and arbitrary symbol-name bytes. Every table symbol and pointer has separate negative controls. Every directory scalar has a mutation control.

Bounds controls cover exact positive integer limits, False and True, floats, subclasses, missing slots, uninitialized frozen objects, excessive counts, and 10000-level nested input objects. The type guards reject these malformed inputs without invoking their methods. Additional controls check exact physical storage, name, symbol, hash, relocation, and row capacities. They check scalar and byte work limits before dependent access. Large `p_memsz` values cause no proportional allocation. A complete eight-byte write must still satisfy F1 after correction.

The tests include 4000 deterministic structure mutations and 400 deterministic arbitrary-byte cases. Each checks repeated results. No unexpected error occurred in those controls. Separate fault injection confirms that RuntimeError, AssertionError, TypeError, and ValueError remain visible. Instrumented call controls detect an attempted ambient operation, then confirm that the parser makes no such operation. Source imports are limited to `array`, `bisect`, `dataclasses`, `struct`, and `typing`.

These checks support the stated bounds and error behavior. They are not an exhaustive proof. File and record caps do not prove a total Python memory bound. No peak memory or Linux compatibility measurement is claimed.

The check results are as follows. Counts are local test counts, not Phoenix evaluation results.

| Check | Observed result |
| --- | --- |
| Actual frozen checkout tests, `existing-confirmed` | 1025 passed. Child exit 0. |
| Independent final set, `independent-final` | 2148 passed. Ten rejection expectations failed. Child exit 1. Eight failures reproduce F1. Two are O1. |
| Additional literal inventory edges | 12 passed. Child exit 0. |
| Ruff format and Ruff lint | Both passed for the two new Python files. |
| Strict mypy | Passed for the two new Python files. |
| Existing-test line coverage | 663 of 667 statements. |
| Independent-final line coverage | 665 of 667 statements. This coverage does not override F1. |

[Check commands](check-commands.json) records the exact argv, working directory, scoped environment, child exit code, time, and log name for all 16 recorded commands. Each shell sourced `/Volumes/Extreme Pro/Phoenix/env.sh`. [review-env.sh](review-env.sh) then set task-specific temporary and cache paths. Python used `-B` and `PYTHONDONTWRITEBYTECODE=1`. The bytecode prefix was absent before and after. Every pytest command used an explicit root, confcutdir, and fresh basetemp.

The source test command used the actual checkout path. The independent commands used only this exact audit root. They imported the actual frozen product module. The tests assert its path and SHA-256. The original source suite was repeated with a unique retained coverage database at `existing-confirmed.coverage`.

All failed setups and controls remain preserved. The first independent run had 2100 passes and six control defects. Four mutations wrote unchanged mirror values. Two removed only an unused static import. [The correction record](setup-and-control-corrections.md) explains the separate v2 file. The original test file and log remain unchanged.

The mixed-root `combined-final` command failed before tests ran. Pytest tried to inspect a common audit parent. The installed guard denied a stat call on a protected sibling. No private content was read. [The setup record](combined-setup-failure.md) and full log remain preserved. The guard was not inspected, changed, or bypassed. This setup failure is not a product finding. Separate exact-root commands corrected the setup.

The initial temporary coverage database was reused between early runs. Their exported JSON reports and logs remain separate. I do not claim that every early raw coverage database was retained. The final independent database was copied to `independent-final.coverage`. The final source repetition used its own database. An initial read of absent `tests/conftest.py` and an existing-directory mkdir warning are also recorded. No earlier report or failed log was replaced.

The source identity was checked before and after. HEAD remained `75b42cf8b1da83b2090be8a7031216826986ba1f`. The tree remained `7b30b11afe24668e489e1dad1bad1797ee58d9b7`. The checkout was clean at both checks. The base is `d736ef8728d474cf3bb7d050bb0a1d173f54a034`.

Only the following five paths differ from the base. All 230 other base tracked files are unchanged. This preserves the existing policy hashes, readers, schemas, native collector headers, targets, dependencies, and tools. [The complete diff](source-diff.patch) includes the complete new unit and progress appends.

| Path | Bytes before and after review | SHA-256 before and after review |
| --- | ---: | --- |
| `phoenix/observe/collector_elf.py` | 53108 | `a4ceff84e6dd3a7762fb6115d46c644bc72add234c083d1d7f09a0c53b380487` |
| `tests/test_observe_collector_elf.py` | 42956 | `22bd497cc36ab67cfc4616d2ea327c8ddc06549273824ea50589099f986de3ed` |
| `docs/adr/0041-passive-collector-elf.md` | 10645 | `9a964a0e4a7ff7e5a90305c41969b14e285f5209fe12be4ce66cbce748e2ca57` |
| `docs/STATUS.md` | 8423 | `c5aeeeaffbbcfe44ffbe6fae04bc772b1af94bbce71e0c5cee42c1cd0f4477f1` |
| `docs/LOG.md` | 59145 | `78d8639dff5663d0d9b0412067ba9c8c86bfdf70871f64ce658cbd2ff4a4cea4` |

Both progress prefixes match the base. STATUS has 489 appended bytes. LOG has 1760 appended bytes. LOG includes the writer's 870-byte entry and the parent's 890-byte verification entry. The final LOG hash therefore differs from the writer's earlier report. I do not describe the final LOG as only the writer's own append.

[Source before](source-before.json) and [source after](source-after.json) contain the full source identities and prefix checks. The latter also verifies the four exact design hashes and the writer report hash against the named parent records. I read the complete source, tests, ADR0041, four design documents, writer report, and named parent-check records. I did not rely on the writer's tests or exit status as independent assurance.

The writer and ADR0041 correctly state that the fixtures are synthetic. They do not claim actual GCC or Clang retention. Their existing permission description does not establish F1's missing rounded destination checks. The parent's 2434-test result is attributed evidence only. This review did not rerun that broader set or the full `scripts/check` gate.

A coherent fabricated ELF passes this parser by design. Its witness contents, D, R, N, and complete logical record are not decoded in U1. Stale on-disk pointer words can also pass while changing input identity. These results cannot prove compiled retention, source authenticity, trusted issuance, actual collector table use, or runtime capture.

Both Linux profiles remain test-only. Candidate granules 4096, 16384, and 65536 are assumptions. No pinned Linux kernel or loader evidence was read. No actual Linux GCC or Clang output was checked. U2 still needs complete logical readback. U3 and U4 need fixed witness inputs and native compiler evidence. U5 needs trusted issuance and proof that the collector uses these arrays. Full capture review remains OPEN. Production remains HOLD. No milestone or SPEC section 9 result is accepted.

The Poteto Investigation workflow was applied within the user's restrictions. Prove It Works led to direct imports, retained counterexamples, and source identity checks. Test Behavior, Not Implementation led to literal input construction and public result checks. The user prohibited nested models and source writes. Those instructions replaced the skill's model delegation and edit steps. The throughput checkpoint is not applicable to this read-only review.

No nested model, agent, model CLI, API call, session, or dispatcher was invoked. Standard service was requested. No service setting changed or Fast mode was enabled. Host model routing was not independently attested. No target execution, compiler, linker, Ghidra, container, VM, input-plugin loading, network request, or credential access was used.

No sealed source, held-out input, source archive, private run, Author content, session history, dispatcher events, dispatcher stderr, or dispatcher summary was read. The denied stat during setup remains an explicit process exception. All review writes were confined to the two assigned task roots. No source, Git state, policy, recipe, dependency, or tool was changed. The external mounts remained available. Internal free space was 13740068 KiB against the recorded 14432616 KiB baseline. The decrease was below 2 GiB.

DRAINING and PAUSED were absent at the final source check. There is no owned background child or scheduled continuation. [final-check.json](final-check.json) binds this verdict, the source hashes, recorded commands, restrictions, and evidence files.
