# Phoenix status

This isolated branch integrates the shared capture guards and the M2
matrix. Fresh Sol review held three further findings at `1cf064b`.
This checkpoint corrects replay publication and cyclic replay log paths.
The durable capture rejection correction and fresh combined reviews remain
open. The branch is not ready for sealed M2 use.

The final report is staged before its last capture and ledger checks.
An earlier or current replay cannot publish a fresh model log after report
rendering. A cyclic log path gives a controlled error. Eight focused
requirements passed. The complete parent gate passed 730 tests, with 25
opt-in skips and 92.27% evaluator line coverage.
[Replay issue](https://github.com/dvgyl/phoenix/issues/5).
[Capture issue](https://github.com/dvgyl/phoenix/issues/6).

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 passed at exact measured commit `6897e47`. The `m1` tag points to it.
Guarded original `m1-t0-6897e47` and replay `m1-t0-replay-6897e47`
agree in every stable field. Phoenix is 17/20 fully successful and raw is
8/20. Both 40-task bindings and model summaries match the reports.
Independent Sol and Astra passed these measured results. Main records the
acceptance at `49bd659`. New sealed measurement remains closed until the
remaining evaluator fixes pass.

Original `m1-t0-baae648` and replay `m1-t0-replay-baae648` have equal stable
fields. Phoenix is 17/20 fully successful. It retains two `embedded_text`
failures and one behavior failure. Raw is 8/20 and retains 12 compiler failures.
Both methods have 792 eligible cases, zero emulator disagreements and zero
errors. Coverage is 790/1079 recovered block entries. The complete original
model log stayed unchanged. Replay created no model log. Model use was 69 calls
and $1.4249648 API-equivalent cost, with zero unknown-cost reservations.

The shared correction freezes every captured file and validates the complete
model ledger against the ordered task roster. It rejects malformed binding
JSON and inconsistent saved configuration. Its final parent gate passed 455
tests. Fresh Sol and Astra reviews passed before source integration on main.
A new measured candidate is still required. Historical runs are not backfilled.

The matrix has 130 original variants and 260 method tasks across T0 and T1.
The integration opens the complete capture roster before configuration or
submission writes. It checks evidence before each archive read and before
publication. It checks every replay ancestor's capture binding. Seven new
negative requirements fail against the previous matrix. All eight integration
checks pass, including a complete roster and accounting control.

T1 remains sealed with 15 programs and 90 variants. Its 304 to 316 C LOC range is
limited and must remain visible in the final report. Minimum source branch
coverage is 184/197. Minimum mutation detection is 11/12. Source and input
archive commitments precede reconstruction. This branch retains those hashes.

The reusable observer controls passed a fresh Linux run and independent Sol
review. The observer remains separate from production. Independent Sol review
held opt-in stripped-binary evidence candidate `ac45adf`. It needs corrections
and expanded public checks. Private Astra authors are preparing T2 and T3.
Their sources and detailed logs remain sealed.

The internal-drive baseline is 14,432,616 KiB free. The workspace is the external
APFS mount at `/Volumes/PhoenixWork`. The dedicated VM has four CPUs and 2 GiB
of memory. Standard service and fresh Sol review apply to every major block.

## Next actions

1. Port the durable capture rejection correction and verify the full gate.
2. Obtain fresh independent Sol and Astra reviews of the combined source.
3. Keep new sealed measurement closed until the evaluator passes.
4. Complete production M2 recovery and its public evidence gates.
5. Continue M3, T3 qualification, M4, publication and section 9 replay.
