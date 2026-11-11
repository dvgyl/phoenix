The owner requires verified Phoenix completion through SPEC.md section 9. This independent review checks the revised pure-frame contract at one exact revision. It preserves the agent-sealed corpus.

**PASS for the revised pure-frame contract.** I found no remaining concrete defect in the owned block under the stated canonical checked-input contract. F1 and F2 are closed by the declared capability restriction. Every rejection exports no local values. This verdict gives no production or milestone approval.

**Production admission remains HOLD.** The exact scope dependency has its own known XABORT HOLD in issue8, as stated in the task. That defect is not a new frame finding. The separate scope correction must finish. The parent must then port its exact final files and run the combined checks. The byte boundary, collector, live controls, hardware checks, and inference gates also remain open.

The reviewed HEAD is `b85febaa4735c9916a526598b8ba06d0db07919d` on `agent/m2-observation-frames`. The checkout was clean before and after the checks. All reviewed files match HEAD and retain their initial digests. The local remote-tracking ref has the same full revision. No network check of the remote was made. See [before.json](before.json), [after.json](after.json), and [identity-checks.json](identity-checks.json).

| Owned file | SHA-256 |
| --- | --- |
| `phoenix/observe/capture.py` | `580188caf5f6c45330a15db6f018337c59826d925599e32ca64b53b122133467` |
| `phoenix/observe/frames.py` | `08a60db74fdc7d03445b11bfe85ae6f7945d68f8acc8a5bbab042a211030c54b` |
| `tests/test_observe_frames.py` | `82afd2cfdfba3f0db57414f766cacfc7708f3997b4bc43a8b272e0ca83a49c90` |
| `docs/adr/0031-checked-frame-reduction.md` | `08417759fefb1cae481fa0f29ac38b512192f07f54cb63118c1e4ec30f5f12c1` |

Scope and its tests exactly match `b42a7a294220cec9cb3a9e52134dcc4179c83949`. Their digests are `053651a6a8dadf178dfb564a8702ab903ea28d51bb965faf1c4e324b07d5787c` and `409e88f3945139c812ed24216b4467e70c56daad9c075870485083b26d612e77`. This identity check does not clear issue8. Mapping, full plan, and wire retain their independently reviewed bytes. The complete dependency digests are in before.json. The correction source manifests and all three patch digests pass. `git apply --reverse --check` accepts the full correction patch. Its blocks equal the owned and dependency patch blocks. No patch was applied.

The complete original Astra design and report, original worker API and report, original Sol HOLD and control scripts, and new Astra correction were read. The correction review includes its design, API, report, patch contents, commands, source identities, behavior comparison, revised-control patch, and supplied parent logs. [inputs.json](inputs.json) binds these public records. The original design, implementation reports, HOLD, scripts, and original result logs retain their committed audit digests. No broad audit search was used.

The correction explicitly replaces the original local-retention row and controls 41 and 42. Local retention after a frame-only error is unsupported. The old positive remains valid evidence of the old contract. It is not an acceptance requirement for this revision. ADR0031 states this restriction at [line 23](/Volumes/PhoenixWork/worktrees/m1-preflight-review/docs/adr/0031-checked-frame-reduction.md:23).

The source establishes the new rule directly. [Rejected at line 185](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:185) has `local: tuple[()]`. The failure handler at [line 911](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:911) always returns `Rejected(rejection, ()), ()`. The success path at line 925 calls `_local` only after preflight and complete reduction. Both public functions use this same decision. The incomplete post-failure scan and withheld set are deleted. No second frame algorithm, normalized stream, or repair path appears.

The success path at [line 882](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:882) exports only Entry, CallAttempt, and Continuation fields. It copies each field without conversion. It retains the site, sequence, trace digest, wire identity, and scope digest. ReturnAttempt values are excluded. The permanent tests and fresh controls check exact values and provenance, including high-bit values and repeated activations.

