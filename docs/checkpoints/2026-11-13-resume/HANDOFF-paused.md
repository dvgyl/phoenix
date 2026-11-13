# Phoenix continuation handoff

## Timed pause

The user requested a three-hour work period, then a complete pause and a
handoff. The deadline is **2026-11-13 01:11:47 UTC**, also London time.
Dispatch is locked. All workers and queues are stopped. Colima is
stopped. Read the observed final pause record below. The goal-pause
update follows the handoff as the final action at the requested deadline.
Resume requires a new user instruction.

The goal remains the complete `SPEC.md` section 9. M0 and M1 are accepted.
M2, M3, M4, publication, and every headline replay remain incomplete.
Never mark the goal complete because a checkpoint or review passes.

The previous pause record is preserved at commit `e1f0fff`. Its active
worker and pending dependency-port statements are historical. The user
explicitly resumed that work on 12 November. The old `efcad05` freeze ended.
Do not restore it or move an accepted milestone tag.

## Resume procedure

1. Source `/Volumes/Extreme Pro/Phoenix/env.sh` in every shell. Work in
   `/Volumes/PhoenixWork/phoenix`.
2. Read `AGENTS.md` and `SPEC.md` in full, including after compaction.
3. Read the installed `pstack:poteto-mode` skill. The current version is
   0.9.137 under `/Users/devg/.codex/plugins/cache/pstack-claude/pstack`.
4. Fetch origin. Read this file from `origin/agent/thread-handoff`.
5. Read the shared checkpoint with the installed `resume.mjs`:

   ```sh
   node /Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/scripts/resume.mjs read --project /Volumes/PhoenixWork/phoenix
   ```

6. Read `docs/STATUS.md`, the latest `docs/LOG.md` entries, and 20 commits.
   Inspect actual branches, pending files, processes, free space, and VM
   state. Local snapshots can be stale.
7. Remove `audit/continue-v1/PAUSED` and `DRAINING` only after a new explicit
   user instruction to resume and the required verification. Replace the
   old deadline configuration before dispatch. Do not revive an old queue.

Use ASD-STE100 Issue 9 and write for clear human understanding. Do not ask
questions. Use Standard service everywhere. Obtain a fresh independent
GPT-6.1 Sol review after every major block. Use Astra before foundational
or difficult interface decisions, for competing long-term designs, for
repeated compatibility failures, and for milestone critical review.

## Repository and accepted results

Main is clean and pushed at `2c9934a6b96004536c5db98e844dce180c958c25`
at the verified pause checkpoint. No new source was integrated after it.
The handoff branch merges that implementation and retains old public
archival patches. The historical handoff log remains an exact prefix.
The complete main log sequence is preserved in order.

| Tag | Immutable peeled commit |
| --- | --- |
| `m0` | `4ef231a1bbdc8d572e06dd5a44efff620dda0e97` |
| `m1` | `6897e4753d8acedfae57af63e6426faf116bed2e` |

Original `m1-t0-6897e47` and replay `m1-t0-replay-6897e47` agree in all
stable fields. Independent Sol and Astra passed their exact evidence.
Phoenix passed behavior for 19/20 variants, integrity for 18/20, and all
success conditions for 17/20. Ghidra-raw passed 8/20 in each category.
Phoenix has two `embedded_text` failures and one behavior failure.
Both methods have 792 eligible variant-case pairs, no emulator disagreement,
and no evaluation error. Coverage is 790/1,079 recovered block entries.
This is not source branch coverage. Later code does not inherit M1 scores.
Full original costs, warnings, bindings and limitations remain in STATUS
and the accepted reports. Preserve all earlier failures and HOLDs.

The resumed dependency ports are complete and pushed:
`94caeb4fcd8f7734b11da59c455f4e4d04dc9caf` for pure frames and
`a2af90cdfb339765b85abb46982a13f0088d5677` for raw capture dependencies.
Both include the exact scope ADR. Full gates passed. Fresh Sol passed the
dependency ports. This does not close the full capture review.

Main now includes the reviewed pure scope/frame unit, complete collector
data, byte graph, corrected source-token reader, typed collector header,
and pure project-profile reader. Exact independent reports and hashes are
in `docs/reviews/2026-11-12`. Original HOLDs remain there where applicable.
No pure reader authenticates a process, original source fact, or behavior.

## Current public work units

