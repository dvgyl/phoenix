# Phoenix status

The full SPEC section 9 goal is incomplete. M0 and M1 are accepted. The user
resumed work for another hour at 20:46:45 London time on 13 November 2026.
Pause at 21:46:45. Begin draining at 21:31:45. The new one-time timer is active.
Use Standard service and preserve corpus sealing. Commit and push each verified
unit. Earlier pause records and timers remain historical.

## Accepted measured results

M0 is 4ef231a1bbdc8d572e06dd5a44efff620dda0e97.
M1 is 6897e4753d8acedfae57af63e6426faf116bed2e.
Original m1-t0-6897e47 and replay m1-t0-replay-6897e47 agree in stable fields.
Phoenix passes behavior for 19/20 variants, integrity for 18/20, and all success
conditions for 17/20. Raw passes 8/20 in each category. Phoenix retains two
embedded-text failures and one behavior failure. Raw retains 12 compiler-error
variants. Each method has 792 eligible variant-case pairs and zero emulator
or evaluation errors. Coverage is 790/1,079 recovered block entries, not source
branch coverage. Later code inherits no score.

## Verified engineering state

Exact candidate layout integration 2046688 and graph integration 7761d83 pass
full hooks, pushes and fresh full Sol integration reviews. The layout review
closes the earlier stale-docs finding. Graph F1, F2 and listing-caller defects
are closed for its pure reader. Source schema 2, capture, semantics and native
approvals remain open. Preserve the historical test-file hash failure.

Last test correction 8f1c394 passes the full hook and push. All 223 diagnostic
tests and direct identity controls zero through ten pass. Existing collisions
now require refusal instead of being skipped. Product readers stay exact.
Fresh Sol review of this correction is part of the final handoff audit.

Core readback has an exact seven-file backup. Port only the verified diagnostic
fixture correction from 8f1c394. The eight-file source gate is active. The earlier
failed full gate remains preserved. It had 18,351 passes, 26 skips and one strict
identity-collision refusal from an incorrect fixture. Both fresh full Sol and
independent Astra Core reviews remain required after the source gate and push.

Comparator source 7ee3a1d passes its full hook, push, fresh Sol review and Astra
harness review. Main now imports only its three exact files. Root repeats the
focused tests and real-report negative controls. The main full gate and fresh
Sol integration review remain required. Issue 0001 stays open until that review.
Issue 0003 tracks five broader validator limits. Old reports remain exact.
This import changes the current worker source identity. Existing images do not
inherit that identity. Preserve accepted M1 images and verify labels before use.

The latest verified native workflow is 43431817090 at exact 293477f. Both CPU
jobs and comparison pass. Complete Mac/native M0 and public switch evidence
passes fresh Sol and root repeats, with aggregate-only limits. Public fixtures
are not sealed reconstruction scores. No newer native result is assumed.

## Corpus and open gates

T1 has 15 programs and 90 variants. Its narrow source range is 304 to 316 lines.
T2 has ten programs and 60 variants. Its approved adequacy is 18,590/21,685 source
branches and 305/310 mutant kills. Five non-equivalent mutants survive. Separate
witnesses do not count as held-out kills. One confirmation uses a declared
emulator diagnostic rule. All 60 final rebuilds match. These are source counts.

T3 has five programs and 20 variants under Author assertions. Its safe public
record integration passes Sol review; first-publication review remains HOLD.
Issue 0002 tracks two labels. Branch counts are 2,340/3,211. The small mutation
sample has 36 kills, four survivors and two inconclusive results among 42 compiled
mutants. Keep 16 invalid mutants, 40 setup failures and two interruptions.
Archive hashes are commitments, not private-byte verification. No Phoenix score,
native x86 validation or numerical T3 adequacy pass is supplied. Only a dedicated
Corpus Author may read private material. Root reads approved aggregates.

Full capture review remains OPEN after provider screening. Do not retry,
rephrase, replace, change provider/settings or bypass it. Parser-only and public
PASSs close no capture, producer, semantic, emission or production gate.
Colima is stopped and the private lease is released. Check the live stop record.
Accepted M0/M1 tags and images remain exact. All storage stays on external APFS.
Internal baseline is 14,432,616 KiB. Investigate below 12,479,491 KiB.

## Next actions

1. Finish both full gates and push each green unit. Verify actual remote tips.
2. Obtain fresh full Sol and independent Astra Core reviews. Integrate only
   reviewed exact files after resolving findings. Preserve the staged ADR.
3. Obtain fresh Sol comparator integration review. Design the separate validator
   with Astra. Refresh current worker labels before use.
4. Resolve T3 labels and private validation through a separate Author. Add T2/T3
   admission without reducing held-out sets. Continue byte source and adapter work.
5. Complete M2, M3, M4, every baseline, publication and every headline replay.
