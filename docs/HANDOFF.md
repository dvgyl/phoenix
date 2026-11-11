# Phoenix continuation handoff

## Paused at the owner's request

The goal is paused. All Phoenix workers and queues are stopped. The Linux
VM is stopped. Read the pause update at the end of this file before any
earlier active-work snapshot. Resume only after a new user instruction.

Prepared on 2026-11-11 at the owner's request. The goal remains completion
through `SPEC.md` section 9. M0 and M1 are accepted. M2 through M4,
publication, and the final headline replays remain open. This handoff does
not pause the goal or approve a later milestone.

Read the final review update below first. It supersedes the earlier active
review snapshots in this file.

## Start here

1. Source `/Volumes/Extreme Pro/Phoenix/env.sh` in every shell.
2. Work in `/Volumes/PhoenixWork/phoenix`.
3. Read `AGENTS.md` and `SPEC.md` in full after every context compaction.
4. Read the installed `pstack:poteto-mode` skill. The current path is
   `/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.135/skills/poteto-mode/SKILL.md`.
   Version 0.9.133 was replaced during this run. Locate a later installed
   version if this path changes. Preserve earlier review identities.
5. Read `docs/STATUS.md`, the latest `docs/LOG.md` entries, and the last
   20 commits. Read this handoff before the older handoff in Git history.
6. Fetch origin. Check actual branch tips, clean state, review reports,
   process state, and free space before resuming work.

The owner requires ASD-STE100 Issue 9 and clear human understanding.
Do not ask questions. Use Standard service for all roles and runtime calls.
Obtain a fresh independent GPT-6.1 Sol review after each major work block.
Use Astra for the algorithms, repeated-failure diagnosis, corpus authorship,
milestone review, and adversarial evaluator and integrity review.

The old instruction to hold main at `efcad05` was satisfied. That replay
and final Astra review finished with HOLD. The repaired M1 was measured,
replayed, independently reviewed, and accepted at `6897e47`. Do not restore
main to `efcad05` or move the accepted milestone tags.

## Storage and execution

`PHOENIX_ROOT=/Volumes/PhoenixWork`. The case-sensitive APFS sparsebundle
is under `/Volumes/Extreme Pro/Phoenix`. Store tools, caches, temporary
files, downloads, runs, and VM disks under `PHOENIX_ROOT`.

The internal baseline is 14,432,616 KiB. Investigate internal free space
below 12,479,491 KiB. The latest check had about 16 GiB free internally,
23 GiB on the 60 GiB workspace, and 87 GiB on the physical external drive.
Recheck these values. Keep the Mac awake with `caffeinate -dimsu`.

The Colima VM has four CPUs and 2 GiB of memory. The private T2 Author
owns the VM. Do not run Docker commands, build images, change tags, or
prune storage until that Author releases the VM. Execute all original and
rebuilt target programs in Linux containers. Host static inspection,
Ghidra, and syntax-only C checks are permitted established workflows.

## Sealing

The corpus is agent-sealed on an honor system. State this in every report.
Only the dedicated Corpus Author reads private sources and held-out data.
The main agent may read permitted release metadata, approved aggregate
status, approved author handoffs, and frozen category reports.

Do not read `sealed/src`, source archives, held-out files, private Author
logs, stderr, events, or session histories. Do not inspect those files to
prepare a public backup. Do not commit secrets, private corpus material,
held-out inputs, large binaries, caches, or runtime images to this public
repository. Publication follows the M4 freeze.

## Accepted M1

The immutable tags are as follows.

| Tag | Commit |
| --- | --- |
| `m0` | `4ef231a1bbdc8d572e06dd5a44efff620dda0e97` |
| `m1` | `6897e4753d8acedfae57af63e6426faf116bed2e` |

Original `m1-t0-6897e47` and replay `m1-t0-replay-6897e47` agree in every
stable field. Independent Sol and Astra reviews passed the exact evidence.
The review directories are `audit/m1/milestone-6897e47-sol` and
`audit/m1/milestone-6897e47-astra` under `PHOENIX_ROOT`.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

Phoenix compiled all 80 builds with eight warnings. Raw compiled 48 of 80
builds. Raw has 12 failed variants. Phoenix has two `embedded_text`
failures and one behavior failure. Each method has 792 eligible original
cases, zero emulator disagreements, and zero evaluation errors. Coverage
is 790 of 1,079 recovered block entries. This is not source branch coverage.

