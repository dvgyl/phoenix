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

Native CI at `efcad05` passed and matched the current Mac M0 public
outcomes on both native architectures.
[CI run 42859828267](https://github.com/dvgyl/phoenix/actions/runs/42859828267).
The corrected candidate still needs its own checks and exact evaluation.

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

1. Verify the CMake feedback correction and its independent Sol review.
2. Check the corrected public pipeline and native CI.
3. Measure a new M1 candidate, replay it exactly, and obtain Astra review.
4. Complete observer controls and independent M2 evaluator review.
5. Integrate verified M2 work after M1, then continue through M4 and section 9.
