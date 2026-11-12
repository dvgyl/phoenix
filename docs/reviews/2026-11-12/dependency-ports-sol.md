The owner requires verified Phoenix v1 completion through SPEC.md section 9. This report checks two exact scope dependency ports. It preserves the agent-sealed corpus. The corpus remains sealed by a separate Author on an honor system.

| Dependency port | Exact reviewed revision | Verdict |
| --- | --- | --- |
| Frame, `agent/m2-observation-frames` | `94caeb4fcd8f7734b11da59c455f4e4d04dc9caf` | PASS for exact-copy identity and public dependency compatibility only. |
| Capture, `agent/m2-capture-admission` | `a2af90cdfb339765b85abb46982a13f0088d5677` | PASS for exact-copy identity and public dependency compatibility only. |

No concrete dependency defect was found. Neither verdict approves production capture, a milestone, or project completion. The full capture review remains **OPEN**. Provider screening blocked that review at `9672a0f414e6fe128f8a1763c66694f551f2e2f5`, with no code verdict. The later data-format PASS covers only its declared parser contract. This dependency review does not replace the blocked review or authorize capture production use.

The frame base is `b85febaa4735c9916a526598b8ba06d0db07919d`. The capture base is `9672a0f414e6fe128f8a1763c66694f551f2e2f5`. The canonical scope revision is `09e984b8608743d87ce9b323a9f6a4a2fad9785b`. These identities come from [revisions.json](revisions.json) and Git objects. No later head was substituted. Local remote-tracking refs match both reviewed revisions. No fetch or server check ran.

Both worktrees were clean at the before and after checks. Every tracked file matched its committed blob and executable mode. The checks covered 192 frame files and 198 capture files. [before.json](before.json), [after.json](after.json), and [source-proof.json](source-proof.json) retain the exact identities. The before and after records compare equal. The checks establish the observed endpoint states. They do not independently attest continuous external process activity.

Each port changes exactly five paths against its stated base. They are `phoenix/observe/scope.py`, `tests/test_observe_scope.py`, `docs/adr/0030-requested-observation-scope.md`, `docs/STATUS.md`, and `docs/LOG.md`. ADR0030 is a tracked addition with mode `100644` in each commit. Its earlier untracked state is resolved. All three dependency files match the canonical revision byte for byte. The retained [frame patch](frame-port.patch) and [capture patch](capture-port.patch) show the complete port changes.

All other paths retain their base Git objects and modes. This includes every other implementation and test file. There are 187 unchanged frame paths and 193 unchanged capture paths. No frame algorithm or other production source changed. In particular, `frames.py`, `capture.py`, mapping, plan, transfer, and wire source retain their host-base bytes. Capture `admission.py` and `runtime.py` also retain their base bytes. This is an identity proof, not a new full-component verdict.

The exact shared handoff hashes are as follows. SHA-256 hashes cover complete file bytes.

| File | SHA-256 | Git blob |
| --- | --- | --- |
| `phoenix/observe/scope.py` | `0cb93cadb4657dfeb776293fe823da439eb186c71978f9c74a7d0c1533867ef4` | `0e44841e86b36139b0e7cdadeb87eb029a7ac97c` |
| `tests/test_observe_scope.py` | `2a2ba8c115aeb852834b69e82da9a82a2303dbdf40e0a620a0ca7188a138bd6b` | `fae19675caa5e3eb89fa2562d6da968be7c4db46` |
| `docs/adr/0030-requested-observation-scope.md` | `66ee8af0d38c090f9edab0e9165c60d84f28d45085a663a7412ce1dfb21e9905` | `e13fe86276ee3f6ffd9aa7174758dd0a1270645a` |
| `phoenix/observe/frames.py` | `08a60db74fdc7d03445b11bfe85ae6f7945d68f8acc8a5bbab042a211030c54b` | `eedaf326a60bf8e9103c82f0ff466f8a08b289fc` |
| `phoenix/observe/capture.py` | `580188caf5f6c45330a15db6f018337c59826d925599e32ca64b53b122133467` | `f09b55246acf48b1a81294ec0472c102c71b4f62` |

Capture `admission.py` retains SHA-256 `9fab8a358b5f7181bcab69bf7c7a00f7274ccb44c0658a7a6d9348908efd9082`. Capture `runtime.py` retains SHA-256 `1de1e6e1df74ef49a19731d916548b75df6be1533fdf13f1e9de55da2a4cc6f2`. Its ten-file admission implementation digest remains `98bf983bb30a6dc9be5cb183eb11776bed32934c53bd5995e7d8aced7e7f0f0f`. The policy digest separately binds the scope dependency.

