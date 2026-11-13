# Phoenix status

The complete SPEC section 9 goal is active. M0 and M1 are accepted.
M2 through M4, publication and every headline replay remain incomplete.
The user resumed work on 13 November. The old timer is retired. No new
pause deadline exists. Use Standard service and preserve corpus sealing.

## Accepted measured results

M0 is `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 is `6897e4753d8acedfae57af63e6426faf116bed2e`.
Original `m1-t0-6897e47` and replay `m1-t0-replay-6897e47` agree in all
stable fields. Phoenix passed behavior for 19/20 variants, integrity for
18/20, and all success conditions for 17/20. Ghidra-raw passed 8/20 in
all three categories. Phoenix has two embedded-text failures and one
behavior failure. Raw has 12 variants with compiler errors. Both methods
have 792 eligible variant-case pairs and no emulator disagreement or
evaluation error. Coverage is 790/1,079 recovered block entries. This is
not source branch coverage. Later code does not inherit these scores.

## Current engineering state

Main includes the reviewed scope, frames, collector data, schema 1 byte
graph/source readers, typed header, project-profile reader, byte diagnostic
and passive ELF reader. The exact byte and ELF integrations passed full
hooks and fresh Sol integration reviews. The fixture correction at
`293477f` also passed its full hook and fresh independent red/green review.
It fixes eight setup failures in both earlier native CPU jobs. All 223
diagnostic controls pass with ambient PHOENIX_ROOT absent.

The latest verified passing native workflow is `43431817090` at exact
`293477f`. Both CPU jobs and their comparison passed. Root checked both
complete ZIP digests and reports. Mac run
`m0-ea89531416274da5b4df008f7a219d06` agrees with both native runs on revision,
worker source, seed, cases and outcomes. Fresh Sol evidence review passed.
Root repeated all nine pure check groups and four independent controls.
The public reports retain aggregate-only execution limits.

Public switch run `public-switch-293477f-20261113` passed both GCC and Clang
inputs. Its eight positive builds match 56/56 cases each. All eight negative
builds fail the three unvisited selector-11 cases by stdout. Exact source
replay snapshots match. Positive GCC builds retain two warnings each.
Positive Clang builds have zero warnings. Negative builds retain three each.
These public fixture checks are not sealed reconstruction scores.

Schema 2 graph source `23e05e9` remains on HOLD pending a checked repair.
Astra corrected six exported mnemonics and exact integer function identities.
Root also corrected the same equality defect for listing-edge callers.
Ten new refusals failed before that correction. All twelve caller controls
now pass. Root repeated 1,311 focused controls and 65 independent controls.
The historical test-file hash assertion remains an expected failure after
new regressions. Its original expectation is unchanged. Full source checks,
push and fresh full Sol review remain required before integration.

Candidate layout source `e721885` passed its full hook, push and fresh full
Sol implementation review. Root repeated 1,744 layout, ELF, data and header
controls. The reviewer added 2,020 independent mutation refusals. Main imports
only its exact module, tests and ADR0043. This integration still requires
its full checks and fresh Sol integration review. Both candidate definitions
remain test-only. No decoder or native layout approval is supplied.

A separate Astra writer implements complete private U2 readback in the old
layout worktree. Do not edit or move that checkout. The returned source needs
root checks, a fresh full Sol review and an independent Astra critical review.
Final identity inputs and immutable metadata retention remain separate gates.

Full capture review remains OPEN after provider screening. Parser-only PASS,
representation checks and public switch checks do not replace it. Complete
producer admission, native facts, compiled retention, trusted issuance,
operational table use, calibration, capture and production remain open.

## Corpus and execution

T1 is sealed with 15 programs and 90 variants. Its source range is only
304 to 316 C lines. T2 is sealed with ten programs and 60 variants. Approved
T2 adequacy is 18,590/21,685 source branches and 305/310 mutant kills.
Five non-equivalent mutants survive. Separate witnesses do not count as
held-out kills. One confirmation uses a declared emulator diagnostic rule.
All 60 final rebuilds match. These are source adequacy counts, not Phoenix
scores. Accepted T0 and T1 commitments remain exact.

A dedicated Standard Astra Corpus Author completed T3 qualification and sealing
for five programs and 20 variants. Root read only its three approved aggregate
records. Fresh Sol public-record review is active. The Author reports 11,264
variant-case pairs and 45,056 original executions with no oracle disagreement.
Source coverage is 2,340/3,211 branch counters. The small mutation sample has
36 confirmed kills, four survivors and two inconclusive results among 42
compiled mutants. Keep invalid mutations, setup failures and interruptions.
T3 has no numerical adequacy gate in SPEC. No Phoenix score was produced.
Publication evidence retains first-public-snapshot and training-date limits.
The Author released its VM lease and stopped Colima. Root confirmed that Colima
is stopped. Accepted M1 image identities remain preserved.
Current worker and checker source labels were verified for the public runs.
Keep tools, caches, temporary files and VM disks on external APFS.
The internal free-space baseline is 14,432,616 KiB. Investigate values below
12,479,491 KiB. Read the live lease and checkpoint before further execution.

## Next actions

1. Finish graph source checks, push and obtain fresh full
   Sol review. Integrate exact accepted bytes without replacing later main.
2. Check and review the exact layout integration. Review the complete private
   U2 readback after its writer ends. Keep native and public-success gates open.
3. Complete the separate source adapter, indirect calls, byte idioms and
   fault localization. Keep all authority and full capture gates explicit.
4. Review and commit approved T3 records and commitments. Complete and replay M2
   and M3, including types, modules and the Astra readability review.
5. Freeze M4 with every baseline and ablation. Publish failures, costs,
   limitations and required artifacts. Reproduce every headline result.

The report-comparator self-check gap is tracked in
`docs/issues/0001-public-report-self-check.md`. Current complete assertions
detect it. It does not invalidate the accepted bounded public records.
