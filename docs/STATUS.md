# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. Exact `baae648` replay reproduced all stable fields.
Main is fixed at `6897e47` during a new guarded original and replay.
There is no M1 tag.

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

Native CI and the current Mac M0 passed at `6897e47`. All three reports
match in revision, source hash, seed, cases and outcomes.
[CI run 42905864046](https://github.com/dvgyl/phoenix/actions/runs/42905864046).
The guarded M1 original is active. Its exact replay remains required.

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

## Separate U1 candidate

`agent/m2-production-recovery` has an uncommitted U1 evidence adapter.
It is disabled by default. Main remains separate for M1. ADR0022 records
the mapping, static index, import checks, and static plan candidate.
Public static Ghidra checks passed for four PIE fixtures and both saved
switch fixtures. Changed data spans remain unavailable byte evidence.
The switch arrays still have 13 targets and 12 labels. No target ran.

The writer retained a nested-sandbox test failure under its outer guard.
The complete parent gate passed 549 tests with 26 opt-in skips and 90.06%
evaluator line coverage. Ruff, format, strict mypy and the unchanged
protection tests passed. These are software checks, not evaluation scores.
Parent evidence is under `$PHOENIX_ROOT/audit/m2-production-u1/`.
Fresh independent Sol and Astra reviews remain pending. Linux ET_EXEC,
PLT/GOT, and multiple-executable-segment gates remain pending. The public
builder is ready. Production observation and U2 are disabled.

## Next actions

1. Complete the guarded M1 original and exact replay on unchanged main.
2. Obtain milestone review before tagging or M2 integration.
3. Finish the combined evaluator and fresh observer evidence reviews.
4. Review U1 independently, then run its pending public Linux fixture gates.
5. Integrate verified M2 work after M1, then continue through M4 and section 9.