| Host | Policy digest at prior base | Policy digest after port |
| --- | --- | --- |
| Frame | `cd898d91ab5faca1cd8db27bc675222c36f3f964b2f57585493984858dd5a44b` | `d958b7093004c7688813a350b8a24f0f1be7010fb781bf7da8c044f2dae855c0` |
| Capture | `1b29ff07683570899f162ba73d8546a3fb2913a8b86e3290176775743c88408d` | `51b6e8997390608328232495dcfd4c82b4b422c80cbacc3d5151cfb796780c9e` |

The independent calculation hashes the ordered nine-file manifest and its canonical JSON bytes. It agrees with [policy_implementation_sha256 at line 361](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/scope.py:361) in each host. Each of the nine individual source mutations changes the digest in the independent controls. Those mutations affect reads in the test process only. No source file was changed.

The capture policy digest differs from the canonical frame digest for one pre-existing reason. Its `phoenix/lift/mapping.py` differs between the two prior bases. The frame file has SHA-256 `0de522e7d34c921545c94087eae89a6ef7875079e8d3a16012342fb75c02956b`. The capture file has SHA-256 `400b0c21201a522133767b5505c02dc000d8ed25e7d5390744c1b383bd0df0aa`. Capture [line 326](/Volumes/PhoenixWork/worktrees/m1-development-evidence-fix/phoenix/lift/mapping.py:326) exposes `read_selected_generation`. Both versions retain their own prior-base bytes. The other eight policy source hashes agree across hosts. The differing digest is therefore required by the declared source identity rule.

The concrete compatibility findings are as follows.

| Check | Evidence and result |
| --- | --- |
| Stricter ordinary evidence is retained. | [scope.py line 681](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/scope.py:681) requires positive ordinary evidence. The copied permanent tests pass. Fresh controls reject empty translations for `4889c0`, `31c0`, and `c6c000`. Separate explicit data translations retain their ordinary guards. XABORT and XBEGIN controls still reject. |
| Full plan identity is retained. | The plan source is unchanged. A neutral synthetic fixture preserves every certificate field except policy identity when the test substitutes the prior policy digest. Its full plan bytes remain equal. This comparison isolates the identity change. It does not reconstruct the prior policy algorithm or repeat the historical 16-public-input comparison. |
| Frame rejection exports no local values. | [frames.py line 924](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:924) returns empty local output for each typed rejection. Both public frame APIs use that decision. Existing controls and fresh register, missing-return, duplicate-entry, stale-selection, and stale-receipt controls pass. Both APIs return empty local output on the checked frame failures. |
| Successful synthetic output retains provenance. | Fresh controls bind the current policy to a checked synthetic fixture. The admitted tree retains the policy and scope digests. Every exported local record retains the scope digest. This fixture is private checked-input test construction. It does not authenticate a real capture. |
| Stale capture scope identity rejects. | Capture [admission.py line 203](/Volumes/PhoenixWork/worktrees/m1-development-evidence-fix/phoenix/observe/admission.py:203) rebuilds scope and compares its bytes. Line 224 compares runtime scope and policy identity. Fresh dependency controls reject an old-policy scope, an old-scope receipt, an old runtime policy, and an old runtime scope. Each rejection exports no local values. These checks assess only the dependency identity paths. |
| Host public contracts remain compatible. | Combined scope, frame, observation mapping, plan, observation wire, physical transfer, import and address evidence, lift data-format, and invocation-wire tests pass on both exact revisions. The capture run also repeats the existing 69 public admission tests for dependency compatibility. Their passing results do not certify the full capture component. |

The independent controls are in [test_dependency_controls.py](test_dependency_controls.py). They use public test fixture builders and new assertions. All input values are synthetic. [review_checks.py](review_checks.py) records the commands, environments, output logs, and child exits in [commands.jsonl](commands.jsonl). A successful driver exit alone was not used as a verdict.

