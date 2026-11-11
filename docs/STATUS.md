# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 passed at `6897e4753d8acedfae57af63e6426faf116bed2e`.
M2 work is in progress. No M2 result or later milestone is accepted.

| M1 method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

Original `m1-t0-6897e47` and exact replay `m1-t0-replay-6897e47`
agree in every stable field. Each method has 792 eligible variant-case
pairs, zero emulator disagreements, and zero evaluation errors. Coverage
reaches 790 of 1,079 recovered block entries. This is separate from source
branch adequacy. Phoenix has two `embedded_text` failures and one behavior
failure. Raw has 12 failed variants with compiler errors. Phoenix compiled
all 80 builds with eight warnings. Raw compiled 48 of 80 builds.

Both 40-task bindings match the report fields and complete model summaries.
The original log and both saved bindings stayed unchanged. Replay created no
model log. Phoenix used 86 model calls with $1.7865956 API-equivalent cost
and zero unknown-cost reservations. Median original reconstruction time was
46.79 seconds per variant. Independent Sol and Astra reviews passed these
exact measured results. The public pipeline passed all four builds for both
methods. [Native CI](https://github.com/dvgyl/phoenix/actions/runs/42905864046)
and both native-to-Mac comparisons passed.

The measured revision can accept contradictory pre-freeze checkpoint
metadata in a synthetic run. The reviewed evidence for these two real runs
is consistent. Before future sealed measurement, complete the shared
capture correction and retain detected rejection across retry. The M2
coordinator also needs final replay accounting checks. Earlier failed runs
and review verdicts remain in the log.
[Capture issue](https://github.com/dvgyl/phoenix/issues/6).
[Replay issue](https://github.com/dvgyl/phoenix/issues/5).

T1 is sealed with 15 programs and 90 variants. Its source and input
commitments are on the isolated evaluation branch. T2 private validation
has started. T3 has five source-screened selections and no runtime-qualified
batch. All source and held-out inputs stay sealed.

The public U1 evidence gate passed all 16 configurations at `49202a7`.
Fresh Sol and Astra source reviews passed. The separate observer controls
also passed.

The opt-in switch artifact export passed on the public GCC and Clang
binaries. It kept ordinary lift bytes unchanged and bound the normalized
graphs to their lift generation. Sol held the separate switch recognizer.
It needs stronger checks against the original instruction sequence.
No reconstructed target ran and no M2 result is claimed.

The internal free-space baseline is 14,432,616 KiB. The workspace is the
external APFS mount at `/Volumes/PhoenixWork`. The VM has four CPUs and
2 GiB of memory. Use Standard service. Obtain a fresh independent Sol
review after each major block and Astra review where required.

## Next actions

1. Close durable capture rejection and final replay accounting. Verify both
   evaluator scopes before a new sealed run.
2. Finish U1 source review and U2 public build and behavior checks.
3. Continue production observation, indirect calls, byte idioms, and repair
   fault localization. Keep the two oracle engines independent.
4. Finish private T2 validation. Validate T3 in a separate Linux window.
5. Complete M2 through M4, publish the required artifacts, and replay every
   headline result.
