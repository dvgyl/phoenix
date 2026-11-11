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
metadata in a synthetic run. The reviewed evidence for the two real runs
is consistent. Main now binds returned submissions to the exact checkpoint
bytes and preserves a detected contradiction across retry. Sol and Astra
passed the shared correction. The combined M2 evaluator remains under
independent review. Earlier failed runs and review verdicts remain in the
log. No new sealed run has started.
[Capture issue](https://github.com/dvgyl/phoenix/issues/6).
[Replay issue](https://github.com/dvgyl/phoenix/issues/5).

T1 is sealed with 15 programs and 90 variants. Its source and input
commitments are on the isolated evaluation branch. T2 private validation
has started. T3 has five source-screened selections and no runtime-qualified
batch. All source and held-out inputs stay sealed.

The reviewed U1 lift evidence and opt-in recovery plan are on main.
Public static checks passed 16 configurations at `49202a7`. Sol and Astra
passed the exact source review. The public observer controls passed.
The reviewed conditional switch proof and optional graph publication
are on main. They retain the ordinary lift and keep generation unchanged.
The separate bounded C source parser passed on both public fixtures.
This branch binds ordinary token evidence and normalized graphs in
one optional lift generation. Both public generations and the 22
focused checks passed. Checked C emission and Linux behavior remain
separate gates.

The internal free-space baseline is 14,432,616 KiB. The workspace is the
external APFS mount at `/Volumes/PhoenixWork`. The VM has four CPUs and
2 GiB of memory. Use Standard service. Obtain a fresh independent Sol
review after each major block and Astra review where required.

## Next actions

1. Finish the combined M2 evaluator reviews before a new sealed run.
2. Finish U2 proof, generation, and public behavior checks.
3. Continue production observation, indirect calls, byte idioms, and repair
   fault localization. Keep the two oracle engines independent.
4. Finish private T2 validation. Validate T3 in a separate Linux window.
5. Complete M2 through M4, publish the required artifacts, and replay every
   headline result.

This branch binds exact ordinary source observations to schema 3. It
does not prove C tokens. The public saved generations still pass.