| Check run in this review | Actual child exit | Actual result |
| --- | --- | --- |
| Frame combined public tests | 0 | 1,197 passed, 3 deselected. [Log](frame-combined.log). |
| Capture combined public tests | 0 | 1,266 passed, 3 deselected. [Log](capture-combined.log). |
| Frame independent dependency controls | 0 | 27 passed, 5 skipped. [Log](frame-independent.log). |
| Capture independent dependency controls | 0 | 32 passed. [Log](capture-independent.log). |
| Ruff check on copied source and tests, each port | 0 each | Both passed. [Frame](frame-ruff.log), [capture](capture-ruff.log). |
| Ruff format check on copied source and tests, each port | 0 each | Two files already formatted in each port. [Frame](frame-format.log), [capture](capture-format.log). |
| Strict mypy on copied source and tests, each port | 0 each | No issues in two source files per port. [Frame](frame-mypy.log), [capture](capture-mypy.log). |
| Git diff check against each exact base | 0 each | Passed before and after. [Frame](frame-after-diff-check.log), [capture](capture-after-diff-check.log). |
| Final identity comparison | 0 | Both clean states, all tracked bytes, modes, branches, heads, and recorded local refs match the before records. [After identities](after.json). |

The three deselections in each combined run are `test_launcher_opt_in_publishes_pair_and_default_stays_legacy`, `test_launcher_rejects_partial_companion`, and `test_public_phase_grid_storage`. The command excludes launcher-named cases and the live Ghidra fixture case. Other lift failure tests use mocked subprocesses or temporary shell stubs. No Ghidra installation or target program ran. The frame independent run skips five capture-only checks because that tree has no raw admission or runtime module.

The supplied full quality evidence was read in full. It reports the following results. These are parent runs, separate from this review's commands.

| Supplied record | Recorded exit and result |
| --- | --- |
| [frame-quality.log](/Volumes/PhoenixWork/audit/resume-20261112/frame-quality.log) and [exit file](/Volumes/PhoenixWork/audit/resume-20261112/frame-quality.exit) | Exit 0. Lint passed. 162 files formatted. Strict types passed for 123 files. 2,040 tests passed and 26 skipped. Reported evaluator coverage is 92.42%. |
| [capture-quality.log](/Volumes/PhoenixWork/audit/resume-20261112/capture-quality.log) and [exit file](/Volumes/PhoenixWork/audit/resume-20261112/capture-quality.exit) | Exit 0. Lint passed. 168 files formatted. Strict types passed for 128 files. 2,114 tests passed and 26 skipped. Reported evaluator coverage is 92.42%. |
| [Frame commit hook](/Volumes/PhoenixWork/audit/resume-20261112/frame-commit-hook.log) | The log says the quality hook passed and identifies commit `94caeb4`. No separate hook exit file was supplied. |
| [Capture commit hook](/Volumes/PhoenixWork/audit/resume-20261112/capture-commit-hook.log) | The log says the quality hook passed and identifies commit `a2af90c`. No separate hook exit file was supplied. |

The parent checked all ten pending files against the canonical pause manifest before resume, as stated in the task. This review checks the resulting commits and tracked ADR additions. The public [saved handoff](public-handoff.md) retains the pause limits. [input-identities.json](input-identities.json) binds that Git revision, the three approved reports, both quality logs and exit files, both hook logs, and revisions.json.

The three older empty-translation MOV and XOR positives remain withdrawn capability positives. Their unchanged broad suites remain red. The scope report records 177 passes with two failures, and 517 passes with one failure, each at exit 1. Those historical suites were not rerun or edited here. Their supported subsets and new negative controls must not be described as making the unchanged broad suites fully green. The old frame local-retention positive also remains withdrawn. Its prior unchanged broad suite retains the expected exit 1. All earlier HOLD records remain intact. This report does not close issues 8 or 9.

All test counts in this report describe local software checks. They are not Phoenix evaluation results, portability measurements, or live capture evidence. No new `phoenix-eval` metric, runtime success claim on main, milestone acceptance, or tag is supplied.

The original contract limits remain in force. [ADR0030 line 52](/Volumes/PhoenixWork/worktrees/m1-preflight-review/docs/adr/0030-requested-observation-scope.md:52) requires complete, faithful raw translation and checked instruction starts. Operation shapes do not prove operand semantics or translation completeness. Local branch certificates identify destinations, not branch conditions. Static root selection does not prove a runtime predecessor. Static import routes identify symbol requests, not providers or resolved runtime slots. This review does not establish independent machine instruction semantics.

All collector, runner, deployment, live lifecycle, full outcome, mapping, callback, and recovery gates remain OPEN. A manifest, supplied dataclass, matching digest, or passing synthetic fixture does not establish which process ran. A trusted pinned runner must bind exact binary, lift, mapping, plan, scope, policy, receipt, raw schema 2 wire, runtime, collector, plugin, QEMU, image, and installed admission identities. Both root addresses need independent classification. The saved root stack target needs an independent entry-time read. The complete process outcome needs exact stdout, stderr, termination, paths, file bytes, modes, and declared invocation checks.

