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
passed the shared correction. The combined M2 evaluator passed fresh
Sol and Astra reviews at `05979af`. The reviewed evaluator and T1
commitments are on main. Earlier failures remain in the log. No new
sealed run has started. The first native CI run failed because a replay
property test used a Mac-only scratch path. The correction passed all
13 affected cases and fresh Sol review. Native CI at `53ee7de` passed
both architectures and its outcome comparison. Its public case counts
and full outcome digests match the historical Mac run. The same-revision
Mac check still needs refreshed images and the Linux VM. The later
`3c11d94` native arm64 job passed. Its amd64 job reached the 30-minute
limit during pinned integrity package downloads. The native job limit
is now 60 minutes. Its replacement run remains required.
[Capture issue](https://github.com/dvgyl/phoenix/issues/6).
[Replay issue](https://github.com/dvgyl/phoenix/issues/5).

T1 is sealed with 15 programs and 90 variants. Its source and input
commitments are in the repository. T2 private validation is active. T3 has five source-screened selections and no runtime-qualified
batch. All source and held-out inputs stay sealed.

The reviewed U1 lift evidence and opt-in recovery plan are on main.
Public static checks passed 16 configurations at `49202a7`. Sol and Astra
passed the exact source review. The public observer controls passed.
The reviewed conditional switch proof and optional graph publication
are on main. They retain the ordinary lift and keep generation unchanged.
The ordinary source observations, schema 3 publication, bounded C
binding, checked emitter, and protected writer passed fresh Sol review.
Both public fragments retain all cases and defaults. Host syntax checks
pass. The opt-in reconstruction caller also passed fresh Sol review.
It records the setting for exact resume and replay. The option remains
off by default. The public production-caller driver passed fresh Sol source
review and is on main. Its source check proves byte retention. Both behavior
controls remain mandatory. Public Linux behavior and unvisited-case checks
remain open.
The structural schema 2 wire reader passed fresh Sol review and 596
additional controls. The static observation plan and shared physical
transfer checks also passed fresh Sol review. The exact outcome and
runtime mapping gate passed fresh Sol review. Its mapped result does not
authorize recovery. Frame admission and live capture remain open.

The internal free-space baseline is 14,432,616 KiB. The workspace is the
external APFS mount at `/Volumes/PhoenixWork`. The VM has four CPUs and
2 GiB of memory. Use Standard service. Obtain a fresh independent Sol
review after each major block and Astra review where required.

This isolated branch adds fixed public recursion and callback controls.
Host syntax and manifest hashes pass. Linux execution and review remain open.

## Next actions

1. Refresh worker images and pass public evaluator gates before a new
   sealed M2 run. Wait for the private author to release the Linux VM.
2. Finish U2 proof, generation, and public behavior checks.
3. Continue production observation, indirect calls, byte idioms, and repair
   fault localization. Keep the two oracle engines independent.
4. Finish private T2 validation. Validate T3 in a separate Linux window.
5. Complete M2 through M4, publish the required artifacts, and replay every
   headline result.
