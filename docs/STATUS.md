# Phoenix status

The full SPEC section 9 goal is incomplete. M0 and M1 are accepted. The user
requested a one-hour pause at 16:15:25 London time on 13 November 2026.
Implementation is stopped for the handoff. The shared checkpoint records final
pause confirmation. Keep PAUSED after the deadline until explicit user resume.
Use Standard service and preserve corpus sealing. The old timer is historical.

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

Core readback remains uncommitted in its isolated branch at e721885. Root reads
all source and tests and repeats 14,451 affected controls. The full hook fails
one old property fixture; 18,351 tests pass and 26 are skipped. Identity 9 collides
with an existing fixture identity. Port the verified test correction and repeat
the gate. Seven staged files have exact local and public patch backups. Both
fresh full Sol and independent Astra Core reviews remain open.

Comparator source 7ee3a1d passes its full hook, push, fresh Sol review and Astra
harness review. Its main integration remains pending. Issue 0001 stays open.
Issue 0003 tracks five broader validator limits. Old reports and historical
controls remain exact. Future comparator integration changes worker identity.

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

## Next actions after explicit resume

1. Read the shared checkpoint and handoff. Verify files, processes, VM and timer.
2. Port the exact fixture fix to Core, repeat its full hook, push and obtain both
   required reviews. Preserve every pending file and staged ADR first.
3. Integrate the three exact comparator files with full checks and fresh review.
   Then design the separate validator. Refresh current worker labels before use.
4. Resolve T3 labels and private validation through a separate Author. Add T2/T3
   admission without reducing held-out sets. Continue byte source and adapter work.
5. Complete M2, M3, M4, every baseline, publication and every headline replay.