| Review area | Source and control evidence |
| --- | --- |
| F1 transit omissions and duplicates | The unchanged canonical transit script passes all four cases. Duplicate E, missing terminal J/T, and an early shared mismatch followed by duplicate E return no local values. The ordered positive still admits one opaque leaf. |
| F2 later structure after an early error | The unchanged canonical user script passes all three cases. The fresh route matrices pair omissions, duplicates, order failures, and open frames with an early E/A mismatch. Both APIs export no local values. The existing private controls also cover near-call mismatches before missing returns and open frames. |
| First rejection | `_Failure` reporting is unchanged. All 28 original control result codes match the correction behavior comparison. The early shared-error event and related references remain unchanged in the permanent canonical tests. Preflight still checks wire and capture consistency before frame reduction. |
| Shared roles | `bundle`, `visit`, and `resume` enforce confirmation, C, E, and current A/J/R order at [line 528](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:528). Fresh controls cover E/A, E/R, E/J, C/A, C/R, C/J, C/E/A, C/E/R, and C/E/J. They test missing roles, duplicate roles, order changes, and unequal captured fields. C/E/R and related private combinations do not prove static reachability. |
| Calls and registers | Near-call RSP is pre-call RSP minus eight. The other five captured fields must stay equal across the call. Caller entry RSP is not imposed on later calls. All six fields have negative controls. Fresh positives include pre-call RSP 8 and the maximum unsigned 64-bit value. |
| Returns and root closure | C3 uses its own frame entry RSP and top continuation. C checks call identity, pre-call RSP, and internal return RAX. Root closure checks its independent target, exact R/T references, and checked RSP plus eight at [line 638](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:638). Root RAX does not establish process exit status. |
| Recursion and repeated continuations | Each call gets a new node. The top call determines C. Existing and original independent controls admit distinct recursive snapshots and reject swapped call references. No older-stack search occurs. |
| Opaque leaves and exact transit | Direct external calls invent no entry sample. Transit advances through exact entries and terminal J/T at [line 748](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:748). Fresh canonical routes have 1, 2, and 32 entries. Every single-record omission and duplicate, every adjacent hop reversal, and omitted terminal pairs reject. Neutral instruction execution remains a collector obligation. |
| Lazy resolution and unsupported flow | In-image lazy resolution rejects. Unknown callbacks, wrong continuations, cross-owner tails, and nonlocal returns reject. ProcessExit and nonempty contract tables reject. A static import request remains provider-unknown. |
| Counters and bounds | Preflight checks limits, counters, byte counts, identity, and mapped Transfer indexes at [line 228](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/frames.py:228). Node count includes the root and closed nodes. Existing tests cover exact limits, limit excess, Boolean counters, recursion depth, and closed-node totals. Fresh private target-table, sequence, outcome, and root-classification faults reject with empty output. |
| Bounded work | Static indexes precede the event pass. Each reducer step consumes events or advances one route position. Stack operations and six-field comparisons have fixed cost. Local export makes one further pass after success. Work is linear in event count after bounded static setup. There is no scan of older frames. This is source analysis, not a performance measurement. |

The exact command arrays, environment paths, exits, and complete output logs are in [commands.json](commands.json) and [independent-commands.json](independent-commands.json).

| Host command or control | Result |
| --- | --- |
| Focused frame, scope, mapping, plan, and wire pytest suites | 363 passed. Exit 0. |
| Ruff check and format check over 11 source and test files | Passed. Both exits 0. |
| Strict mypy over the same files | Passed. Exit 0. |
| `git diff --check` | Passed. Exit 0. |
| Original `canonical_controls.py`, unchanged | 4 controls passed. Exit 0. |
| Original `canonical_user_controls.py`, unchanged | 3 controls passed. Exit 0. |
| Original `controls.py`, unchanged | 20 of 21 controls pass. Exit 1. The sole expected mismatch is `isolated-frame-error-keeps-local-bits`. |
| Separate `controls-revised-contract.py` | 21 controls passed. Exit 0. Its diff exactly matches revised-control.patch. |
| Fresh [independent_controls.py](independent_controls.py) | 354 controls pass. Seven admit, 269 reach frame rejection, and 78 reject in the existing wire parser or mapper. Exit 0. |
| Fresh [shared_controls.py](shared_controls.py) | 159 controls pass. Twenty-seven admit and 132 reject. Exit 0. |

