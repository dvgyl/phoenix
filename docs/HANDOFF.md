# Phoenix thread handoff

Prepared on 2026-11-10 at the owner's request to continue in a new thread.
The v1 goal remains incomplete. M0 passed. M1 is awaiting exact replay
and final review. Main is fixed while that work runs.

## Read first

1. Source `/Volumes/Extreme Pro/Phoenix/env.sh` in every shell.
2. Read `AGENTS.md` and `SPEC.md` in full. These govern the work.
3. Read the attached `pstack:poteto-mode` skill in full at
   `/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.133/skills/poteto-mode/SKILL.md`.
4. Read this file, `docs/STATUS.md`, the latest `docs/LOG.md` entries,
   `docs/QUESTIONS.md`, and the last 20 commits.
5. Check free space and the live process and report state below.

The original Downloads attachments are missing. Use the tracked repository
copies. AGENTS.md SHA-256 is
`5dc37aed176f6a9990979b29df9b771bfaedcf07df6e09c1d34a5b851216bc3c`.
SPEC.md SHA-256 is
`dbc3ec8aab2fb74e5bab303017208a2ed93169acc7d2fb3e5938b88b2c073671`.
Both have been tracked since `2623d48`.

The owner authorized autonomous work through SPEC section 9. Use short,
clear ASD-STE100 prose. Commit and push green work. Delegate the required
algorithm, review, and corpus roles to GPT-6 Astra on Standard service.
The current thread used Standard-configured CLI workers because the
native explicit-model subagent tool advertised Priority service.
The launch briefs and guards are under the external `audit/` directory.

## Workspace and storage

The physical workspace is `/Volumes/PhoenixWork`. Its repository is
`/Volumes/PhoenixWork/phoenix`. The case-sensitive APFS sparsebundle is
stored under `/Volumes/Extreme Pro/Phoenix`. The environment script mounts
it and directs tools, caches, temporary files, runs and VM storage there.

The internal free-space baseline is 14,432,616 KiB. Investigate a drop below
12,479,491 KiB before more work. The latest check had about 15,991,516 KiB
free internally and 43,832,300 KiB free on the APFS workspace. Check again.
The dedicated Colima VM has four CPUs and 2 GiB of memory.

Execute original and rebuilt targets in the Linux containers. Host static
ELF inspection, C syntax checks, and Ghidra analysis are established paths.
Use `caffeinate -dimsu` for long operations. GitHub CLI uses
`GH_CONFIG_DIR=/Users/devg/.config/gh`.

## Main and the active M1 result

Main is clean at `efcad059d362bc61a4069268e1122d74e89c6054`.
The remote main has that revision. The accepted M0 tag is
`4ef231a1bbdc8d572e06dd5a44efff620dda0e97`. There is no M1 tag.

Frozen run `m1-t0-efcad05` has these `-O0` results.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

Two Phoenix variants failed `embedded_text`. One failed behavior.
Twelve raw variants have a compiler failure. Per architecture, 16 raw
GCC builds and eight raw Clang builds compiled. All 80 Phoenix builds
compiled with zero warnings. Both methods had 792 eligible original cases,
zero emulator disagreements and zero evaluation errors. Coverage is
790/1079 recovered block entries. Source branch coverage is a separate measure.

The frozen full model log SHA-256 is
`728cf1a3f10b21b54c7c747f7dabbbaada85c68b286110d5b865bfe77dd23f44`.
It records 80 calls, 1,159,763 input tokens, 650,880 cached input tokens,
and 52,065 output tokens. API-equivalent model cost is $1.603504.
Unknown-cost reservations are zero. Median reconstruction time across all
20 Phoenix variants is 51.892799854 seconds. It includes waits and failures.
The signed-in CLI cost measure is distinct from subscription charges.

The exact replay is `m1-t0-replay-efcad05`. All 40 submissions were captured
before this handoff. Held-out measurement was active at the last check.
Its process PID was 86475. Its log is
`/Volumes/PhoenixWork/audit/m1/m1-t0-replay-efcad05.log`.
The old thread's exec session was 21205. Use the PID, files and lock state
in a new thread because tool session handles can be chat-specific.

