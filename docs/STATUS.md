# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 passed at `6897e47` and has its exact tag. Main records acceptance
at `49bd659`. M2 is in progress. No new sealed evaluation is ready.

This branch adds a bounded normalized switch graph reader and checked
relative table recognizer. It has 13 passing synthetic checks. Both saved
public GCC and Clang switch graphs give 12 cases and one default. The
checked recognizer rejects seven changed evidence controls for each
compiler. The complete parent gate passed 594 tests with 26 opt-in skips
and 90.06% evaluator coverage. The exporter and generated C pipeline are
not connected. Fresh independent review remains open.

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
Guarded M1 original `m1-t0-6897e47` retained Phoenix 17/20 and
Ghidra-raw 8/20 fully successful. All 40 report rows match their bound
checkpoints and model summaries. Its exact replay is active.

T1 is sealed with 15 programs and 90 variants. Its archive commitments
are pushed on `agent/t1-commitments`. Integration waits for M1 acceptance.
A fresh private Astra author has resumed incomplete T2 preparation.
The source and held-out inputs stay private. T3 qualification is pending.

Verified static lift evidence awaits integration after M1. The separate
public observer calibration passed its fixed positive and mutant controls.
Wrong-API and missing-register runtime controls passed a fresh Linux run
and independent Sol review. The observer remains separate from production. The M2 evaluator is in its
separate worktree, with synthetic checks and review in progress.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.
Every major work block requires a fresh independent GPT-6.1 Sol review.
Milestone and integrity reviews also require Astra. CLI workers use
Standard service with Fast mode and nested agents disabled.

## Separate U1 candidate

Initial opt-in U1 candidate `ac45adf` remains on its own branch. Independent
Sol confirmed six saved public static exports and held seven findings.
The hardening branch corrects them. It rejects conflicting import or target
evidence, protects the input paths, and preserves the previous complete
generation after a failed refresh.

The parent also reproduced two selector faults. A symbolic link reached a
valid selector outside the publication path. A named pipe blocked the
reader. The reader now requires a regular file and uses a bounded
nonblocking read without following symbolic links. Both probes pass.

The parent gate passed 578 tests with 26 opt-in skips and 90.06% evaluator
line coverage. Two fresh Ghidra analyses of public GCC and Clang switch
fixtures preserved the original binary, lift, and address proof hashes.
They published a complete generation through the new path. No target ran.

Fresh Sol confirmed the seven earlier fixes and both selector checks.
It held two more findings. The static plan now rejects a direct call
target that disagrees with the raw operation. Failed mapping or lift
validation retains the Ghidra diagnostic without changing the prior
generation. The corrected parent gate passed 581 tests with 26 opt-in
skips and 90.06% evaluator line coverage. All six saved exports retained
1,172 witnesses and 80 named import bindings.

The code remains opt-in. Fresh independent Sol and Astra reviews and the
expanded E1 Linux fixture checks remain open.
[Tracked review findings](https://github.com/dvgyl/phoenix/issues/7).

## Next actions

1. Complete exact guarded M1 replay on unchanged main.
2. Obtain milestone review before tagging or M2 integration.
3. Finish the combined evaluator and fresh observer evidence reviews.
4. Review U1 independently, then run its pending public Linux fixture gates.
5. Integrate verified M2 work after M1, then continue through M4 and section 9.