Phoenix used 86 calls and $1.7865956 API-equivalent cost. It used 1,268,096
input tokens, 669,056 cached input tokens, and 52,161 output tokens.
Unknown-cost reservations are zero. Median original reconstruction time
was 46.79 seconds. Replay time is not a speedup measurement.

The complete model log SHA-256 is
`ceed478c6f304e4cb388bc6b8599b475ea5e8b701f9d76e1d1b3c7024a2771db`.
The original binding is
`855accca103dc3dcefca204d2f1ea2085b14322d7e39f1f11c7731182e802a37`.
The replay binding is
`23ca606676d0b5a3882a5064ed71a215166cc588db08741962f0361574886c1e`.
Replay created no model log. Retain all earlier failed runs and HOLDs.
Later synthetic capture defects do not change the consistent saved M1
results. Later source changes do not inherit those scores.

## Main and native checks

The accepted implementation tip before this documentation handoff is
`3939fbc0d928d7701b289d559835bb466497a69c`. It is pushed to main.
The handoff branch merges that tip and adds continuation records and
archival public draft patches. It adds no pending observation code to main.

Main contains these reviewed M2 units.

- The combined evaluator at `3880478` uses the exact reviewed `05979af`.
  It binds 130 original variants and 260 method tasks. It preserves exact
  replay, capture identity, original-ledger accounting, and terminal rejection.
- U1 lift and import evidence is integrated at `d834e47`.
- Static switch evidence is integrated at `74d79b8`.
- The portable replay test correction is integrated at `53ee7de`.
- Schema 2 wire reading is integrated at `072e428`.
- Ordinary source observations, schema 3 generation, bounded C binding,
  protected emission, and protected writing are integrated at `1ca8589`.
- Physical transfer admission is integrated at `f0c61f2`.
- The opt-in checked-switch caller is integrated at `481f0e1`.
- Exact runtime and outcome mapping is integrated at `3c11d94`.
- The CI job limit is 60 minutes at `7cb644d`. Package pins stayed fixed.
- The reviewed public switch caller driver is integrated at `3939fbc`.