All worktree paths below are under `/Volumes/PhoenixWork/worktrees`.
Verify the final pause record and actual Git state before editing.

| Unit | Worktree | Branch or checkpoint | Current draft state |
| --- | --- | --- | --- |
| P1 project metadata | `m1-public-profile` | `agent/m3-project-profile-reader`, `6d00328` | Sol and Astra PASS. Exact files integrated on main. Adapter design has ended. Verify ownership before reuse. |
| Byte diagnostic | `m1-follow-up-review-e07ec17` | `agent/m2-byte-export-producer` | Clean and pushed at `7562edb`. F3 passed the full hook. Fresh Sol PASS ended 00:52:32 UTC. Parent repeated all 114 fresh controls. Integration is deferred. |
| Passive ELF U1 | `m1-ci-reliable` | `agent/m2-passive-collector-elf`, `11cb51b` | Clean, fully checked and pushed. Fresh Sol PASS ended 00:42:40 UTC. Parent repeated all 1,344 fresh controls. Integration is deferred. |
| Raw capture | `m1-development-evidence-fix` | `a2af90c` | Dependency port only. Full capture review remains open. |
| Public calibration | `m1-submission-recovery` | `cf066d6` | Source review PASS. Actual compiled caller frames and live cases remain open. |
| Handoff | `m1-preflight-review-2` | `agent/thread-handoff` | Public pause records. No new implementation beyond main. |

P1 passed fresh Sol and mandatory Astra at exact `6d00328`. The parent
repeated all 1,508 Sol controls and 1,185 Astra controls. The code accepts
immutable metadata and exact supplied CMake bytes only. P2 must carry
caller-reduced limits and installed evaluator policy separately. Later
adapters must discover complete source origins and actual shared users.
Native GCC and Clang evidence for all four build contexts remains required.
P2 through P9 and production v2 remain open.

The P1 worker improperly hashed public dispatcher event files. Preserve its
report, failed logs, earlier source, patch and manifest. Both independent
reviews accept code only and make no process-assurance claim. A separate
profile-design output-directory error is preserved in its audit record.
The v5 guard blocks future dispatcher-data reads. Existing guards were not
changed during active tasks.

The byte diagnostic runs one ordinary decompiler result. Existing graph
and source readers and publication versions 1 through 3 remain unchanged.
The actual public E1 job has nine `entry_unrepresentable` gaps, ten
`empty_printer_token` gaps, and zero complete printer observations.
Thirteen block-owned operations retain Java dead flags and conflict gaps.
Do not discard those flags or silently remove empty printer items.

Fresh Sol held `d1a1779` for five routine filesystem errors that escaped
the finite diagnostic contract. Five new permanent controls failed before
correction and passed after it. All 110 unchanged independent controls and
786 affected host tests passed. Two optional live tests were skipped.
A repeated public static job retained exact ordinary lift, mapping and
inspection bytes. Context identities now bind the changed exporter source.
The F1 correction passed the full gate at `b252452`. Fresh Sol found
F2: Python 3.12 reports real symlink loops as RuntimeError with direct
OSError(ELOOP) context. Required Astra selected a dedicated narrow resolver.
Root applied it at six controlled sites. All 37 focused controls, 174
unchanged independent controls and 823 affected tests passed. Two optional
live tests skipped. Actual public static bytes remained exact. The full
gate passed and the branch was pushed at `01dc406`.

Fresh Sol then found F3: the ordinary reader's nested EvidenceError
escaped the diagnostic format contract. Root repeated 24 coherent invalid
cases and four valid controls. Required Astra inspected reader contracts.
The premise that all expected refusals had three handled classes was false.
Use a local EvidenceError handler around parse_lift only. Keep the direct
cause. Do not broaden outer handlers or change the stable reader contract.
All 40 new permanent controls, 322 unchanged independent controls and 863
affected tests passed. Two optional live tests skipped. Ruff and strict
mypy passed. The first fixture setup and three test typing errors remain
preserved. The full hook passed and the branch was pushed at `7562edb`.
Fresh Sol passed the complete diagnostic unit at 00:52:32 UTC. Root
repeated all 114 fresh independent controls; all passed.
All earlier HOLDs remain preserved. Complete producer admission is open.
Earlier actual static jobs bind their exact earlier source revisions.