Live evidence remains required for root-read calibration, all instruction guards, instruction size and next-PC checks, all six register fields, role order, recursion, root closure, post-root monitoring, counters, bounds, exact neutral transit, omitted code, callbacks, reentry, and collector mutation controls. A coherently omitted activation with a rewritten receipt cannot be detected by the pure reducer alone. The mapping adapter, collector transport design, runtime process association, deployment binding, and full capture review remain unapproved.

The fixed public GCC and Clang matrix at O0 and O2 remains required. It must retain both operations, all required lengths, every emitted main call, invalid arguments, early returns, empty and cap inputs, standard I/O errors, and rejected development cases. Separate recursion and four-argument patterns, actual disabled-guard and missing-activation controls, three repetitions, native x86-64 and AArch64 checks, and complete outcome comparisons remain required. Preserve the archived v1 observer and accepted oracle identities. Source checks do not replace positive and negative runtime checks for the public switch caller.

The supported profile has six registers, RDI, RSI, RDX, RCX, RAX, and RSP. Four are argument registers. Provider identity, automatic application binary interface type inference, branch conditions, complete indirect target sets, general callbacks, tails, nonlocal returns, nonreturn contracts, signal handlers, threads, R8/R9, vector registers, stack arguments, aggregate values, and memory snapshots remain unsupported or unproved. Local output after rejection remains unsupported. Default lazy-resolution rejection must stay visible. An eager positive requires its own declared invocation and accepted development outcome. Recovery and localization must wait for their integration and live approval gates.

M2 through M4 remain incomplete. SPEC.md section 9 still requires M4, held-out T0 through T3 results against every baseline, costs, a failure taxonomy, publication of the required artifacts, and replay of every headline result. Public runtime gates, sealed adequacy work by the separate Author, baselines, ablations, and independent milestone reviews remain required. This dependency PASS closes none of those gates.

The requested GPT-6.1 Sol role and Standard service tier are launch settings. This report does not independently attest routing. No provider or safety setting changed. No nested agent, commit, push, tag, Docker command, target execution, Ghidra process, model-provider call, network call, private run, or session-history read occurred. All new files are in this audit directory or `/Volumes/PhoenixWork/tmp/m2-dependency-ports-sol-resume-20261112`.

One initial revision-file search traversed audit directory metadata too broadly. Access to four private Author or health directories was denied. No private file content was read. All later reads used exact public paths. No sealed source, held-out input, source archive, private Author output or history, Colima disk, or private audit content was read. Internal free space was 13,067,996 KiB at the recorded check, above the recorded investigation threshold. No storage change was needed.

An optional lint check of the new audit scripts initially returned exit 1 for two import-order errors and one lambda assignment. [The original log](audit-lint-initial.log) is retained. The audit scripts were corrected. [Final lint](audit-lint-final.log) passed at exit 0. The independent controls were then repeated. No repository file needed a change.

The first final-state driver returned exit 1 after its child checks passed. Its last assertion compared Python tuples with JSON lists. The saved before and after JSON records were already equal. The corrected verifier compares normalized JSON records. Its repeated final check passed at exit 0. [Review tool failures](review-tool-failures.md) preserves both audit-script failures and their limits.

The full requested AGENTS.md, SPEC.md, installed poteto-mode skill, three approved public reports, supplied quality evidence, hook logs, and public pause update were read. The [task list](todo.md) records the user limits that replace nested-agent, source-edit, history, and shipping steps. The Prove It Works principle led to direct Git-object comparisons, per-file hashes, executed controls, and final state verification. Its leaf skill was read. Technical-writing and unslop guidance were applied with ASD-STE100 Issue 9.

The following commands reproduce the review checks. They use the fixed revisions in revisions.json. The driver rejects a changed or dirty worktree. All pytest, Hypothesis, coverage, and mypy paths are under the permitted temporary directory. Python bytecode writes are disabled.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-preflight-review
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/python -B /Volumes/PhoenixWork/audit/m2-dependency-ports-sol-resume-20261112/review_checks.py before tests independent quality inputs source-proof after
```

The command arrays in commands.jsonl also reproduce each child check separately. Existing logs record the actual reviewed runs. The report verdicts depend on the identity proof, compatibility results, and stated contract limits together.