Native CI run 42959931595 passed both architectures and their comparison
at exact `3939fbc`. The archive hashes and report identities were verified.
Evidence is in `audit/m2-ci-3939fbc`. The native run IDs are
`m0-d54e6878254c40e1ae564f737f41c78a` and
`m0-a065ab2a0a7a486383b1092d858b2d39`.
[Native run](https://github.com/dvgyl/phoenix/actions/runs/42959931595).

The historical Mac case counts and outcome hashes also agree. The
same-revision Mac check is still open because the private Author owns the
VM. Do not claim a current three-mode comparison. The older timeout run
42954976284 remains a failed run. Its replacement 42959082671 passed.

The current worker source SHA-256 is
`d4caef6d06b82e83a58b9220b8d59c2c1e9b7a5d5526b18ec7217b15adfcc22e`.
Refresh the local images after the VM is released and before a new M2 run.
Preserve the exact M1 images first. The accepted M1 worker source is
`03c48c20b2d4f897ad0e17d2f99e3e7863f142e947b29c4616c4574704a52189`.
Its amd64 image is
`sha256:57348abbf3979a9a7790e12ed03a9be0a44ab8b01df57ac445d91cfe1a4e5389`.
Its arm64 image is
`sha256:821a915c0fdc5dec25a483eee3334149c1ddd8cb38b8568d9249c63fefe196fb`.
The old `m1-baae648` tags also remain. Do not overwrite archived identities.

## Checkpoints that are not on main

All worktree paths in this table are under `PHOENIX_ROOT/worktrees`.
Read actual remote tips and final review files before editing a checkpoint.

| Worktree | Branch | Pushed checkpoint | State |
| --- | --- | --- | --- |
| `m1-integrity-text-design` | `agent/m2-observation-scope` | `09e984b` | Fresh independent Sol review active. |
| `m1-preflight-review` | `agent/m2-observation-frames` | `b85feba` | Pure frame contract passed Sol. Scope dependency needs replacement. |
| `m1-development-evidence-fix` | `agent/m2-capture-admission` | `9672a0f` | Parser-only review passed. Full component review remains open. |
| `m1-submission-recovery` | `agent/m2-frame-calibration` | `cd59f7f` | Fresh Sol review active. Linux calibration is open. |
| `m2-prior-art-survey` | `agent/m2-trace-prototype` | `c76cc59` | Archived public v1 observer experiment. Preserve it. |
| `m1-preflight-review-2` | `agent/thread-handoff` | Read actual tip. | This handoff and draft backups. |

The earlier public switch driver checkpoint `63515a7` remains on
`agent/m2-public-switch-gate`. Its worktree was reused only after review
finished and the exact code was integrated on main.

### Static scope correction

The first independent HOLD found float aliases in proof evidence, XBEGIN
with absent raw translation, and an incoming reported root caller.
Correction `b42a7a2` passed the original 179 controls. A second fresh Sol
review found four XABORT cases. Issue 8 remains open.

Required Astra root-cause work is in `audit/m2-scope-control-root-astra`.
The resulting `09e984b` requires positive ordinary-instruction evidence.
Empty raw translation is accepted only for nine exact NOP forms or
ENDBR64 at the owner entry. Nonempty raw translation needs a known core
operation shape. Conflicting evidence rejects. Physical transfer checks
remain separate.

This contract still depends on complete faithful raw translation and
checked instruction starts. It does not independently prove arbitrary
instruction semantics. Three earlier empty-translation positives are now
unsupported. Their bytes are `4889c0`, `31c0`, and `c6c000`. Preserve their
old failing controls as declared capability changes. Do not report those
unchanged broad suites as fully passing.

Supported old controls passed 177 cases with two deselected. Supported
fresh controls passed 517 with one deselected. The expanded existing suite
passed 898. All 16 public plans stayed byte-identical. Scope certificates
changed only the source-policy digest. No new public rejection was added.
The parent repeated the checks. The full commit hook and push passed.

Fresh Sol review is `audit/m2-observation-scope-positive-sol`, launched at
05:27:40 UTC on exact `09e984b8608743d87ce9b323a9f6a4a2fad9785b`.
Its original exec session is 36837. Do not edit that tree during review.
Require its actual PASS before promoting the scope block. Retain the prior
HOLDs in `m2-observation-scope-final-sol` and
`m2-observation-scope-corrected-sol`.

### Pure frame reduction

Original `69e3768` received HOLD for inconsistent local-value retention
after rejection. Required Astra correction removed that capability.
At `b85feba`, every rejection returns an empty local-value tuple.
Successful output retains the original six-field values and provenance.

Fresh Sol `audit/m2-observation-frames-corrected-sol` passed this pure
contract. It passed 363 existing tests, 354 fresh controls, and 159 shared
role controls. The original broad suite retains one expected mismatch
for the withdrawn post-rejection retention capability. Its revised suite
passes. Production admission remains open. Issue 9 remains open until
verified integration and dependency checks finish.

Port the final reviewed scope files into this tree after scope review
finishes. Run combined checks. Do not change the reviewed frame algorithm
as part of the dependency update. No collector or inference is approved.

### Raw capture boundary

`9672a0f414e6fe128f8a1763c66694f551f2e2f5` adds `admission.py`,
`runtime.py`, tests, and exact checked dependencies. It passed 69 boundary
tests and 432 combined tests, strict types, and the full commit hook.
It checks raw identities, complete outcomes, invocation identity,
canonical plan and scope, bounds, runtime manifests, and frame reduction.
The runtime identity includes ten installed admission source files.

These are source and data checks. They do not authenticate a collector or
prove that a supplied process ran. An expected runtime digest must come
from a future trusted pinned runner. The collector, deployment binding,
and all live gates remain open.

The requested full independent review in
`audit/m2-capture-admission-final-sol` ended with exit 1. The provider
blocked the request for possible cybersecurity risk. It ran no checks and
returned no code verdict. Preserve that evidence. Do not disable safety
settings, change providers, or rephrase the same blocked full task to
avoid screening.

A separate, genuinely narrower local data-format review passed at the same
revision. `audit/m2-capture-data-formats-sol/report.md` covers only
`runtime.py`, `parse_receipt`, and `_outcome`. It passed 69 existing tests
and 128 independent tests. This partial PASS does not close the missing
full-component review. Keep that review gate open. Continue independent
work that does not depend on the gate.

After the final scope passes, port its exact files into this tree and run
the combined checks. The current tree uses the held `b42a7a2` scope.
The corrected frame source already matches `b85feba`.

### Public calibration fixtures

`cd59f7f6ff4fdbbdae65fcdded33b06d1dadf45c` adds public fixtures under
`corpus_public/mechanisms/frame-calibration` and ADR 0034. The fixed roster
has 33 cases. It includes recursive calls with high-bit values, return
patterns, two calls that may reuse one stack slot, and `qsort` callbacks.

There are 29 expected supported cases and four expected callback
rejections. Sources and cases have committed hashes. Syntax-only C11
checks pass. The compiler output must establish actual machine patterns.
No Linux build or target execution has occurred.

This new fixture declares eager binding with `-Wl,-z,now` from creation.
It does not change the archived Clang lazy-binding negatives, the sealed
matrix, or the fixed invocation environment.

Fresh Sol is `audit/m2-frame-fixtures-final-sol`, started at 05:28:16 UTC.
The queued launcher PID was 48230 before dispatch. Read the actual final
report and exit files. Do not start a duplicate or edit its source tree.

## Public switch caller gate

The actual production caller driver is on main. It has 56 fixed cases,
with 53 development cases that omit selector 11. It uses a fixed mechanical
cleanup response with zero live model calls. It checks actual reconstruction,
exact replay, four distinct build configurations, complete positive
behavior, and a compiled negative control on the three unvisited cases.

Fresh Sol passed source checkpoint `63515a7`. The source check proves byte
retention only. An inactive definition can retain bytes. Both positive and
negative behavior controls remain required. No Linux gate has run.

After the private VM lease ends, use `scripts/check-m2-public` and its
README. The command requires `PHOENIX_VM_LEASE=public-u2` before external
commands. Do not set this while T2 owns the VM. Keep `--checked-switches`
off by default until its actual public runtime gates pass.

## Collector and lazy transit

Required Astra baseline design is in
`audit/m2-observation-frame-design-astra/{design,report}.md`.
The production collector is not implemented. A parent transport proposal
is in `audit/m2-collector-architecture/options.md`. It compares a bounded
native plan parser with one plugin per binary using a generated typed C
header. The latter needs a trusted build receipt. Obtain an Astra
architecture check before implementing this choice.

Bind original binary, full plan, static scope, policy, six registers,
native collector source, compiled plugin, QEMU, guest runtime, observer
image, and installed admission source. Keep generated original-byte
witnesses outside the reconstructed project. Keep the QEMU 9.2 observer
separate from the accepted QEMU 8.2.2 oracle. Preserve the v1 experiment.

Required Astra lazy design is in `audit/m2-lazy-transit-design-astra`.
It defines a separate classic RELA PLT profile and bounded certificate and
receipt. It does not approve live lazy transit. Do not force a loader
variable into the fixed invocation environment or change archived negatives.

Read-heavy Sol verified the saved guest loader in
`audit/m2-guest-loader-static-sol/report.md`. Loader SHA-256 is
`c20a2dc8917c755f02b94049356320fe1f62ac7d9f8994731f807d9df39302da`.
Its Build ID is `0d77dbd4379bf0b5af3e05be7fb6af1e4cea7c96`.
Matching official Ubuntu package and debug files establish static resolver
entries and exits. They do not establish the current runtime mapping.
The saved context belongs to an older accepted image.

The QEMU 9.2 public plugin API cannot supply all required guest mapping
identity and change evidence. No approved mapping adapter exists. A small
QEMU extension needs Astra design. Static candidate pin fields remain
explicitly absent where live evidence is missing. Do not invent a bias,
use zero as an unknown address, or treat a candidate pin as accepted.

## Corpus status

T1 is complete with 15 programs and 90 variants. Source sizes are only
304 to 316 C LOC. Disclose this narrow range. Minimum source branch
coverage is 184/197. Minimum mutation detection is 11/12. One of 180
non-equivalent mutants survived. The source and input commitments are in
`docs/corpus_commitments.md` and already on main.

| T1 archive | SHA-256 |
| --- | --- |
| Source | `6e1667e79f6f245d2e87c6558bea22d5d48f7de4847f9e6a35e2095a2c9a3385` |
| Inputs | `4f4394480b69a593ba1f2b68fb026db5ff69225ca4c6bf85cfc1602af73d8c8f` |

Private T2 Astra PID 9983 remains active. Its original exec session is
97319. Read only `audit/m3-corpus-author/status.json` for current progress.
At 05:30 UTC it reported validation of one program and six variants,
10 total programs, 60 required variants, 29,788 fixed inputs, 307 planned
mutants, and three passing coverage reports. These are progress counts,
not final adequacy or acceptance. A prior approved health check reported
bounded progress and no owner action. Never read private worker output.

T3 has five source-screened candidates and no runtime-qualified batch.
Only `audit/t3-corpus-author/{qualification-report,qualification-summary}.md`
is approved for the parent. Two publication dates need stronger proof or
replacement by the private Author. The recorded official runtime model
cutoff is 2026-04-30. T3 needs its own private Astra Linux window after T2.

## Public draft preservation

`docs/checkpoints/2026-11-11` preserves 29 old public draft files as eight
patches. The manifest records each original worktree, base, exact file
hash, mode, and patch hash. The parent applied each patch to a separate
index at its recorded base and checked every file byte and executable mode.
All checks passed. The original files remain in their old worktrees.

These patches are archival records. They are not new accepted code.
Current implementations are already in later main commits. Do not apply
these patches to main. Generated lifts, scratch logs, coverage databases,
large binaries, and private corpus material remain outside Git.

## Review loop and live process checks

Fresh Standard CLI review dispatch uses
`audit/continue-v1/dispatch-review.sh`. The call is
`bash dispatch-review.sh sol|astra CHECKOUT AUDIT_DIR`. Prepare a fresh
`brief.md` first. The script selects the explicit model, requests the
Standard tier, disables Fast mode and nested agents, and applies
`review-guard-v3.sb`. Guard private corpus data and Author session history.
A writer uses a separate worktree and an own-tree guard.

Every brief states the goal, exact input revision, allowed writes,
verification scope, and required summary. Freeze the source during review.
The parent reads the full report, inspects the diff, and repeats relevant
checks. A successful process exit alone is not a PASS. A partial review
cannot close a wider gate. Requested role and service are launch settings,
not independent routing attestation.

At most four models may run, including the root. At 05:30 UTC the active
models were root, private T2 Astra, scope Sol, and fixture Sol. Completed
parser and loader reviews no longer occupy slots. Read `start.utc`,
`end.utc`, `exit-code`, and the actual report before new dispatch.
New chats may not share exec session handles. Use verified PIDs and files.

The detailed local state is `audit/continue-v1/state.json`. Its
`current_continuation_latest` must match this handoff. Older keys are
historical. `todo.md` and `decisions.tsv` in the same directory preserve
the longer work record. No private source belongs in those records.

## Resume order

1. Finish the two active public Sol reviews. Preserve every HOLD. Obtain
   the handoff review and verify that the pushed branch contains this file.
2. Port the final reviewed scope into frame and raw-boundary checkpoints.
   Repeat combined checks. Keep the missing full capture review open.
3. Obtain the collector transport decision from Astra. Implement the
   approved producer and runner. Pass public lifecycle, stack-word,
   order, full-outcome, mapping, and negative controls after VM release.
4. Refresh current worker images while preserving M1 identities. Pass
   the public switch caller, observer, and same-revision Mac checks.
5. Implement the remaining indirect-call and libc-idiom recovery. Use
   Astra for trace fault localization, whole-program types, and struct
   unification. Check actual public behavior before sealed measurement.
6. Measure and exactly replay M2 using the fixed T0 and T1 matrix.
   Obtain independent Sol and Astra milestone and harness reviews.
7. Finish T2 and T3 privately. Complete M3 type share, modules, uncertainty,
   no-regression checks, and Astra readability review of five projects.
8. Run the frozen M4 matrix with every baseline and ablation. Publish
   costs, failures, and limitations. Verify commitments. Publish the
   required artifacts and reproduce every headline with evaluator replay.

Package confidence currently uses `tested` and `unverified`. Recovered
block coverage is not the source branch evidence needed for `verified`.
M4 and every item in SPEC section 9 remain required. Do not mark the goal
complete because a handoff, review, checkpoint, or intermediate gate passes.

## Final review update

The independent handoff review passed exact `972f43a752becd763ed8afefa70b79960d440437`.
It reconstructed all eight patches and all 29 original files independently.
All 164 implementation files outside `docs` match main `3939fbc` exactly.
Both historical log sequences remain. This final update changes only
public records. It adds no pending observation implementation to main.

The completed review states are as follows. The table supersedes the active
review snapshots above.

| Block | Exact checkpoint | Current review state |
| --- | --- | --- |
| Static scope | `09e984b8608743d87ce9b323a9f6a4a2fad9785b` | Fresh Sol PASS for the stricter static contract. |
| Pure frames | `b85febaa4735c9916a526598b8ba06d0db07919d` | Fresh Sol PASS for the revised pure contract. Dependency port remains open. |
| Capture parsers | `9672a0f414e6fe128f8a1763c66694f551f2e2f5` | Data-format PASS only. Full capture review remains open. |
| Public fixtures | `cf066d69162de8657563f087b491995ca5c0a63f` | Fresh Sol PASS after the README correction. All live gates remain open. |
| Handoff and archival patches | `972f43a752becd763ed8afefa70b79960d440437` | Fresh Sol PASS. This later update records the completed reviews. |

The scope review passed 713 new independent controls. It retains the
faithful-translation precondition and the three withdrawn old positives.
It does not approve independent machine semantics, runtime capture, or
recovery. Issue 8 remains open until verified integration.

The original fixture review placed `cd59f7f` on HOLD for a README stack
claim. Correction `cf066d6` changes only that README and progress records.
Fresh Sol closed F1. The C sources, 33-case roster, manifest, ADR, flags,
and source and case hashes remain unchanged. The live gate must verify
a caller stack frame in every required compiled build. No Linux fixture
execution has occurred.

Exact copies of the five named PASS reports are in
`docs/reviews/2026-11-11`. Their manifest binds the original report bytes.
The original reports, controls, and logs remain under `PHOENIX_ROOT/audit`.
The provider-blocked full capture review still has no code verdict.
Do not treat the narrower parser review as its replacement.

The handoff reviewer could not inspect the private Author status or use
`ps` under its guard. The parent checked the permitted status and PID.
The private T2 Author remains active and retains the VM lease. Do not
infer release from a finished public review. Check the actual current
private Author status through the approved parent path before any Docker
command. The public reviewers have ended. Their source worktrees are clean.

The next action is the exact reviewed scope dependency port into the
frame and capture checkpoints, followed by combined checks. Then continue
the ordered collector, public runtime, M2, M3, M4, publication, and replay
work above. The goal remains active. SPEC section 9 remains incomplete.

## User-requested pause on 2026-11-11

The owner requested a safe pause after the last active continuation.
The goal status is `paused`. All recorded public and private worker PIDs
and queue PIDs are absent. Colima shut down cleanly at 06:08:04 UTC.
No container work continues. The VM disk and private corpus files remain.
The private T2 status file is a stale progress snapshot after interruption.
It does not establish an active process or a completed corpus batch.

Main remains clean at `3939fbc`. The last complete public handoff was
`26be701`. The following two source worktrees retain pending changes.

| Worktree | Base | Pending state |
| --- | --- | --- |
| `m1-preflight-review` | `b85feba` | Five changed or new files. Full commit gate interrupted. No new source commit or push. |
| `m1-development-evidence-fix` | `9672a0f` | Five changed or new files. Full commit gate not completed. No new source commit or push. |

Both ports use exact scope source, tests, and ADR from `09e984b`.
The focused frame suite passed 1,093 tests. The focused capture suite passed
924 tests. These are unit-test results. The new dependency-port review
was queued but never started. It was cancelled for the pause.

The scope ADR is new and untracked in both source worktrees. The earlier
verifier inspected only tracked differences. It incorrectly described the
ADR as already present. The pause checkpoint includes that file and all
other pending files. The original staged and unstaged files remain in place.

`docs/checkpoints/2026-11-11-pause` contains two inert patches, their exact
file manifest, and the interrupted public collector task files. The parent
reconstructed all ten pending files at their recorded bases and checked
exact bytes and executable modes. The patches are backups, not accepted
production changes. The collector Astra task ended after interruption
with exit 1 and no approved design or verdict.

A pause marker exists at `audit/continue-v1/PAUSED`. The dispatch helper
rejects new workers while that marker exists. No source commit loop,
queued review, or private Author process must restart automatically.

After the owner explicitly resumes, read this checkpoint and inspect
actual process and Git state. Remove the pause marker only after that
instruction. Add the scope ADR when staging the two source ports. Repeat
the full quality gates, commit and push each verified port, and obtain a
fresh independent Sol dependency-port review. The wider capture review
remains open. Restart collector design as a fresh Astra task with the
saved inputs and interruption record. A separate private Corpus Author
must inspect its own saved checkpoint before corpus validation resumes.
The main agent must not read private sources, inputs, logs, or history.

Do not restart the Linux VM until a new owner-approved continuation needs
it. Preserve all old M1 image identities. M2 through M4, publication, and
the headline replays remain incomplete. No milestone tag changed.