The fresh final Astra review was still active at PID 53202. Its session
was 83205. Its brief, public events, stderr and eventual reports are under
`/Volumes/PhoenixWork/audit/m1/final-efcad05/`.
It waits for the replay evidence. The report names are `review.md` and
`summary.md`. Check their actual contents before any milestone decision.

The final review directory already contains `result.json`, `aggregate.json`,
`original-ledger.json`, `ci-compare-all.json` and `preflight.md`.
After replay finishes, publish these additional files there.

- `replay-result.json`, copied from the frozen replay `m1.json`.
- `replay-aggregate.json`, produced with the existing aggregate helper.
- `replay-ledger-check.json`, with the independently checked full original
  log hash, stable-field equality, and replay-log absence.

The aggregate helper is
`/Volumes/PhoenixWork/audit/m1/summarize-category-report.py`.
The original and replay reports are below their run directories in
`/Volumes/PhoenixWork/runs/`. Reading frozen counts and categories is permitted.
The original model log is in `runs/m1-t0-efcad05-rebuild/llm.jsonl`.
The replay pipeline ID is `m1-t0-replay-efcad05-rebuild`.

Keep main, accepted images and locked tool files fixed until replay and
its checks finish. If the replay process has ended without a report, first
check the log and process state. The recorded-response resume command is
idempotent when the prior process has released the evaluation lock.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
cd "$PHOENIX_ROOT/phoenix"
caffeinate -dimsu uv run --locked phoenix-eval m1 \
  --run-id m1-t0-replay-efcad05 --replay m1-t0-efcad05
