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
is now 60 minutes. The replacement native run at `20402bc` passed both
architectures and the outcome comparison. The downloaded artifact hashes,
worker source identity, and report bindings passed the parent check.
The same-revision Mac comparison remains open until the private VM is free.
[Capture issue](https://github.com/dvgyl/phoenix/issues/6).
[Replay issue](https://github.com/dvgyl/phoenix/issues/5).

T1 is sealed with 15 programs and 90 variants. Its source and input
commitments are in the repository. T2 private validation is incomplete. A separate Corpus Author resumes it. T3 has five source-screened selections and no runtime-qualified
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

## Current recovery work

The exact scope and pure-frame files from `e7c9450` passed fresh Sol review.
All 1,009 combined host tests passed. The parent repeated all 72 new
integration controls. Existing pipeline and generation code remain unchanged.
The reducer requires canonical private checked input. It does not authenticate
a supplied selection or receipt. Every rejection returns no local values.

The raw capture boundary remains isolated. Its full independent review is
open after provider screening. The parser-only PASS does not replace it.
Astra approved the corrected typed-header collector design for implementation.
The corrections cover trusted build issuance, per-trial calibration,
compiled-data retention, and exact launch and source identities.
Production capture and all live collector gates remain open.

T2 validation remains private and incomplete. Its separate Author retains
the Linux VM. T3 has five source-qualified selections. All five runtime
qualifications remain pending. No new evaluation result is claimed.

The independent review records are in `docs/reviews/2026-11-12`.
Their manifest binds exact report bytes. Historical HOLDs remain preserved.

Complete static collector data is pushed at `63dd985`. Its full quality gate
passed. Fresh independent Sol review remains open. The parent repeated all
1,130 affected tests. The typed header renderer is a separate work unit.
The new byte-graph reader passed 525 affected host tests. Its full quality
gate, commit, and independent review remain in progress. These pure units
do not authorize production capture or byte-idiom emission.

## Next actions

1. Implement and review complete collector data, typed headers, and build
   issuance under the corrected Astra design. Keep full capture review open.
2. After the private Author releases the VM, preserve M1 image identities,
   refresh current images, and pass the public switch and collector gates.
3. Complete indirect-call recovery, byte idioms, exact fault localization,
   whole-program types, modules, and bounded function cleanup.
4. Finish private T2 and T3 qualification. Complete and replay M2 and M3.
5. Freeze M4 with every baseline and ablation. Publish required artifacts
   and reproduce every headline result. Meet every SPEC section 9 condition.