Astra adapter design uses immutable Git copies from `d1a1779` in
`audit/m2-byte-adapter-design-astra-20261112/inputs`. It must resolve actual
entry association, Java dead-bank bookkeeping versus native liveness,
and zero-length printer trivia through a new versioned adapter. The Astra task ended at 23:26:23 UTC. The parent read all four final
documents and verified 13 frozen inputs and 36 primary source hashes.
The selected plan uses separate graph and source schema 2 readers first.
Keep complete Java banks and post-printer inventories with explicit gaps.
ADR0041 is taken by U1. Use ADR0042 for the later adapter work. No compiler, Ghidra job, VM, target or production
caller is authorized by that design task.

Compiled-data architecture is in `audit/m2-compiled-data-design-astra-20261112`.
The parent read all four final documents. The selected design uses fixed
installed Linux layout expectations, a data-only compiler witness, and a
bounded passive ELF reader. U1 is implemented and code-reviewed. U2 readback follows
verified U1 integration. U3 native witness work follows U2 review. U4 actual Linux
compiler evidence and U5 production integration remain on HOLD. Never
load a plugin for inspection or treat Darwin layout checks as Linux proof.
U1 must state its page-rounded alias and RELRO assumptions explicitly.

U1 first passed the full gate at `75b42cf`. Fresh Sol held it for F1:
unsectioned runtime relocation writes lacked complete page-mapping checks.
A separate executable-section observation required an explicit contract.
Root reproduced eight F1 rejection failures. Required Astra selected the
existing full eight-byte page mapper and conservative rejection of writes
that intersect nonempty allocated executable sections. Build sorted ranges
once. Preserve endpoint adjacency and ignore empty or nonallocated ranges.
All 2,472 affected and 2,169 earlier independent controls passed. One
historical source-hash assertion was excluded and retained unchanged.
The correction passed the full gate and was pushed at `11cb51b`.
Fresh independent Sol passed the complete corrected U1 unit at 00:42:40 UTC.
It ran 1,344 additional controls. Root repeated all 1,344 controls; all passed.
Candidate page granules are
unapproved test-profile values. No actual Linux compiler profile,
compiled retention, plugin loading or production authority is approved.


## Capture and other open gates

The full capture review remains **OPEN after provider screening**. The
blocked task has no code verdict. The narrower parser-only PASS does not
close that gate. Do not disable screening, change providers or settings,
or rephrase the same full task to avoid screening. Keep `admission.py`
and `runtime.py` isolated. Continue work independent of that gate.

The corrected collector architecture requires trusted build issuance,
per-trial calibration and applicability, compiled-data retention, and exact
launch and complete source/import identity. Preserve the old nine-file
and ten-file hash algorithms. Data, header and design PASS results do not
supply those live facts. The QEMU mapping adapter also remains open.

The public switch driver is on main. Its 56 fixed cases include 53 dev
cases that omit selector 11. It requires actual reconstruction, exact
replay, four builds, complete positive behavior, and compiled negative
controls for the three unvisited cases. No live model call is needed.
Keep checked switches off by default until these runtime gates pass.
The command requires `PHOENIX_VM_LEASE=public-u2`; never set it while the
private Author retains the VM.

Whole-program types, modules, uncertainty annotations, indirect-call
recovery, byte idioms, trace fault localization and bounded cleanup remain
incomplete. The readability rubric is an unadopted candidate under
`audit/m3-readability-rubric-root-20261112`. It needs Astra review before
use. The required five-project readability assessment remains open.

## Native checks, images and storage

Native workflow `43322747514` passed at exact main `2c9934a` on both CPUs.
The parent verified both archive digests, complete reports, revision,
worker identity, seed, all public outcomes, three self trials, sandbox
probes, builds and five-of-five mutation detection for each toy program.
The native comparison passed. Evidence is in `audit/m2-ci-2c9934a`.
The first safe archive check rejected the expected two-part report path;
no file was extracted. A corrected bounded check retained both JSON files.

The complete current worker source digest is
`f2ae5cdece588e795c60c3c45f630027cc3f4d954738b6801a842b1cc2f391a1`.
Recalculate it after source integration. The same-revision Mac comparison
remains open. Preserve accepted M1 image identities before rebuilding:

- amd64: `sha256:57348abbf3979a9a7790e12ed03a9be0a44ab8b01df57ac445d91cfe1a4e5389`.
- arm64: `sha256:821a915c0fdc5dec25a483eee3334149c1ddd8cb38b8568d9249c63fefe196fb`.
- Accepted M1 worker source: `03c48c20b2d4f897ad0e17d2f99e3e7863f142e947b29c4616c4574704a52189`.

Do not overwrite the old `m1-baae648` tags or archived images. Current
images must bind current source before Linux validation. No image or VM
action is permitted during the private lease, except safe shutdown after
the Author has stopped for this explicit user pause.

Store everything under `/Volumes/PhoenixWork`, including tools, caches,
temporary files and VM disks. Its case-sensitive APFS image is stored on
`/Volumes/Extreme Pro/Phoenix`. The internal baseline is 14,432,616 KiB.
Investigate free space below 12,479,491 KiB. Preserve the verified external
cache moves and symlinks. Do not change unrelated applications or system
swap. The VM has four CPUs and 2 GiB of memory. Execute every original or
rebuilt target only inside Linux containers. Host static Ghidra, Java
compilation and C syntax-only checks do not execute targets.

## Private corpus and process control

Only a separate dedicated Corpus Author may read private sources,
held-out inputs, source archives, private runs, Author logs or history.
The parent reads only `audit/m3-corpus-author/status.json` and the eventual
approved handoff under `resume-storage-restored-20261112`. Never inspect
private files to prepare a backup. The corpus is agent-sealed on the honor
system. State this in reports.

T1 is sealed with 15 programs and 90 variants. Its source sizes are only
304 to 316 C LOC. Disclose that narrow range. Commitments are on main.
T2 is sealed. The approved final Author handoff is dated 00:48:17 UTC.
It reports ten programs, 60 stripped variants, 43,276 fixed inputs,
20/20 generator replays and 60/60 exact final rebuilds. Every variant
passed the fixed set under both emulators. Every program passed at least
85 percent source branch coverage and 90 percent mutant detection.
Aggregate coverage is 18,590/21,685 branches. Mutant detection is 305/310.
Five non-equivalent mutants survived. Separate witnesses confirmed them
and did not count as held-out kills. One confirmation used a declared
emulator-diagnostic rule. Original comparisons used no normalization.
Minimum program coverage is 2,742/3,225. Minimum mutant detection is 29/32.
Source sizes range from 1,502 to 4,036 C LOC. These are corpus adequacy
counts, not Phoenix reconstruction scores. No source or input was read
by the principal agent.

The approved T2 source and held-out archive hashes are appended to
`docs/corpus_commitments.md`. Accepted T0 and T1 entries remain exact.
The approved release-manifest hash is
`cd60cf5a1bdc7106c02bfad3c0ab7820fd6a3d7a8aaab757e234fe958b63e78f`.
Keep both private archives sealed until the specified publication stage.
The Author reports no owner blocker, released the VM and stopped Colima.
Root observed the Author process absent and Lima Stopped at 00:50:43 UTC.

The evaluator needs capacity for 9,216 inputs and 30,700,244 encoded input
bytes per program. The Author used caps of 16,384 inputs and 32 MiB.
Per-case sandbox limits are unchanged. Verify evaluator-owned admission
before any sealed run. Do not silently reduce the input set or per-case
limits. T3 did not start. It has five source-screened selections; all five
Linux runtime qualifications remain pending. The official model knowledge
cutoff is 2026-04-30. It is not an independently verified training completion
date. Prefer the open public Linux gates before a new private T3 lease.

The final pause record gives actual process and VM observations.
At most four model processes include root. Native explicit-model
collaboration advertises Priority only. Guarded CLI roles request Standard
with Fast and nested models disabled. That is a launch setting, not an
independent routing attestation.

Use `audit/continue-v1/dispatch-review-v6.sh` for future public reviews.
It refuses DRAINING and PAUSED. Its immutable v5 task guard protects private
material, confines audit writes and denies dispatcher event/stderr/summary
data reads. Writers need a separate own-tree guard and Git-write denial.
Do not relax a guard to fix a test collection error. Correct test roots,
temporary directories and cache locations instead.

The deadline watcher only writes markers. It does not stop processes.
The principal agent must stop and verify all workers and queues, stop the
private Author safely, and then stop Colima. Preserve private VM storage.
The one-time automation id is `pause-phoenix-and-prepare-handoff`.
Disable it after handling the pause. Set the existing goal to `paused`
only after the handoff, checkpoint and actual shutdown checks are complete.