```

Require `reproduced=true`, every stable result field equal, the full original
model log hash preserved, and replay-log absence. Timing is the only excluded
result field. Require the fresh exact Astra PASS before tagging `m1` at efcad05.
If its process ends without a verdict, start a fresh Standard Astra reviewer
with the complete existing brief and all frozen evidence. Preserve any HOLD.

Native CI run `42859828267` passed on its third package-delivery attempt.
Earlier attempts rejected incorrect CA package bytes. The checksum pins held.
Current Mac M0 run `m0-43bba34c9d8d426aa1c029de0e5071c1` matches native runs
`m0-63e11acadaba4b53817dd84dd275338d` and
`m0-57503989b8684a089c788cbbe841a000`.
The scripted proof is `audit/m1/ci-efcad05/compare-all.json`.
[Exact CI run](https://github.com/dvgyl/phoenix/actions/runs/42859828267).

Retain both earlier measurements. `m1-t0-ce6a34d` scored zero fully
successful variants for both methods and reproduced on exact replay.
`m1-t0-5695148` scored Phoenix 17/20 and raw 0/20. Its replay reproduced.
Final review held 5695148 because the raw support header conflicted with
fortified glibc. Commit `ff4e427` corrected two format-parameter declarations.
Public red/green tests and all 48 Linux compiler-integrity checks passed.
The current main host gate passed 393 tests with 25 skips and 90.01% coverage.

## Sealing and access boundaries

Only a dedicated Corpus Author reads private source and held-out material.
The main agent uses stripped release binaries, permitted manifests, aggregate
adequacy records, and frozen category reports. Optional research tools and
new experiments use public fixtures. The interpretation for required pipeline
tools is recorded in `docs/QUESTIONS.md`.

Treat these paths and their contents as private to their Corpus Author.

- `/Volumes/PhoenixWork/sealed/src/`, including author events and stderr.
- `/Volumes/PhoenixWork/holdout/` and its input archives.
- Source archives under `/Volumes/PhoenixWork/sealed/`.
- Corpus Author Codex session histories, which can contain source text.

Keep private contents outside the repository and the main context. Preserve
all archive commitments. Publication follows the M4 freeze. Every report must
state that the corpus is agent-sealed on an honor system.

### T1 is complete and sealed

T1 has 15 programs and 90 GCC/Clang O0/O2/Os variants. The lead checked all
release hashes, ELF contracts, roster entries and aggregate adequacy records.
Permitted release metadata is `sealed/release/t1/`.
Permitted author handoff files are `audit/m2-corpus-author/{report,summary}.md`
and `parent-release-check.json`.

Source size is 304–316 C LOC. Keep this limited range visible in the report.
Minimum branch coverage is 184/197. Minimum mutation detection is 11/12.
One of 180 non-equivalent mutants survived, with a separate private witness.

The archive hashes are committed and pushed before T1 reconstruction.

| Archive | SHA-256 |
| --- | --- |
| `t1-source.tar.gz` | `6e1667e79f6f245d2e87c6558bea22d5d48f7de4847f9e6a35e2095a2c9a3385` |
| `t1-inputs.tar.gz` | `4f4394480b69a593ba1f2b68fb026db5ff69225ca4c6bf85cfc1602af73d8c8f` |

Remote branch `agent/t1-commitments` ends at `1d118ca`. Its two commits are
`f6d644b`, the hash-only commitment, and `1d118ca`, the progress record.
This handoff branch descends from them. Main integration waits for the M1 freeze.

### T2 is incomplete

The T2 author returned FAIL with one source draft, zero accepted programs,
and zero validated variants. It created neither final archive. It has ended
and reports zero active child processes. Its last metadata state says
`awaiting-runtime`. A fresh author must continue privately.

Read only `audit/m3-corpus-author/{brief,report,summary}.md` and `status.json`
for the parent handoff. The private draft and all detailed output are in
`sealed/src/t2/`. A fresh Standard Astra Corpus Author can read that private
namespace directly. Its guard is `audit/m3-corpus-author/guard.sb`.
The resource gate `audit/m3-corpus-author/linux-ready` is still absent.
Coordinate the 2 GiB VM before opening it. M1 replay and the pending observer
build have priority. The author contract requires 10 independent multi-file
programs, 60 variants, at least 20 meaningful mutants each, and a size spread
across 1,500–6,000 real C LOC. The full contract is in its public brief.

## M2 work and its exact state

### Static lift evidence has verified commits

Worktree `worktrees/m1-preflight-review-3`, branch `agent/m2-lift-evidence`,
has local commits `f9e4020` and `8964db0`. They await main integration.
The first adds bounded Ghidra storage, type-reference, register and jump-table
proposals, a strict reader, schema extension, tests and ADR0019.
The second applies the reviewer's internal `typeId` naming recommendation.

Fresh Astra closure review passed the bounded extension. It reran 14 original
independent tests and added 24 closure tests. The parent host gate passed
489 tests with 26 skips and 90.06% evaluator coverage. Public isolated Ghidra
runs preserved every legacy field and recovery output. A further parent check
proved all export fields equal after the naming change.
The final Java SHA-256 is
`7b9a7c600e28f35eef316fe3dde60ae2ce085d7ec6e609c767413539d9605e73`.

Public GCC and Clang switch fixtures each export 13 destinations and 12 labels.
The default destination has no label. The parent corrected an initial check
that required equal lengths. The reader retains separate arrays.
Evidence is in `audit/m2-survey/lift-evidence-fixed-review.md`,
`lift-evidence-fixed-parent-gate.log`, `lift-evidence-parent-naming.log`,
and `public-switch/parent-check.json`. Broader live custom-storage, recursive-type,
and large-export checks remain open. M2 milestone review remains required.

### Public trace prototype has uncommitted work

Worktree `worktrees/m2-prior-art-survey`, branch `agent/m2-trace-prototype`,
is based on 5695148. It has 26 prospective files. The prototype uses a separate
pinned QEMU 9.2.0 observer. Its PRIOR_ART, ADR0018, license and notice records
preceded implementation. The accepted oracle uses QEMU 8.2.2 and Rosetta.

Fresh source review passed public experimentation. The real fixture build then
exposed a worktree bind-mount assumption and a missing writable Clang temporary
path. The parent fixed the builder and added a transport regression.
All 16 actual Linux builds and static plans passed. The updated parent gate
passed 496 tests with 23 skips and 90.01% evaluator coverage.
Source and case commitments retain their values.

The observer image build and live calibration remain pending. Follow
`experiments/m2_trace/README.md` from that worktree. The accepted runtime context
and compiled fixtures are prepared under `tmp/m2-public-calibration/`.
The compiled manifest SHA-256 is
`c2516cbc609ca8bee334c3b5f47e511715fb82b92ed89545a31324beb0efd7bf`.
The new fixture-transport correction still needs independent closure review
before integration. Actual register timing, memory freshness, outcomes,
negative controls and three repetitions remain required runtime checks.
The recipe creates only `phoenix-m2-trace:arm64-qemu9.2.0-v1`.

Read `audit/m2-survey/algorithm-design.md`, `prototype-fixed-review.md`,
`trace-fixture-transport-report.md`, and `trace-fixture-plans.json`.
The directory also retains earlier review failures and fix evidence.

### M2 evaluation matrix is partial and fails lint

Worktree `worktrees/m1-ci-snapshot-review`, branch `agent/m2-evaluation-matrix`,
is based on `1d118ca`. The writer was stopped for this handoff. Its process and
children have ended. Changes are confined to `phoenix_eval/corpus.py` and the
new, untracked `phoenix_eval/m2.py`. Keep this partial code out of main.

The handoff check stopped in Ruff. One line exceeds the line limit.
The return annotation `Scope` is undefined. Later checks remain unrun.
The log is `audit/thread-handoff/evaluation-matrix-check.log`.
A fresh worker must finish and verify the feature.

The full brief is `audit/m2-survey/evaluation-matrix-brief.md`.
The design is `tmp/m2-evaluation-matrix/plan.md`.
It specifies 130 original variants and 260 method tasks with tier-separated
keys, one run budget, one model log, and a freeze before any held-out read.
It preserves M1 callers and replay. It adds grouped M2 scores and conservative
architecture checks. ADR0020 is reserved for this task.
Fresh independent harness and integrity review is required before sealed M2 use.

## Durable working-file backups

The original worktrees retain their current files. Additional public-source
backups and tracked patches are in `audit/thread-handoff/`.
`working-files.json` lists every file and archive hash.

| Backup | Files | SHA-256 |
| --- | --- | --- |
| `trace-prototype-working-files.tar.gz` | 26 | `de90f59cb60bed4a6eae707937d7844241aff66032e064accc973bfa78cdd386` |
| `evaluation-matrix-working-files.tar.gz` | 2 | `be1dd740cc2ae7479b64f607408a9ad6b75219a24c0a05801b117b09b6b4c609` |

These backups contain public implementation work. Private corpus material
stays in its separate namespaces. `audit/handoff-process-stop.json` records
the stopped writer. The detailed continuation record is
`audit/continuation-state.json`. This handoff supersedes its older process states.

## T3 and reuse

The metadata survey established the official `gpt-6.1-sol` knowledge cutoff
as 2026-04-30. Its seven candidates remain unqualified. Read
`audit/m2-survey/t3-metadata-report.md` before further selection. A separate
author must check publication history, license, and the full input contract.
Candidate source files were outside the main survey scope.

Before new reuse, record PRIOR_ART, the decision and license, then preserve
attribution in THIRD_PARTY_NOTICES. Prefer pinned upstream releases.
Keep optional experiments on public fixtures. Preserve the reported novelty
limits in SPEC section 2.2.

An earlier signing probe used host GnuPG 2.5.21 before its reuse entries were
written. The later ADR and LOG disclose this process deviation. Preserve that
disclosure in the final report. Corresponding-source and runtime-image
publication duties remain part of M4.

## Next actions in order

1. Check the active replay and read-only review. Finish and publish replay
   evidence. Require exact equality and the final Astra verdict.
2. Tag M1 only after acceptance. Then integrate the committed T1 hashes and
   update main progress files. The current replay uses efcad05.
3. Integrate the verified static evidence commits after the freeze ends.
   Run the full parent gate and review the exact integrated diff.
4. Build and calibrate the public observer. Coordinate VM resources with
   the fresh T2 author. Complete its runtime and source review gates.
5. Finish the M2 matrix implementation and its independent review.
   Add production recovery and localization from proven public evidence.
6. Measure and replay M2 against the sealed T0 and T1 rosters.
   Continue through M3 and M4 under SPEC section 9.

The v1 completion condition still includes the frozen T0–T3 evaluation,
every baseline and ablation, failure taxonomy, costs, public artifacts,
verified commitments, and replay of every headline result.
