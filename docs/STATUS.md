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

Schema 2 graph source `23e05e9` is on HOLD for two functional defects.
The recognized-name set confuses six Java constant names with exported
mnemonics. Supplied function identities also need exact integer checks
before equality and lookup. Root reproduced 28 failures and 38 passes.
A separate Astra fix uses the isolated source worktree. Full checks and
fresh full Sol review are required before integration. Earlier comment
HOLDs and their test-only corrections remain preserved.

Candidate layout source `e721885` passed its full hook and is pushed.
Root repeated 1,744 layout, ELF, data and header controls. Fresh full Sol
implementation review remains required. Both candidate definitions are
test-only. No decoder or native layout approval is supplied. The staged U2
design keeps final identity inputs and metadata retention open.

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

A dedicated Standard Astra Corpus Author owns private T3 qualification and
its sole VM lease. Root reads only approved aggregate records. No other role
may use that VM before release. Accepted M1 image identities remain preserved.
Current worker and checker source labels were verified for the public runs.
Keep tools, caches, temporary files and VM disks on external APFS.
The internal free-space baseline is 14,432,616 KiB. Investigate values below
12,479,491 KiB. Read the live lease and checkpoint before further execution.

## Next actions

1. Correct both graph defects, run full checks, push and obtain fresh full
   Sol review. Integrate exact accepted bytes without replacing later main.
2. Finish layout implementation review and its exact integration. Then add
   complete private U2 readback with retained limits and independent tests.
3. Complete the separate source adapter, indirect calls, byte idioms and
   fault localization. Keep all authority and full capture gates explicit.
4. Finish private T3 through its separate Author. Complete and replay M2
   and M3, including types, modules and the Astra readability review.
5. Freeze M4 with every baseline and ablation. Publish failures, costs,
   limitations and required artifacts. Reproduce every headline result.

The report-comparator self-check gap is tracked in
`docs/issues/0001-public-report-self-check.md`. Current complete assertions
detect it. It does not invalidate the accepted bounded public records.


## Public report self-check correction, 13 November

An isolated source correction requires exact true for each program self_match.
Root retains the 24-failure parent check. All 28 final tests and 54 actual-report
negative controls pass. Both native-only and native/emulated positive comparisons
pass. Full source checks, Sol correctness review and Astra harness review remain
required. No old public report, historical control, score or image is changed.
