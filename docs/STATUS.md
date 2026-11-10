# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. The guarded original `m1-t0-6897e47` measured Phoenix
17/20 fully successful and Ghidra-raw 8/20. All 40 report rows match their
bound checkpoints and model summaries. Exact replay runs on the same main
revision and images. There is no M1 tag.

This branch isolates the capture consistency correction. Independent Sol
confirmed the original mismatch correction. It held a symbolic link loop
that produced a traceback on interrupted resume. The parent reproduced that
case and the same error during freeze. All three targeted rejection checks
passed in the first correction. A second Sol review reproduced a concurrent
replacement between the path checks. Strict physical path resolution now
covers the freeze path as well as resume. Four targeted checks passed.
The parent gate passed 520 tests with 25 opt-in skips and 90.55% evaluator
line coverage. Fresh independent Sol and Astra reviews passed this correction.
The branch stays separate while main completes exact M1 replay.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

These are the original and replay `-O0` results from `m1-t0-baae648`. Two Phoenix
variants failed `embedded_text`. One failed behavior. Twelve raw variants
had compiler failures. All 80 Phoenix builds compiled with zero warnings.
Both methods had 792 eligible cases, zero emulator disagreements, and
zero evaluation errors. Coverage reached 790 of 1,079 recovered block
entries. Source branch adequacy is a separate measure.

Earlier replay `m1-t0-replay-efcad05` has `reproduced=false`. It retains 17/20
Phoenix successes and 8/20 raw successes. One original Phoenix behavior
failure became `pipeline-failed`, with no source or measurement record.
The other 39 stable records match. The replay measured only 754 Phoenix
variant-case pairs. The full original model log stayed unchanged.
The replay created no model log. Both frozen reports remain intact.

Commit `05d362f` corrects two
inherited evaluation findings from the M2 Astra review. Synthetic M1 tests
reproduced source replacement through a changed checkpoint and omitted charges
for ledger keys outside the task roster. ADR 0021 defines the separate capture
binding and complete ledger reconciliation. Astra closed R3 and R4. Sol found
malformed capture-binding JSON. The correction rejects duplicate fields and
requires an integer schema. Replay configuration comparison now preserves
JSON types. Fresh Sol review passed that candidate. Astra held a missing
completed-resume configuration check. The correction now checks the completed
report before capture reuse or archive access. The parent gate passed 455
tests with 25 opt-in skips and 90.40% evaluator line coverage. Fresh Sol and
Astra reviews passed the final correction. It is integrated on main.
Combined M2 integration, new candidate measurements and milestone acceptance
remain open.

Independent Sol diagnosis reproduced the cause. CMake elapsed times
entered compiler-failure feedback and changed the next repair prompt.
Exact model-ledger lookup correctly rejected that unrecorded request.
The correction removes only the two known CMake timing suffixes from
model feedback before truncation. Raw diagnostics and exact ledger checks
retain their values. The old replay remains failed evidence.
[Tracked defect](https://github.com/dvgyl/phoenix/issues/1).

Earlier results also remain in the record. `m1-t0-ce6a34d` scored zero
fully successful variants for both methods and reproduced on replay.
`m1-t0-5695148` scored Phoenix 17/20 and raw 0/20 and reproduced on replay.
Its raw score includes the support-header defect corrected at `ff4e427`.
The later `efcad05` review closed that header finding.

At `baae648`, public pipeline checks passed for both methods in all four
build configurations. Native CI passed. Both native M0 reports matched
the Mac report `m0-93e7c011124d4017b5908b8284535b1f`.
[CI run 42883642379](https://github.com/dvgyl/phoenix/actions/runs/42883642379).
Original `m1-t0-baae648` and replay `m1-t0-replay-baae648` have equal stable
fields, including failures and accounting. The original model log stayed
unchanged. Replay created no model log. The original has 69 calls and $1.4249648 API-equivalent
cost, with zero unknown-cost reservations. No M1 tag is permitted while
evaluation corrections and their new measurement gates remain open.

T1 is sealed with 15 programs and 90 variants. Its archive commitments
are pushed on `agent/t1-commitments`. Integration waits for M1 acceptance.
A fresh private Astra author has resumed incomplete T2 preparation.
The source and held-out inputs stay private. T3 qualification is pending.

Verified static lift evidence awaits integration after M1. The separate
public observer calibration passed its fixed positive and mutant controls.
Wrong-API and missing-register controls passed earlier Linux checks.
The reusable command passed source and host review. Its fresh Linux run
is active. The M2 evaluator passed separate Sol and Astra reviews. Its
integration with the shared guards is in a separate uncommitted branch.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.
Every major work block requires a fresh independent GPT-6.1 Sol review.
Milestone and integrity reviews also require Astra. CLI workers use
Standard service with Fast mode and nested agents disabled.

## Isolated C-F2 correction

C-F2 remains under review in `agent/evaluation-capture-consistency`, based on
`6897e47`. Synthetic M1 coordinator tests reproduced three contradictions
between returned submissions and checkpoint bytes during later capture.
The candidate compares both evidence sources before the freeze. One bounded
reader validates checkpoint metadata and hashes the same bytes. Submission
resume uses that reader too. The public report schema remains 1.

The final focused suite passed 217 tests. The final `scripts/check` passed
Ruff, format, and strict mypy. Its test run had 516 passes, 25 opt-in skips,
and one failure. The outer guard blocked the unchanged nested protection
test. Evaluator line coverage was 90.52%. Nonregular checkpoint rejection
also closes the file descriptor. All failed logs remain available.

The parent must run the complete gate outside the outer guard. Fresh Sol and
Astra review remain required. C-F1 belongs to the separate M2 branch. Main
and its active original and replay remain unchanged and were not inspected.
No real-run certification, M1 acceptance, sealed M2 approval, or tag is claimed.
Evidence is in `/Volumes/PhoenixWork/audit/evaluation-capture-consistency/`.

## Next actions

1. Finish the reusable observer controls and check their saved evidence.
2. Check public and native runs for the current shared correction.
3. Measure that M1 candidate, replay it exactly, and obtain milestone review.
4. Complete observer controls and independent M2 evaluator review.
5. Integrate verified M2 work after M1, then continue through M4 and section 9.
