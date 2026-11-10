# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. Final Astra review held `efcad05` because exact replay
changed one stable failure record. Matching success counts did not satisfy
the replay requirement. There is no M1 tag.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

These are the original `-O0` results from `m1-t0-efcad05`. Two Phoenix
variants failed `embedded_text`. One failed behavior. Twelve raw variants
had compiler failures. All 80 Phoenix builds compiled with zero warnings.
Both methods had 792 eligible cases, zero emulator disagreements, and
zero evaluation errors. Coverage reached 790 of 1,079 recovered block
entries. Source branch adequacy is a separate measure.

Replay `m1-t0-replay-efcad05` has `reproduced=false`. It retains 17/20
Phoenix successes and 8/20 raw successes. One original Phoenix behavior
failure became `pipeline-failed`, with no source or measurement record.
The other 39 stable records match. The replay measured only 754 Phoenix
variant-case pairs. The full original model log stayed unchanged.
The replay created no model log. Both frozen reports remain intact.

The isolated `agent/evaluation-freeze-accounting` worktree corrects two
inherited evaluation findings from the M2 Astra review. Synthetic M1 tests
reproduced source replacement through a changed checkpoint and omitted charges
for ledger keys outside the task roster. ADR 0021 defines the separate capture
binding and complete ledger reconciliation. This work is uncommitted. It has
not changed main or measured a candidate. Astra closed R3 and R4. Sol found
malformed capture-binding JSON. The correction rejects duplicate fields and
requires an integer schema. Replay configuration comparison now preserves
JSON types. Fresh Sol review passed that candidate. Astra held a missing
completed-resume configuration check. The correction now checks the completed
report before capture reuse or archive access. The parent gate passed 455
tests with 25 opt-in skips and 90.40% evaluator line coverage. Fresh Sol and
Astra reviews passed the final correction. Combined M2 integration, new
candidate measurements and milestone acceptance remain open.

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
Original `m1-t0-baae648` reports the same 17/20 Phoenix and 8/20 raw
success counts and failure categories shown above. Its exact replay is
active. The original model log has 69 calls and $1.4249648 API-equivalent
cost, with zero unknown-cost reservations. No M1 tag is permitted while
evaluation corrections and their new measurement gates remain open.

T1 is sealed with 15 programs and 90 variants. Its archive commitments
are pushed on `agent/t1-commitments`. Integration waits for M1 acceptance.
A fresh private Astra author has resumed incomplete T2 preparation.
The source and held-out inputs stay private. T3 qualification is pending.

Verified static lift evidence awaits integration after M1. The separate
public observer calibration passed its fixed positive and mutant controls.
Wrong-API and missing-register runtime controls remain open. Its source
and runtime evidence need fresh review. The M2 evaluator is in its
separate worktree, with synthetic checks and review in progress.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.
Every major work block requires a fresh independent GPT-6.1 Sol review.
Milestone and integrity reviews also require Astra. CLI workers use
Standard service with Fast mode and nested agents disabled.

## Next actions

1. Finish the unchanged main replay and verify its complete stable evidence.
2. Integrate the reviewed shared correction and check public and native runs.
3. Measure that M1 candidate, replay it exactly, and obtain milestone review.
4. Complete observer controls and independent M2 evaluator review.
5. Integrate verified M2 work after M1, then continue through M4 and section 9.