These counts describe synthetic software checks. They are not Phoenix evaluation results, actual measurements, or live capture evidence. The fresh script label `boundary-rejected` means rejection by the existing wire parser or mapper. It does not mean that the future receipt boundary exists. For every checked record that reached frame rejection, both public APIs returned empty local output.

The original broader script's expected mismatch is preserved in [original-broader.log](original-broader.log). It still reports `return_rsp`, but now returns zero facts. The revised script changes only that control's name and expected empty output. The original wrappers were not run because they write into the old audit directory. Their child scripts ran directly and unchanged. The supplied parent logs were read. This review independently repeats the focused checks, not the full repository commit hook.

Two errors in new review scripts are preserved. [independent-first-failure.log](independent-first-failure.log) records an unmatched parenthesis. [shared-first-failure.log](shared-first-failure.log) records an incorrect test expectation for RDI at an E/R site. ReturnAttempt contains only RSP and RAX. The corrected controls permit unrelated fields to change when no matching field was captured. Neither failure required a production source change.

To repeat the checks, use the following commands from the reviewed checkout. The runner records the original broader script's expected exit 1.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-preflight-review
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/Volumes/PhoenixWork/tmp/m2-observation-frames-corrected-sol
.venv/bin/python -B /Volumes/PhoenixWork/tmp/m2-observation-frames-corrected-sol/run_checks.py
.venv/bin/python -B /Volumes/PhoenixWork/audit/m2-observation-frames-corrected-sol/independent_controls.py
.venv/bin/python -B /Volumes/PhoenixWork/audit/m2-observation-frames-corrected-sol/shared_controls.py
```

The private `_CheckedCapture` at [capture.py line 61](/Volumes/PhoenixWork/worktrees/m1-preflight-review/phoenix/observe/capture.py:61) remains a precondition, not an authentication method. Synthetic construction does not establish capture honesty. The future byte boundary must parse exact saved receipt and runtime-manifest bytes, reconstruct canonical scope, call the mapper, and bind all identities, lengths, and digests. It must independently classify both root addresses and bind the actual termination to the complete accepted outcome. The saved root target must come from an independent entry-time read. It must not be reconstructed from the later return.

The native collector and live public gate remain open. Required evidence includes root-read calibration, complete instruction guards, next-position checks, exact neutral route execution, post-root monitoring, six-register capture, shared-role capture, recursion, and actual collector mutation controls. The unchanged public fixture and rejected development cases must remain in accounting. Full stdout, stderr, termination, paths, file bytes, and modes need comparison. Required repetitions and native x86-64 and AArch64 CI checks remain open. A coherently omitted activation with a rewritten receipt cannot be detected by this pure reducer alone.

Recovery and localization must wait for their integration gate. Provider identity, automatic application binary interface type inference, general callbacks, tails, nonlocal returns, lazy resolver transit, nonreturn contracts, signal handlers, threads, R8/R9, vector registers, stack arguments, aggregate values, and memory snapshots remain unsupported. Local retention after every rejection is also unsupported. Eager binding needs its own declared invocation and accepted oracle outcome. The default lazy rejection must remain visible. Missing collector or runner modules are open work, not an additional defect in this private reducer.

I used the installed [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.135/skills/poteto-mode/SKILL.md). No replacement was needed. The Boundary Discipline principle kept authentication requirements at the future byte boundary. The Prove It Works principle led to direct source identity checks and independent controls. Both leaf skills were read. The user restrictions replace skill steps for nested agents, edits, history, and shipping. No nested agent, target execution, Docker, Ghidra, provider, private author material, sealed source, held-out input, actual measurement, or session history was used. New files are confined to the two permitted directories. No commit or push occurred.

The requested GPT-6.1 Sol model and Standard service tier are launch settings. This review does not independently attest them. SPEC.md section 9 remains open. It still requires M4, held-out T0 through T3 results against every baseline, costs and failure taxonomy, publication, and replay of every headline result. This PASS applies only to the exact revised pure-frame contract reviewed here.