## Resume order after explicit authorization

1. Verify all final pause facts and exact pending-file backups. Remove
   markers only after explicit authorization. Start fresh tasks, not stale
   queues. A separate private Author must inspect its own checkpoint.
2. Integrate the exact reviewed byte diagnostic and U1 ELF files. Both
   corrected branches passed full hooks and fresh Sol review. Preserve
   every HOLD and every later parallel main addition. Keep each ADR
   with its unit. Recheck complete dependencies and run the full gate.
   Do not replace main with either older branch tree. Publish current
   source identities and pass native CI before later runtime validation.
3. Follow approved adapter and compiled-data designs in separately reviewed
   units. Keep full capture and production authority gates open.
4. After actual private lease release, preserve M1 images, build current
   images, and pass the public switch, collector and same-revision Mac gates.
5. Complete M2 and exact replay. Obtain independent Sol and Astra milestone
   and harness reviews. Preserve sealed T2 and finish T3 through a separate Author.
6. Complete M3 types, modules, no-regression checks and readability review.
   Freeze M4 with every baseline and ablation. Publish failures, costs,
   limitations and required benchmark artifacts. Verify commitments and
   reproduce every headline through evaluator replay.

## Preserved public records

`docs/checkpoints/2026-11-13-pause` retains exact final adapter and
compiled-data design documents. It also retains the historical six-test
F2 regression checkpoint. The parent reconstructed that test file at its
recorded base and checked exact bytes and mode without changing the
original index. These are records, not accepted implementation changes.

## Final pause record

Fresh independent Sol passed exact draft `8579da3` and its archival
records. The parent repeated all 39 archived source files, 18 review
copies and five interrupted-task records under the unchanged guard.
All passed. This draft review does not certify the later shutdown.

Observed at 00:57:47 UTC on 13 November:

- All model workers, dispatch queues and private Author processes are
  absent. All public review wrappers ended naturally. The drain check
  had zero remaining targets. No worker needed a stop signal.
- Colima reports that it is not running. Lima reports `Stopped` at the
  external Phoenix VM path. The VM disk is preserved. No new VM job ran
  after the private lease release. The deadline timer has ended.
- `audit/continue-v1/DRAINING` and `PAUSED` exist. The deadline configuration
  and one-time native automation are paused. Start no worker or stale queue.
- Main remains clean and pushed at `2c9934a`. The byte diagnostic branch
  is clean and pushed at `7562edb`. U1 is clean and pushed at `11cb51b`.
  Both source commits passed the full mandatory hook and fresh Sol review.
  Root repeated all 114 new byte and 1,344 new U1 independent controls.
  All passed. Their ADRs are committed with their units. Integration is
  deferred to the next authorized work period. Preserve all later main
  additions when integrating these older branches.
- All 29 older pending public source files still match their committed
  backups. Their eight original worktrees and 92 public scratch paths in
  `m1-build-hardening` are retained. No new source file or ADR is pending
  in the two corrected source branches. The historical ten-file dependency
  backup and six-test F2 backup remain historical, not current patches.
- GitHub reported zero running and zero queued workflows at 00:55 UTC.
  The latest main native workflow remains successful. This documentation
  push does not launch the main-only workflow.
- Fresh independent Sol passed the frozen handoff delta and all six new
  report copies. Another fresh Sol passed the approved T2 hash addition
  and public disclosures. These reviews do not certify later shutdown.
  Root directly checked the process, VM and dispatch facts above.
- T2 is sealed. The approved T2 hash table is on this handoff branch.
  Integrate that addition into main before any sealed evaluation. Keep
  accepted T0 and T1 bytes exact. No private source, input or archive was
  read by root. All Phoenix reconstruction and later milestone gates
  remain open. Full capture review remains OPEN after provider screening.

The public `docs/checkpoints/2026-11-13-pause/operational-state.json`
records these operational facts. The canonical resume checkpoint binds
this final handoff commit, push proof, pending-file inventory, approved
aggregate T2 handoff, final reviews and shutdown evidence. It is published
and read after this commit. Its exact location is returned by `resume.mjs
read`. The principal agent then sets the existing goal to `paused` as the
last action at 01:11:47 UTC. This is a user-requested pause. It does not
satisfy SPEC section 9. Resume only after a new explicit instruction.
