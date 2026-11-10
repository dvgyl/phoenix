# Phoenix status

This isolated branch integrates shared correction `05d362f` and matrix
`11da284`. Independent Sol review passed the combined base `0ee21d7`.
Independent Astra review held two findings. This branch corrects replay
ancestry accounting. The capture consistency correction and fresh combined
reviews remain open. The branch is not ready for sealed M2 use.

The replay ancestry correction passed ten rejection checks. The parent gate
passed 660 tests with 25 opt-in skips and 92.30% evaluator line coverage.
[Replay ancestry issue](https://github.com/dvgyl/phoenix/issues/5).
[Capture consistency issue](https://github.com/dvgyl/phoenix/issues/6).

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 and the v1 goal remain open. No M1 tag exists.
Main is pushed at `6897e4753d8acedfae57af63e6426faf116bed2e`.
Its public pipeline passed both methods in all four build configurations.
Native CI run 42905864046 passed. The native results matched the Mac M0 run.
Guarded M1 run `m1-t0-6897e47` froze all 40 captures. Its measurement and
exact replay remain open.

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

1. Port the reviewed capture consistency correction and repeat combined review.
2. Finish the guarded M1 original and exact replay on fixed main.
3. Obtain M1 milestone review before tagging or M2 source integration.
4. Complete production M2 recovery and its public evidence gates.
5. Continue M3, T3 qualification, M4, publication and section 9 replay.
