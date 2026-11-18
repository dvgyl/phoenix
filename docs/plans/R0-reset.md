# R0: Reset the repository and measure the M1 path on corpus_dev

## Purpose

When this plan is complete, Phoenix has an honest and fast measurement loop. One command (`scripts/loop`) runs the pipeline on the development corpus, scores each binary on hidden cases, and adds one row to `docs/SCOREBOARD.md`. Hidden data is protected by a tested sandbox profile. The repository holds only the code that the measured path uses. The workspace has room for the next milestones.

Main metric: the D0 `-O0` binary success rate (`SPEC.md` section 2.3) with the M1 path.

- Value now: not measured. `corpus_dev` does not exist yet.
- Gate value: 80% or more (`docs/ROADMAP.md`, R0).

Experiment budget: 3 experiments. Only steps 14 and 16 make experiments. Step 16 has the third experiment as its reserve: a fix of a demonstrated defect, or a declared cold replication when no defect remains (`docs/ROADMAP.md` section 7, rule 6). A plan never extends a budget (AGENTS.md section 10 Milestones and ExecPlans).

## Progress

- [x] Step 0: Record the start commit (check: `git rev-parse HEAD` -> `1a3716cbce54f1b008afc9e3d0732f7364d5569b`)
- [x] Step 1: Storage cleanup (done before this plan; evidence in "Surprises and Discoveries": 31 GiB free of 60 GiB)
- [x] Step 2: Write `scripts/gc` without run archiving (check: `scripts/gc --dry-run` -> exit 0; candidates in `$PHOENIX_ROOT/tmp/r0-gc-dry-run.log`; free space 31 GiB before and after)
- [x] Step 3: Write the resize procedure and run its dry run (check: `$PHOENIX_ROOT/runs/r0-resize.json` -> `"status": "dry_run_ok"`; image size 60 GiB before and after; VM free 14 GiB)
- [x] Step 4: Protected path list, role profiles, caller migration, `scripts/launch-role`, `phoenix-eval probe` (check: 72 targeted tests passed, including `tests/test_protection.py`; `uv run --locked phoenix-eval probe` -> 88 checks, each `denied=true`; review round 2 found no remaining defect; evidence in `$PHOENIX_ROOT/tmp/r0-protection-tests-round2.log`, `r0-probe.log`, `r0-protection-review-2.log`)
- [x] Step 5: Commit the instruction documents and the protection change on `main` (check: `git show main:docs/plans/R0-reset.md` and `git show main:phoenix_eval/protection.py` -> exit 0; reviewed protection committed as `a52db2c`; commit hook passed)
- [x] Step 6: Build the worker images and start the Dev Author on batch 1 (check: both image builds and `docker image inspect phoenix-worker:amd64` -> exit 0; worker session `01a1e7f1-53ea-7c91-adc4-a0d6a485d66d` runs in `$PHOENIX_ROOT/worktrees/dev-author`, branch `dev-corpus-1`, at `high` effort and Standard service; log `$PHOENIX_ROOT/tmp/r0-dev-author.log`)
- [x] Step 7: Salvage: restore, change and delete (check: imports -> exit 0; deleted-module search -> no matches; `./scripts/check` -> exit 0, 783 passed and 25 skipped; evidence `$PHOENIX_ROOT/tmp/r0-salvage-check.log`)
- [x] Step 8: Create `phoenix/config.py` (check: both model identifiers occur only in `phoenix/config.py`; price tuples match the evaluator; 108 targeted tests passed; strict type check passed; evidence `$PHOENIX_ROOT/tmp/r0-config-tests.log`)
- [x] Step 9: Smoke run of the M1 path on `corpus_public/bitstats.c` (check: `$PHOENIX_ROOT/runs/r0-smoke.json` -> dev pass rate 1.0, integrity passed, all project files byte-identical, `"replay_identical": true`; run `r0-smoke-85594d46f285453883b5954d37c0a9fe`, replay `r0-replay-352b75aa4ca34aefb53a70d46dfdf26f`, commit `7a43189`)
- [x] Step 9a: Land the runtime model change with its tests. The review of `0cbf8f9` found no reproducible defect. Both models replied at the Standard tier. All 74 model and accounting tests and all 1105 full-check tests passed. Both worker images rebuilt from `6c18483`. Evidence: `$PHOENIX_ROOT/tmp/r0-restart-model-tests.log`, `r0-restart-step9a-check.log` and `r0-restart-worker-images.log`.
- [x] Step 9b: Extend the pipeline denial. The synthetic checks cover the new paths and the permitted input and replay files. The real probe returned 648 denied reads with zero failures. The full check passed. The replacement branch passed its independent review and is on `main` at `234387e`. Evidence: `$PHOENIX_ROOT/tmp/r0-restart-step9b-authorized-probe.log` and `r0-restart-step9b-key-review.log`.
- [x] Step 9c: Repeat the public smoke run with the new runtime model. All four builds matched all 7 development cases. The integrity check passed. The replay reproduced all 5 project files byte for byte. `run.json` records the current runtime model and the active pipeline profile. Evidence: `$PHOENIX_ROOT/runs/r0-smoke.json`.
- [x] Step 10: Rebuild the development corpus with the `linux/amd64` compilers. The manifest contains 176 binaries from 22 programs and zero invalid twins. Only the main checkout can run the writer. The tests and the independent review passed. Evidence: `$PHOENIX_ROOT/tmp/r0-restart-step10.log` and `r0-restart-step10-review-2.log`.
- [x] Step 10a: Validate the 22 programs, one program at a time. All 22 commands exited 0. The manifest contained 176 binaries after each program. The evaluator accepted 62,784 valid case and binary pairs across all variants, with zero exclusions. Evidence: `$PHOENIX_ROOT/tmp/r0-restart-validation.log`.
- [ ] Step 11: `phoenix_eval/run.py`, `scripts/loop`, `docs/SCOREBOARD.md`, `scripts/gate`, replay restore (check: `scripts/loop --probe --tier D0 --opt O0` -> exit 0, one row with `loop` = `probe` and `exp` = `-`, and 20 selected binaries); implementation committed as `06f20a1`; canonical publication and typed claims pass 393 related tests in `$PHOENIX_ROOT/tmp/r0-loop-reduction-worker.log`; the probe awaits Step 10a.
- [ ] Step 11a: Bring `tools/adequacy.py` to the sampling, timeout, exclusion and case-minimum rules of `SPEC.md` section 10.6 (check: `uv run --locked pytest -q tests/test_adequacy.py` passes)
- [ ] Step 12: Corpus acceptance: adequacy (check: `uv run --locked python tools/adequacy.py --summary` -> 22 programs at or above both thresholds under the current `SPEC.md` section 10.6; `corpus_dev/quick.txt` and `corpus_dev/accepted.json` exist); partial evidence from the earlier tool version: `driftstat` passes (60/62 branches, 221/243 mutants); `branchmark` passes (249/262 branches, 265/288 mutants, run `74eb878dd7fe4e6e9c5fbc2828f0053b`); `chromapath` fix round 1 passes all 8 validation builds with 518 cases and zero exclusions; its pilot was interrupted at the owner pause and needs a rerun. Seven programs have complete validation. Evidence is in `$PHOENIX_ROOT/tmp/r0-corpus-validation-resumed.log` and `$PHOENIX_ROOT/tmp/r0-chromapath-fix-1-validation.log`.
- [ ] Step 12a: Model-change quick loop (check: `scripts/loop --quick --label "model change"` -> one row with `loop` = `quick`)
- [ ] Step 12b: Repeat the D0 `-O0` probe if a corpus hash changed after Step 11 (check: a probe row with the hashes of `corpus_dev/accepted.json` and 20 selected binaries, or one `docs/LOG.md` line that says both hashes are unchanged)
- [ ] Step 13: R0 bootstrap acceptance (check: `scripts/gate R0-bootstrap` -> `R0-bootstrap: PASS`; declared design: 1 of 3 for the whole item; gate attempts used: 0)
- [ ] Step 13a: Commit the accepted corpus, the quick set and the baseline settings (check: `git status --short corpus_dev phoenix phoenix_eval` prints nothing)
- [ ] Step 14: Experiment 1: the M1 path baseline on D0 and D1, immediately after step 13a (check: a row with `exp` = `1/3`)
- [ ] Step 15: Noise measurement at the same `HEAD` as experiment 1, then one commit of both rows and `docs/STATUS.md` (check: `scripts/loop noise` -> one row with `loop` = `noise` and the commit of experiment 1)
- [ ] Step 16: Integrity window fix, fixtures, review, rescore, experiment 2 (check: `uv run --locked pytest -q tests/test_integrity.py` -> all pass; `PHOENIX_COMPILER_INTEGRITY_ARCHES=amd64,arm64 uv run --locked pytest -q tests/test_integrity_window_challenge.py` -> each pinned case executed and passed; `$PHOENIX_ROOT/runs/r0-window-rescore.json` exists; a row with `exp` = `2/3`)
- [ ] Step 17: Mechanical gates of `scripts/check` (check: `uv run --locked pytest -q tests/test_check_gates.py` -> all pass)
- [ ] Step 17a: Gate changes for the main-metric line, condition 5 and condition 6 (check: `uv run --locked pytest -q tests/test_check_gates.py` -> all pass, with the new cases of Step 17a)
- [ ] Step 18: R0 gate and tag (check: `scripts/gate R0` exits 0 and the last line is `R0 gate: PASS` or the `R0 metric missed` line of Step 17a; `git tag -l r0` -> `r0`; the tag message holds the final full-loop row)

## Pause checkpoint (2026-11-17)

The owner requested a pause. All workers, validation processes and target
containers are stopped. R0 is not complete. The `r0` tag does not exist.
The saved aggregate state is in
[`pause-checkpoint.json`](../evidence/r0/pause-checkpoint.json).

- Main code: `8fdbd1e`. Its full check passed 1105 tests, with 38 skipped,
  87.56% evaluator coverage, and a time of 65.33 seconds.
- The 22 candidate programs and 7848 cases are saved. All 176 variants built
  with zero invalid twins. The current manifest has 56 entries from the
  seven completed validation programs.
- Validation is complete for `branchmark`, `chromapath`, `driftstat`,
  `fernconf`, `gapmeter`, `knotconf` and `lumaquilt`. All eight builds of each
  program passed with zero excluded cases.
- Current adequacy passes: `branchmark` and `driftstat`. The new 518-case
  `chromapath` pilot was stopped. Its request is local run
  `161a4413a7364bf698830c225af2be8f`. Rerun this pilot. Its earlier report
  describes 509 cases and is stale.
- The unmerged compiler-name prototype is saved as `879d612` on
  `wip/r0-local-name-evidence`. Its full check passed 1117 tests, with
  41 skipped. Pinned compiler builds, golden comparisons and critical
  review remain open. Check the aggregate handling of unavailable counts.
- The pending Step 16 challenge fixtures are saved in
  `R0-integrity-window-fixtures.patch`. `git apply --check` passes on main.
  The patch is not active. Apply it at Step 16 and adapt evidence fields
  if the compiler-name prototype is merged.
- Python source has 10638 nonblank lines. The owner review changed the R0
  limit to fewer than 11000 (see "Owner review after the pause").
- No full-loop, noise or sealed run was started. The experiment count is 0.
  The bootstrap design is 1 of 3. Its gate has not been attempted.

The 15 programs without validation are: `niblace`, `pairfold`,
`patchpanel`, `prismcsv`, `recordloom`, `runepack`, `skeinwire`, `spanrank`,
`tariffgrid`, `tilehash`, `tokenlace`, `unitforge`, `velocalc`, `weighbit`
and `wordweft`. Step 10a validates them one at a time. Resume with the
"Restart block" and the Progress order. The run directories and container
images remain on the external workspace under `PHOENIX_ROOT`.

## Owner review after the pause

An owner review of the commits from `1a3716c` to `08ed17f` found that
17 commits gave 0 scoreboard rows. About half of the new `docs/LOG.md`
lines are review rounds or source-size cuts. Six commits removed only
219 lines. This is the stall pattern of the work before the restart.
These rules apply until the row of experiment 1 exists:

1. Code freeze. Change code only when a check of steps 9a to 15 fails,
   when a Dev Author fix round needs a corpus change, or for this allowed
   work:
   - Step 9a: the runtime model change in `phoenix/config.py`,
     `phoenix_eval/model_ledger.py` and their tests.
   - Step 9b: the pipeline denial in `phoenix_eval/protection.py` and
     `tests/test_protection.py`.
   - Step 10: the manifest-writer guard in `phoenix_eval/dev_corpus.py`.
   - Step 11a: the adequacy rules in `tools/adequacy.py` and
     `tools/adequacy_support.py`.
   - Step 16: the window fix, the challenge fixtures and the rescore
     command.
   - Step 17a: the gate changes in `scripts/check_gates.py`: the
     main-metric line, warm timing (condition 5) and the window challenge
     run (condition 6).
2. Do no work whose only purpose is to remove source lines. The R0 limit
   is now fewer than 11000 nonblank lines. The limit of 15000 for all
   milestones is unchanged.
3. Do not merge `wip/r0-local-name-evidence` (`879d612`) in R0. Step 16
   uses the saved fixture patch on main.
4. Run the corpus fix rounds in parallel: at most 4 Dev Author workers at
   one time (AGENTS.md section 7). Each worker has one program, its own
   branch `dev-fix-<program>` and its own worktree
   `$PHOENIX_ROOT/worktrees/dev-fix-<program>`. Workers never run
   `scripts/build-dev-corpus`. The lead is the only writer of
   `$PHOENIX_ROOT/dev_bin/manifest.json`. The lead reads each diff and runs
   the official acceptance commands from the main checkout.
5. Order: Step 9a model change, Step 9b denial, Step 9c smoke run, Step 10
   manifest rebuild, Step 10a validation, Step 11 D0 `-O0` probe, Step 11a
   adequacy tool, Step 12 adequacy and acceptance files, Step 12a quick
   loop, Step 12b repeated probe, Step 13 bootstrap, Step 13a commit,
   Step 14 experiment 1, Step 15 noise and one commit of both rows. Then
   steps 16 to 18. Step 17 code exists already. Connect
   `scripts/check_gates.py` to `scripts/check` only at Step 17.
6. The bootstrap item has one count of 3 declared designs
   (`docs/ROADMAP.md`, R0, "Rules for the bootstrap count").

The R0 gate condition for the main metric is unchanged. If the main metric
is below 80% after the experiment budget, `docs/ROADMAP.md` section 7
rule 6 applies, and `scripts/check_gates.py` implements that rule
(Step 17a).

## Restart block

Keep this block current. A new session resumes from it.

| Item | Value | Restore or regeneration command |
|---|---|---|
| Code commit for the Step 9c smoke run | `234387ee842866051a330e9266daec72c2fa7e12` | `git log -1 --format=%H` |
| Models and roles | the table of AGENTS.md section 6.1; Reviewer: lead model, new session | `grep -n -A6 '^| Role name' AGENTS.md` |
| Image IDs for Step 9c | Both worker and both integrity image IDs are in `$PHOENIX_ROOT/tmp/r0-restart-step9c-images.log`. | `./scripts/build-images worker amd64 && ./scripts/build-images worker arm64`; `./scripts/build-images integrity amd64 && ./scripts/build-images integrity arm64` |
| Worker checkouts | `$PHOENIX_ROOT/worktrees/dev-fix-<program>` | `git worktree list --porcelain` |
| Smoke and replay IDs | `r0-smoke-0bc2d530812b4f79af6a8ff99f4900b0`, `r0-replay-d4b9851e96b9440cbe1ec5336ba7c5dc` | Step 9c. Image IDs and command output: `$PHOENIX_ROOT/tmp/r0-restart-step9c-images.log` and `r0-restart-step9c.log`. |
| Resize record | `$PHOENIX_ROOT/runs/r0-resize.json` | `scripts/resize-workspace --dry-run` |
| Manifest | 176 of 176 binaries. Zero invalid twins. | `scripts/build-dev-corpus` |
| Validation status | 22 of 22 with the Step 10 validator. All 176 variants have zero exclusions. | `scripts/build-dev-corpus --check <program>`. The validation log is `$PHOENIX_ROOT/tmp/r0-restart-validation.log`. |
| Adequacy status | `<passing programs>` of 22, with run IDs | `uv run --locked python tools/adequacy.py <program>` |
| Probe and quick rows | `<rows>` | Steps 11, 12a and 12b |

Before reuse, verify the public smoke replay and each saved adequacy report
against its raw artifacts. Regenerate only missing or stale evidence.

## Surprises and Discoveries

- The first storage cleanup is done. Evidence: `df -h /Volumes/PhoenixWork` shows 31 GiB free of 60 GiB. The cleanup deleted the entries of `$PHOENIX_ROOT/tmp` that were older than the cleanup (22 GiB of old review artifacts), `$PHOENIX_ROOT/audit` (413 MiB), and the two host package caches `cache/pip-host-cache-*` and `cache/homebrew-host-cache-*`.
- Old worktrees and all local agent branches are removed. Each branch tip is kept as a tag `archive/branch/<name>`.
- Remaining large users of the image: `vm/colima` 17 GiB, `sealed` 6.9 GiB, `cache` about 1.5 GiB, `tools` 1.2 GiB, `runs` 429 MiB.
- `docs/adr/` and `docs/QUESTIONS.md` are deleted. `docs/DECISIONS.md` replaces them.
- `$PHOENIX_ROOT/vm/colima/default/colima.yaml` sets a VM disk limit of 32 GiB. The VM disk is inside the workspace image.
- `.gitignore` ignores `/tools/`. Thus a new `tools/` directory in the repository is not committed until step 7 removes that line.
- `$PHOENIX_ROOT/runs/m1-t0-*` hold the evaluator records of the sealed T0 run at M1. Treat them as sealed records (step 4).
- `docs/corpus_commitments.md` had a link to a deleted T3 record archive and a banned process term. That note was replaced before R0. No hash line changed.
- `scripts/build-worker` builds `phoenix-toolchain` only for the native architecture (`arm64` on this host). `phoenix-worker:amd64` is built from the same `toolchain` stage of `containers/Dockerfile` for `linux/amd64`, and contains `gcc`, `clang` and the binutils. Step 10 uses it.

## Decision Log

- Delete the two checked-switch CLI test functions. They test the removed option. The remaining CLI tests stay.

- Keep `corpus_public/` as the harness self-test corpus of `phoenix-eval m0`. Reason: `runprobe.c` is a sandbox probe, not a reconstruction target, and `m0.py` reads this layout. Alternative not selected: move the three programs into `corpus_dev/`.
- Protect `$PHOENIX_ROOT/runs/m1-t0-*` in place with the `sealed_runs` rule. Reason: a move would write into a sealed directory. Alternative not selected: move them to `sealed_runs/`.
- Keep `phoenix_eval/model_ledger.py`, `phoenix_eval/development.py` and `phoenix_eval/submission.py` in R0. Reason: the M1 path imports them. R1 rewrites the ledger and the submission rules. Alternative not selected: rewrite them in R0 before the first row.
- Restore `phoenix/lift`, `phoenix/generate` (except `raw.py`), `ghidra_scripts/ExportLift.java` and `schemas/lift.schema.json` from commit `6897e47`. Reason: that commit holds the accepted M1 lift and generation. Alternative not selected: remove the switch code from the current versions.
- Accept the corpus before experiment 1, and measure the noise before the integrity fix. Reason: a baseline and a noise value are valid only for a fixed corpus, and the comparison of experiments 1 and 2 needs the noise threshold.
- Bundle the R0 prerequisites into one bootstrap enabling item (step 13). Reason: no success number exists before the protection, the salvage, the corpus and the loop are ready. AGENTS.md section 9 Anti-stall rules counts this bootstrap as one enabling item.
- Use `phoenix-worker:amd64` for the corpus builds. Reason: it holds the pinned `linux/amd64` compilers. Alternative not selected: a second `linux/amd64` build of the `toolchain` stage.
- The evaluator copies each release binary into the pipeline run directory. Reason: the `pipeline` profile then denies each sealed path without an exception. Alternative not selected: keep the `release` exception of the current `guarded_command`.
- Owner decision: the R0 source limit is fewer than 11000 nonblank lines, not 9000. Reason: the in-scope evaluation loop, archive recovery and protection code put the source at 10638, and the cuts toward 9000 used six commits for 219 lines with no measurement. Alternative not selected: keep 9000 and continue the size cuts before experiment 1.
- The stale-row gate counts an enabling item's acceptance run as its measurement. Reason: `docs/ROADMAP.md` gives enabling items their own acceptance test instead of a scoreboard row. If AGENTS.md section 9 Anti-stall rules gives another mechanism, use that mechanism and add one line here.

## Outcomes and Retrospective

None yet.

## Context and Orientation

The repository is `$PHOENIX_ROOT/phoenix` (`/Volumes/PhoenixWork/phoenix`) on the branch `main`. The tag `archive/pre-restart` holds the state before the restart. The restart commit `e591d41` deleted the unreachable code. These items are already deleted: `phoenix/observe`, `phoenix/public_checks`, `phoenix/lift/byte_*`, `phoenix_eval/project_profile.py`, `scripts/check-m2-public`, `corpus_public/mechanisms`, their tests and the old process documents. `tests/conftest.py` already disables Hypothesis deadlines.

The workspace is a case-sensitive APFS sparse bundle, `"/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`, mounted at `/Volumes/PhoenixWork` by `"/Volumes/Extreme Pro/Phoenix/env.sh"`. The image has 60 GiB with 31 GiB free. The external drive had about 60 GiB free at the restart. The host is an Apple Silicon Mac (`docs/DECISIONS.md`, entry 1). Linux execution uses Colima (`docs/DECISIONS.md`, entry 2).

The M1 path (`phoenix run` without flags) is: `ingest`, `analyze` (dev set), `lift` (Ghidra), `recover`, `generate` (one whole-program prompt), `verify` (four builds and dev cases), `repair` (up to 20 rounds), `package`. Its modules are `phoenix/__main__.py`, `phoenix/pipeline.py`, `phoenix/ingest`, `phoenix/analyze`, `phoenix/lift`, `phoenix/recover/__init__.py`, `phoenix/generate`, `phoenix/verify`, `phoenix/repair`, `phoenix/package` and `phoenix/llm`. M1 reached 17 of 20 fully successful binaries on sealed T0 `-O0`. Two failures were false positives of the embedded-text rule. One was a behavior failure.

Import facts that the salvage must respect:

- `phoenix/pipeline.py` imports `phoenix.generate.switch_plan` and `phoenix.lift.mapping`.
- `phoenix/generate/__init__.py` imports `phoenix.generate.protected_switch`. `phoenix/lift/__init__.py` imports `phoenix.lift.mapping`.
- `phoenix/llm/provider.py` and `phoenix/llm/ledger.py` import `phoenix_eval.model_ledger`.
- `phoenix_eval/m1.py` imports `phoenix_eval.m2`, `phoenix_eval.capture_binding`, `phoenix_eval.development` and `phoenix_eval.model_ledger`. `phoenix_eval/submission.py` imports `phoenix_eval.development`.
- `guarded_command` has two callers: `phoenix/llm/codex.py` (`guarded_command(self.workspace, command)`, after `inherited_guard`) and `phoenix_eval/submission.py` (`guarded_command(workspace, ..., release=True, probe=probe)`, with the probe file and `PHOENIX_PIPELINE_GUARD`). `tests/test_submission_recovery.py` replaces it with a stub.
- The model identifiers are in `phoenix/llm/provider.py` (enum `Model`) and in the price table of `phoenix_eval/model_ledger.py`.
- The integrity entry point is `phoenix_eval.integrity.check_integrity`.

Terms that this plan uses beyond `docs/ARCHITECTURE.md`:

- "M1 path" is the pipeline as it was at commit `6897e47`.
- "Reference worktree" is a worktree of that commit at `$PHOENIX_ROOT/worktrees/m1-reference`.
- "Bootstrap item" is the R0 enabling item of steps 4 to 12b. Its acceptance command is `scripts/gate R0-bootstrap`.

## Plan of Work

The sequence follows `docs/ROADMAP.md`, R0. Storage and protection come first. The salvage comes next. The Dev Author writes batch 1 in parallel from step 6. The corpus is accepted before experiment 1, in the order of "Owner review after the pause", item 5. Then the M1 path gives the first row before any new subsystem.

| Item | Steps | Metric | Expected result | Limit |
|---|---|---|---|---|
| Storage | 1 to 3 | free GiB | 15 GiB or more free; resize record | 3 attempts |
| Bootstrap item (enabling): protection, salvage, corpus build, batch 1 with validation and adequacy, evaluation loop | 4 to 13a | bootstrap checks passed | `scripts/gate R0-bootstrap` -> PASS | 3 declared designs for the whole item |
| Baseline | 14 | D0 `-O0` success | measured (M1 reached 85% on sealed T0 `-O0`) | experiment 1 |
| Noise | 15 | flip rate for each tier | recorded | no experiment |
| Integrity fix | 16 | D0 `-O0` success; rescore count | a gain of up to the count of experiment-1 binaries whose only integrity category is `embedded_text` | experiments 2 and 3 |
| Mechanical gates | 17 and 17a | gate tests | all pass | 3 attempts |

Inside the bootstrap item, each program of batch 1 has at most 2 rounds of fixes. Then the Dev Author replaces it. A replacement does not reset the bootstrap count.

Critical code in this plan needs the review of AGENTS.md section 8 Review before it merges: `phoenix_eval/protection.py`, `phoenix_eval/submission.py`, `phoenix_eval/run.py`, `phoenix_eval/integrity.py`, `phoenix_eval/quality.py`, `scripts/launch-role` and the scoring part of `scripts/loop`. Start the review when each change is ready. Continue with other steps while the review runs.

## Concrete Steps

Run each command from `$PHOENIX_ROOT/phoenix` after `source "/Volumes/Extreme Pro/Phoenix/env.sh"`, unless a step says otherwise. After each change in `phoenix_eval/` or `containers/`, rebuild the worker images with the command of step 6 before the next loop, because the images contain a copy of `phoenix_eval/`.

### Step 2: `scripts/gc`

Write `scripts/gc [--dry-run]` as a POSIX shell script. It prints the free space before and after. In R0 it does only these actions:

1. Delete each Ghidra project directory under `$PHOENIX_ROOT/runs`.
2. Delete each entry of `$PHOENIX_ROOT/tmp` that is not newer than `$PHOENIX_ROOT/tmp/.gc-mark`. At the end, write a new `.gc-mark`.
3. Run `docker builder prune --all --force` and `docker image prune --force`. Remove each image whose repository does not start with `phoenix-`.
4. Run `colima ssh -- sudo fstrim -av`. This returns the freed VM blocks to the image.
5. Print each run directory above 2 GiB.

`scripts/gc` never deletes a run directory until step 11 adds run archiving. `scripts/gc` never touches `sealed`, `holdout`, `sealed_b`, `holdout_b`, `sealed_runs`, `runs/m1-t0-*`, `dev_bin` or `cache/phoenix/llm`. With `--dry-run`, it prints the actions and changes nothing.

### Step 3: resize procedure

Write `scripts/resize-workspace [--dry-run]` as a POSIX shell script. In R0, run only `scripts/resize-workspace --dry-run`. The dry run computes `allocated`, `host_free` and `size` (step 4 below), prints each command of the procedure, changes nothing, and writes `$PHOENIX_ROOT/runs/r0-resize.json` with the status `dry_run_ok` or `blocked_on_owner`. Run the real procedure only when the storage rule of `docs/ROADMAP.md` section 9 requires it.

The real procedure detaches the workspace image. Thus run the script text from memory, with the working directory outside the image:

```sh
script_text=$(cat scripts/resize-workspace)
cd / && sh -c "$script_text"
```

The real procedure does these steps:

1. Record the VM file system free space with `colima ssh -- df -Pk /var/lib/docker`. Then run `colima stop`.
2. Run `hdiutil detach /Volumes/PhoenixWork`. If it fails, run `lsof /Volumes/PhoenixWork`. If each listed entry has the descriptor type `cwd` or `txt`, run `hdiutil detach -force /Volumes/PhoenixWork`. Otherwise stop the listed processes other than the current session and try one more time. If it still fails, go to step 7 with the status `blocked_on_owner`.
3. Run `hdiutil compact "/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`.
4. Compute `allocated` (GiB, rounded up) with `du -sk` on the bundle, and `host_free` (GiB, rounded down) with `df -k "/Volumes/Extreme Pro"`. Compute `size = min(100, allocated + host_free - 20)`. If `size` is not above the current image size, go to step 7 with the status `blocked_on_owner` and the reason `external drive free space`.
5. Run `hdiutil resize -size "${size}g" "/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`.
6. Attach the image with `. "/Volumes/Extreme Pro/Phoenix/env.sh"`. Find the store with `diskutil info /Volumes/PhoenixWork | awk -F': *' '/APFS Physical Store/ {print $2}'`. Run `diskutil apfs resizeContainer <store> 0`.
7. Exit path. Each path after `colima stop` ends here, also after an error:
   1. Attach the image if it is not attached: `hdiutil attach -nobrowse -mountpoint /Volumes/PhoenixWork "/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`.
   2. Run `colima start`. Check with `docker info`.
   3. Write `$PHOENIX_ROOT/runs/r0-resize.json` with `status`, `reason`, `size_before_gib`, `size_after_gib`, `host_free_before_gib`, `host_free_after_gib` and `vm_free_gib`.

Keep the Colima disk limit at 32 GiB. Increase it only when `colima ssh -- df -Pk /var/lib/docker` shows less than 5 GiB free, and only by an amount that the free space of the image covers with 10 GiB to spare.

Check (R0, dry run): `r0-resize.json` has the status `dry_run_ok`, and `df -h /Volumes/PhoenixWork` shows an unchanged size. If the status is `blocked_on_owner`, write the item under `BLOCKED ON OWNER` in `docs/STATUS.md` (AGENTS.md section 3 Autonomy) and continue. Check (real procedure, later): `df -h /Volumes/PhoenixWork` shows the new size, `docker info` exits 0, and the status is `ok`.

### Step 4: protection

Change `phoenix_eval/protection.py` to the interface in "Interfaces and Dependencies". The protected paths are in this table. `SPEC.md` section 10.5 is the source. If this table differs, follow `SPEC.md`.

| Class | Paths | Profiles that deny the class |
|---|---|---|
| sealed | `$PHOENIX_ROOT/sealed`, `holdout`, `sealed_b`, `holdout_b` | `pipeline`, `engineer`, `dev-author` |
| sealed records | `$PHOENIX_ROOT/sealed_runs`, `$PHOENIX_ROOT/runs/m1-t0-*` | `pipeline`, `engineer`, `dev-author`, `corpus-author` |
| development hidden data | `<checkout>/corpus_dev/*/src`, `<checkout>/corpus_dev/*/holdout`, `<checkout>/corpus_dev/*/tasks`, `$PHOENIX_ROOT/dev_bin/*/*/*.twin` | `pipeline`, `corpus-author` |
| dev-set code and prompts | `<checkout>/phoenix/analyze`, `<checkout>/phoenix/devset`, `<checkout>/phoenix/generate/prompts` | `dev-author`, `corpus-author` |
| corpus sources | `<checkout>/corpus_dev` | `corpus-author` |

`<checkout>` is the main checkout `$PHOENIX_ROOT/phoenix` and each registered worktree under `$PHOENIX_ROOT/worktrees/` (from `git worktree list --porcelain`). Generate one rule for each copy, at each launch. The `allow` argument of `guarded_command` permits named paths inside a denied class. A sealed run (from R2) uses it to give the `pipeline` profile only its own private work directory under `$PHOENIX_ROOT/sealed_work/` (`SPEC.md` section 10.5). Step 9b extends the `pipeline` denial. The `evaluator` profile denies nothing. Remove the macOS-only check for the policy generation, but keep `sandbox-exec` as the only mechanism in R0. R1 adds `bwrap` for Linux.

Migrate each caller of `guarded_command` and its tests in the same change:

- `phoenix/llm/codex.py`: call `guarded_command(workspace, repo, command, "pipeline")`. Keep the `inherited_guard` check before the call.
- `phoenix_eval/submission.py`: call `guarded_command(workspace, repo, command, "pipeline")`. Keep the probe file and `PHOENIX_PIPELINE_GUARD`. Copy the release binary into the pipeline run directory before the launch, and give the pipeline that copy. This replaces the `release` option.
- `tests/test_submission_recovery.py` and each other test that stubs `guarded_command`: use the new signature.

Write `scripts/launch-role <role> -- <command...>`. It calls `uv run --locked python -m phoenix_eval.protection launch <role> -- <command...>`. For the `pipeline` role, it creates the probe file and sets `PHOENIX_PIPELINE_GUARD`.

Add `phoenix-eval probe`. For each profile and each existing protected path of this host, it attempts one read under the profile. It prints one line for each check, `<profile> <class> <checkout> denied=true|false`, and nothing else. The lead model never runs `ls` or `cat` on a sealed path.

Extend `tests/test_protection.py`. For each profile, build a temporary layout with a main checkout, a worker checkout under a temporary `worktrees/` directory, each protected path and one allowed path. Run `cat` on a probe file in each path under the generated profile. Each protected probe is denied in both checkouts. Each allowed probe is readable.

Check: `uv run --locked pytest -q tests/test_protection.py tests/test_submission.py tests/test_submission_recovery.py tests/test_llm.py` passes. `uv run --locked phoenix-eval probe` prints only `denied=true`.

### Step 5: documents and protection on `main`

Commit the instruction documents (`AGENTS.md`, `SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, this plan) and the reviewed protection change on `main` before you create the worker worktree.

Check: `git show main:docs/plans/R0-reset.md > /dev/null` and `git show main:phoenix_eval/protection.py > /dev/null` exit 0.

### Step 6: worker images, Dev Author brief and launch

Before `scripts/launch-role` exists (steps 0 to 4), do not delegate.

Build the worker images. The Dev Author needs `phoenix-worker:amd64` to build and run its programs:

```sh
./scripts/build-images worker amd64 && ./scripts/build-images worker arm64
```

Create the worktree and start the Dev Author with the lead model identifier from AGENTS.md section 6.1:

```sh
git worktree add -b dev-corpus-1 "$PHOENIX_ROOT/worktrees/dev-author" main
scripts/launch-role dev-author -- codex exec -m <lead model> \
  -c model_reasoning_effort=high -c service_tier=default --sandbox danger-full-access \
  -C "$PHOENIX_ROOT/worktrees/dev-author" \
  "Read docs/plans/R0-reset.md, section 'Dev Author brief'. Do that work. Commit on branch dev-corpus-1."
```

The role profile is the sandbox of the worker. Never use `danger-full-access` without `scripts/launch-role`.

#### Dev Author brief

Write 22 new C11 command-line programs in `corpus_dev/`. Do not read `$PHOENIX_ROOT/sealed*`, `$PHOENIX_ROOT/holdout*`, `phoenix/analyze`, `phoenix/devset` or `phoenix/generate/prompts`.

Sizes and kinds (lines as defined in `SPEC.md` section 2.1):

| Tier | Programs | Lines | Kinds |
|---|---|---|---|
| D0 | 10: two in each of 40 to 100, 101 to 160, 161 to 220, 221 to 260 and 261 to 300 lines | 300 or less, one source file | statistics, checksums, encoders |
| D1 | 12: three in each of 301 to 600, 601 to 900, 901 to 1,200 and 1,201 to 1,500 lines | 1 to 3 source files | configuration and CSV transformers, calculators, codecs, image filters |

The D1 programs together contain: structs in each program; function pointer tables in 4 or more; a `switch` with 8 or more cases in 6 or more; recursion in 4 or more; `getopt` or `getopt_long` in 8 or more; floating-point output in 3 or more; a directory tree as input or output in 3 or more; static local variables in 3 or more; `qsort` with a comparator in 3 or more.

Rules for each program:

- It obeys the input contract (`SPEC.md` section 5): deterministic, single-threaded, no network, no `fork`, no `exec`, no time or random values.
- It is a new design, not a port or a copy of a known tool. Its name is lower case, unique, and not the name of a known tool.
- It reports errors with messages on stderr and non-zero exit statuses.
- Write each program so that a case can reach each branch. Use one allocation helper that exits on failure. Do not write a defensive branch that no input can reach.

Build and run each program only in the container:

```sh
docker run --rm --platform linux/amd64 --network none -v "$PWD/corpus_dev/<name>":/w -w /w \
  --entrypoint /bin/sh phoenix-worker:amd64 \
  -c 'gcc -std=c11 -O0 --coverage -o /tmp/p src/*.c -lm && <run the cases> && gcov -b -c src/*.c'
```

Reach 90% of the branches before you commit a program.

Files for each program `<name>`:

- `corpus_dev/<name>/src/*.c` (and `*.h` if needed).
- `corpus_dev/<name>/holdout/gen.py`: a held-out generator with a fixed seed. It uses knowledge of the source. It writes `corpus_dev/<name>/holdout/cases.jsonl`: one JSON object for each line with the fields `args`, `stdin`, `tree` and `environment`, in the format that `phoenix_eval.corpus` reads.
- At least 100 distinct valid cases for each D0 binary and 200 for each D1 binary (`SPEC.md` section 10.6). Include error cases: bad options, missing files and malformed input.
- `corpus_dev/<name>/meta.json`: `name`, `tier`, `lines`, `files`, `category`, `features`, `heldout_cases`, `heldout_seed`.

Acceptance (step 12): `scripts/build-dev-corpus --check <name>` passes for each program, and `tools/adequacy.py <name>` meets the thresholds of `SPEC.md` section 10.6. If a program fails, fix the program or the generator. Do at most 2 rounds of fixes for each program. Then replace the program (step 12 gives the limit).

The lead reads the diff and runs the acceptance commands before the merge (AGENTS.md section 7 Delegation).

### Step 7: salvage

Restore the M1 lift and generation:

```sh
git rm -r -q phoenix/lift
git checkout 6897e47 -- phoenix/lift ghidra_scripts/ExportLift.java schemas/lift.schema.json
for f in $(git ls-tree -r --name-only 6897e47 -- phoenix/generate | grep -v '/raw\.py$'); do
  git checkout 6897e47 -- "$f"
done
for t in tests/test_lift.py tests/test_generate.py; do
  if git cat-file -e "6897e47:$t" 2>/dev/null; then git checkout 6897e47 -- "$t"; fi
done
```

Delete:

```sh
git rm -q phoenix/generate/checked_switch.py phoenix/generate/protected_switch.py \
  phoenix/generate/switch_binding.py phoenix/generate/switch_plan.py phoenix/generate/switch_source.py
git rm -q phoenix/recover/addresses.py phoenix/recover/imports.py phoenix/recover/plan.py \
  phoenix/recover/switches.py phoenix/recover/transfers.py
git rm -q ghidra_scripts/ExportMapping.java ghidra_scripts/ExportSwitchGraphs.java \
  ghidra_scripts/OrdinaryByteEvidence.java ghidra_scripts/OrdinarySwitchEvidence.java
git rm -q tests/test_checked_switch_emission.py tests/test_ordinary_switch_evidence.py \
  tests/test_protected_switch.py tests/test_recovery_switches.py tests/test_recovery_u1.py \
  tests/test_switch_artifacts.py tests/test_switch_binding.py tests/test_switch_pipeline.py \
  tests/test_switch_source.py tests/test_switch_source_generation.py tests/test_lift_evidence.py
```

A command can report that a file is already absent, because the restore replaced `phoenix/lift`. That is the expected result.

Change:

| Path | Change |
|---|---|
| `phoenix/pipeline.py` | Remove the checked-switch path: the `checked_switches` setting and each use of `plan_switches` and `read_selected_generation`. R1 rewrites this file as the stage runner. |
| `phoenix/__main__.py` | Remove `--checked-switches`. Rename the repair-escalation option and its setting, whose names contain a model name, to `--strongest-repair` and `strongest_repair`. Add `--cost-cap-usd`, passed to the per-binary budget. R1 replaces this file with `phoenix/cli.py`. |
| `.gitignore` | Remove the line `/tools/`. |

Keep without change in R0: `containers/*`; `phoenix_eval/` except the files that this plan changes or deletes; `phoenix/ingest`, `phoenix/analyze`, `phoenix/recover/__init__.py`, `phoenix/generate/raw.py`, `phoenix/repair`, `phoenix/verify`, `phoenix/package`, `phoenix/llm` (except the changes of steps 4 and 8); `scripts/build-worker`, `scripts/build-integrity`, `scripts/build-ghidra-native`; `corpus_public/`; the tests of each kept module.

Rule for tests: delete a test file that imports a deleted module. If a kept test fails only because it tests removed behavior, delete that test function and add one line to the Decision Log.

Rule for interface drift: if an import or the smoke run (step 9) fails because a restored module and a kept module disagree, take the `6897e47` version of the kept module too. Add one line to the Decision Log. The reference worktree shows the working combination:

```sh
git worktree add --detach "$PHOENIX_ROOT/worktrees/m1-reference" 6897e47
```

`phoenix_eval/m1.py`, `phoenix_eval/m2.py` and `phoenix_eval/capture_binding.py` stay until step 11 replaces them.

Checks:

- `uv run --locked python -c "import phoenix.pipeline, phoenix.__main__, phoenix_eval.__main__"` exits 0.
- `grep -rnE 'checked_switch|protected_switch|switch_plan|switch_source|switch_binding|lift\.mapping|lift\.index|lift\.evidence|recover\.(addresses|imports|plan|switches|transfers)|ExportMapping|ExportSwitchGraphs|Ordinary(Byte|Switch)Evidence' phoenix phoenix_eval tests scripts` prints nothing.
- `./scripts/check` exits 0.

### Step 8: `phoenix/config.py`

Create `phoenix/config.py` with `ROLE_MODELS: dict[str, str]`. The keys are `runtime` and `strongest`. The values are the identifiers in the "Current model" column of AGENTS.md section 6.1. Add `PRICES`, the price of each model, from the table in `phoenix_eval/model_ledger.py`. Change `phoenix/llm/provider.py` and `phoenix/pipeline.py` to use the role keys instead of the `Model` enum members that carry model names. `phoenix_eval/model_ledger.py` keeps its own table until the R1 ledger rewrite deletes it.

Check: `grep -rn -e '<runtime model id>' -e '<strongest model id>' phoenix` lists only `phoenix/config.py`.

### Step 9: smoke run of the M1 path

```sh
./scripts/build-ghidra-native
./scripts/build-images integrity amd64 && ./scripts/build-images integrity arm64
uv run --locked phoenix-eval m0 --mode apple-silicon --runs "$PHOENIX_ROOT/runs"
smoke="r0-smoke-$(uuidgen | tr '[:upper:]' '[:lower:]')"
scripts/launch-role pipeline -- uv run --locked phoenix run \
  "$PHOENIX_ROOT/runs/<m0 run id>/bitstats-original.elf" --run-id "$smoke"
uv run --locked phoenix run --replay "$smoke"
```

Expected: `phoenix-eval m0` prints the path of its report and exits 0. `phoenix run` exits 0 and prints the project path. The report shows a dev-set pass rate of 100%. `diff -r` between the project of the run and the project of the replay prints nothing. Write `$PHOENIX_ROOT/runs/r0-smoke.json` with `run_id`, `dev_pass_rate` and `replay_identical`.

### Step 9a: land the runtime model change

The working tree holds the model change of AGENTS.md section 6.1: `phoenix/config.py`, `phoenix_eval/model_ledger.py`, `tests/test_accounting.py` and `tests/test_llm.py`.

1. Verify that a `codex exec` call with each model of AGENTS.md section 6.1 returns a response at the Standard service tier.
2. Start the review of AGENTS.md section 8 for the `phoenix_eval/model_ledger.py` change.
3. Run `uv run --locked pytest -q tests/test_accounting.py tests/test_llm.py`. Expected: all pass.
4. Run `./scripts/check`. Expected: exit 0.
5. Commit the model change, its tests and `AGENTS.md` in one commit on `main`.
6. Rebuild the worker images with the command of step 6.

Check: `git status --short phoenix phoenix_eval tests AGENTS.md` prints nothing. `grep -rn -e '<runtime model id>' -e '<strongest model id>' phoenix` lists only `phoenix/config.py`.

### Step 9b: pipeline denial

Change `phoenix_eval/protection.py`. The `pipeline` profile denies each class of `SPEC.md` section 10.5:

1. The whole `<checkout>/corpus_dev` tree of each checkout, not only `src`, `holdout` and `tasks`.
2. The git object stores and history of each checkout: `<checkout>/.git` and the common git directory of each worktree.
3. `$PHOENIX_ROOT/dev_bin`, except the input copy in the pipeline run directory.
4. Earlier evaluation records: `$PHOENIX_ROOT/runs` and `$PHOENIX_ROOT/adequacy_runs`, except the current pipeline run directory (through `allow`).
5. `$PHOENIX_ROOT/sealed_work`, for the R2 staging flow.

Extend `tests/test_protection.py` with one synthetic fixture for each class: a shared case generator at the root of `corpus_dev`, a git object, a sibling binary under `dev_bin`, a held-out file and an earlier run record. Each fixture is denied in the main checkout and in a worker checkout. The input copy and the current run directory stay readable.

This is critical code. Start the review of AGENTS.md section 8.

Check: `uv run --locked pytest -q tests/test_protection.py tests/test_submission.py tests/test_submission_recovery.py tests/test_llm.py` passes. `uv run --locked phoenix-eval probe` prints only `denied=true`, and its output has a line for each new class.

### Step 9c: smoke run with the new runtime model

After Steps 9a and 9b pass, rebuild both worker images for the new evaluator
source. Build Ghidra and the integrity images and run `phoenix-eval m0` as in
Step 9. Run Phoenix on the public binary through
`phoenix_eval.submission.submit`. Use the same entry point for replay. The
evaluator copies the input and replay records into the directory that the
pipeline profile permits. Compare the projects as in Step 9.

Check: `$PHOENIX_ROOT/runs/r0-smoke.json` shows `dev_pass_rate` 1.0 and `"replay_identical": true`. The `run.json` of the run names the runtime model of AGENTS.md section 6.1. Write the run ID and the replay ID in the "Restart block".

### Step 10: `scripts/build-dev-corpus`

The corpus builds use `phoenix-worker:amd64` from step 6. It holds the pinned `linux/amd64` compilers. Check the image first:

```sh
docker image inspect --format '{{.Architecture}}' phoenix-worker:amd64
docker run --rm --platform linux/amd64 --network none --entrypoint /bin/sh phoenix-worker:amd64 \
  -c 'gcc --version && clang --version && objcopy --version && gcov --version'
```

Expected: `amd64`, then four version banners.

Write `scripts/build-dev-corpus [--check] [<program> ...]`. For each program and each build of {`gcc`, `clang`} x {`-O0`, `-O2`, `-Os`, `-O3`}, in `phoenix-worker:amd64` with `--entrypoint /bin/sh`, `--network none` and `SOURCE_DATE_EPOCH` from `tools.lock`:

1. Build `<cc> -std=c11 -<level> -o <name> src/*.c -lm`. Then run `strip --strip-all`.
2. Build the twin with the same command plus `-g`, without `strip`.
3. Compare the `.text` bytes of the two files (`objcopy -O binary --only-section=.text`). Record `twin_valid`.
4. Write the files to `$PHOENIX_ROOT/dev_bin/<name>/<compiler>-<level>/<name>` and `<name>.twin`.
5. Add an entry to `$PHOENIX_ROOT/dev_bin/manifest.json`: `name`, `tier`, `compiler`, `flags`, `sha256`, `category`, `twin_valid`.

With `--check`, also validate each held-out case with the procedure of `SPEC.md` section 10.6, through the evaluator worker. Build the true source for this validation with the canonical flags of `SPEC.md` section 7.2. Write the excluded case numbers to `corpus_dev/<name>/holdout/excluded.json`. Exit non-zero if more than 5% of the cases of a binary are excluded.

Manifest-writer guard. Change `phoenix_eval/dev_corpus.py`: `scripts/build-dev-corpus` exits non-zero before it writes `$PHOENIX_ROOT/dev_bin/manifest.json` when its checkout is not `$PHOENIX_ROOT/phoenix`. Add a test to `tests/test_dev_corpus.py` that runs it from a temporary worktree and expects the exit and an unchanged manifest.

Run `scripts/build-dev-corpus` without `--check` and without program names.

Check: `uv run --locked python -c "import json,os; m=json.load(open(os.environ['PHOENIX_ROOT']+'/dev_bin/manifest.json')); print(len(m['binaries']), sum(not b['twin_valid'] for b in m['binaries']))"` prints `176` and the count of invalid twins. `uv run --locked pytest -q tests/test_dev_corpus.py` passes.

### Step 10a: validation of each missing or stale program

From the main checkout, run one program at a time:

```sh
for p in niblace pairfold patchpanel prismcsv recordloom runepack skeinwire spanrank \
         tariffgrid tilehash tokenlace unitforge velocalc weighbit wordweft \
         branchmark chromapath driftstat fernconf gapmeter knotconf lumaquilt; do
  scripts/build-dev-corpus --check "$p" || echo "failed: $p"
done
```

1. Reuse each record that the current evaluator accepts. The Step 10 guard changed the validator fingerprint. The evaluator rejected all seven earlier records.
2. After each program, run the check command of Step 10. Expected: `176`.
3. For a failed program, start a fix round of Step 12, item 3. Continue with the next program.

Check: each of the 22 programs has `corpus_dev/<program>/holdout/excluded.json`, and `scripts/build-dev-corpus --check <program>` exited 0 for each program.

### Step 11: evaluation loop

Write `phoenix_eval/run.py` within the size limit of `docs/ROADMAP.md` section 6.5. Use `phoenix_eval/m1.py` as the reference for capture, builds, pairs and integrity. After the selection is fixed, it records each selected binary. For each binary, it:

1. Runs `scripts/launch-role pipeline -- uv run --locked phoenix run <copy of the binary> --run-id <id> --cost-cap-usd <cap>` with the cap of the tier (`SPEC.md` section 12.3), through the slots of `docs/ARCHITECTURE.md` section 14.1.
2. Captures the project with `phoenix_eval/submission.py`.
3. Builds it four ways, runs the valid held-out cases on both architectures, and runs `check_integrity`.
4. Computes `register_named_locals` and `goto_per_100_lines` with the new `phoenix_eval/quality.py`.
5. Records the result, the failure categories, the integrity sub-categories, the binary SHA-256 and the held-out hash of each binary.

It writes `$PHOENIX_ROOT/runs/<run_id>/scoreboard.json` with the fields of `docs/ROADMAP.md` section 6.2, also when the execution stops (`run_state` = `stopped`; each binary that did not complete is a failure). A field without a source in R0 is `null`. `phoenix-eval run --resume <run_id>` continues a stopped run. A retry keeps the recorded failures and cost. `phoenix-eval --replay <run_id>` repeats the evaluation with the recorded LLM responses. If the run directory is archived, it first restores the archive and verifies its SHA-256 (`docs/ARCHITECTURE.md` section 2.3).

Change `phoenix_eval/__main__.py`: replace the commands `m1` and `m2` with `run`, and add `probe` (step 4). Then delete:

```sh
git rm -q phoenix_eval/m1.py phoenix_eval/m2.py phoenix_eval/capture_binding.py \
  tests/test_m1.py tests/test_m2.py tests/test_m2_capture_binding.py \
  tests/test_m2_replay_validation.py tests/test_capture_rejection.py tests/test_evaluation_freeze.py
```

Write `scripts/loop` with the interface of `docs/ROADMAP.md` section 5. In R0, it has the loop options, `--probe` and `noise`. R2 adds `sealed-pre`, `sealed-import` and the sealed corpus mode of `phoenix_eval/run.py`, before Sealed-A run 1. `scripts/loop` refuses to run when `phoenix/` or `phoenix_eval/` has an uncommitted change, and it records `HEAD`. Thus the sequence is: commit the code, run the loop, commit the row. It samples the peak memory and the free storage after each binary. It appends one row to `docs/SCOREBOARD.md` in the format of `docs/ROADMAP.md` section 6.3, and creates the file with its header if the file does not exist. Nobody writes a row by hand.

Add run archiving to `scripts/gc` after the restore works: archive a run directory as `<run>.tar.gz`, record its SHA-256 in `$PHOENIX_ROOT/runs/archive-index.json`, restore it one time to a temporary directory and compare, and only then delete the directory. Keep the run directories of the newest 4 full-loop rows, of the noise row in force, and `runs/m1-t0-*`.

Write `scripts/gate` with the targets `R0-bootstrap`, `R0` and `--enabling <name>` only. Each later milestone adds its gate in its ExecPlan. Each target prints one line for each condition (see "Validation and Acceptance").

Write `tests/test_run.py`: a fixture project that passes, one that fails one case on ARM64 only, one with an integrity failure, a stopped run that still writes its row, and a replay that restores an archived run.

Check: `scripts/loop --probe --tier D0 --opt O0` exits 0 after Step 10a. `tail -1 docs/SCOREBOARD.md` shows a row with `loop` = `probe` and `exp` = `-`. The run selects 20 binaries (10 D0 programs x 2 compilers at `-O0`). `uv run --locked pytest -q tests/test_run.py` passes. Record the corpus and held-out hashes of the row.

### Step 11a: adequacy rules

Change `tools/adequacy.py` and `tools/adequacy_support.py` to the procedure of `SPEC.md` section 10.6:

1. Enumerate the distinct mutants. Use all if there are 300 or fewer. Otherwise sample 300 without replacement with a seed that is committed before the sampling.
2. Set each time limit to 10 times the median of three runs of the original. Count a timeout as a kill only after a repeat under the same limit confirms it and the original passes under that limit. Count an unstable result as unresolved.
3. Accept at most 20 survivor exclusions for each program, across its scored variants. Each needs a semantic proof, an independent review record and the 1,000-case search.
4. Write the raw score and the triaged score. A zero denominator fails.
5. `--summary` also checks 100 distinct valid cases for each D0 binary, 200 for each D1 binary, and the 5% exclusion cap against the complete candidate set.

Check: `uv run --locked pytest -q tests/test_adequacy.py` passes, with a test for each of items 1 to 5.

### Step 12: corpus acceptance

Merge each fix branch of the Dev Author after its acceptance (AGENTS.md section 7 Delegation). Then:

1. For each changed program, run `scripts/build-dev-corpus --check <program>` from the main checkout. Never run a full `--check`.
2. `tools/adequacy.py <program> [--seed N]` follows the procedure of `SPEC.md` section 10.6 (Step 11a). Run it in `phoenix-worker:amd64`. The selected mutator is recorded in `docs/DECISIONS.md` (a tool decision). The tool writes `corpus_dev/<program>/adequacy.json`.
3. Run it on the 22 programs. Run again each earlier report that the old tool version made. For each program below a threshold, start a fix round: a new Dev Author worker on its own branch and worktree, with the command of step 6 and these changes: `git worktree add -b dev-fix-<name> "$PHOENIX_ROOT/worktrees/dev-fix-<name>" main`, `-C "$PHOENIX_ROOT/worktrees/dev-fix-<name>"`, and the prompt `Read corpus_dev/<name>/adequacy.json. Add held-out cases or fix the program. Do not run scripts/build-dev-corpus. Commit on branch dev-fix-<name>.` Do at most 2 fix rounds for each program. Then replace the program, at most one time. If the replacement also fails after 2 rounds, write the kind of the program in `docs/LOG.md` and write a program of a different kind. Repeat items 1 and 2 for each changed program.
4. Write `corpus_dev/quick.txt` with quick set version 1 (`docs/ROADMAP.md` section 5).
5. Write `corpus_dev/accepted.json` with `corpus_hash` and `heldout_hash`. Each later row records the same two hashes. After any later change of the corpus, repeat items 1 to 5 and `scripts/loop noise` before a comparison (`docs/ROADMAP.md` section 6.1).

Check: `scripts/build-dev-corpus --check <program>` exited 0 for each of the 22 programs. `uv run --locked python tools/adequacy.py --summary` prints 22 programs at or above both thresholds. The manifest has 176 binaries.

### Step 12a: model-change quick loop

Run this step as soon as `corpus_dev/accepted.json` and `corpus_dev/quick.txt` exist. AGENTS.md section 6.1 requires one quick loop after a model change.

```sh
scripts/loop --quick --label "model change"
```

Check: one row with `loop` = `quick` and the hashes of `corpus_dev/accepted.json`.

### Step 12b: repeated probe

Compare the hashes of `corpus_dev/accepted.json` with the hashes of the Step 11 probe row. If either hash differs, run the Step 11 probe command again.

Check: a probe row with the accepted hashes and 20 selected binaries, or one `docs/LOG.md` line that says both hashes are unchanged.

### Step 13: bootstrap acceptance

```sh
scripts/gate R0-bootstrap
```

The bootstrap item has one count of 3 declared designs for the whole item (`docs/ROADMAP.md`, R0, "Rules for the bootstrap count"). A revert, a rename or a replacement never resets the count.

1. Before each design, write `attempt <n> of 3: <design>; failing check: <check>; command: scripts/gate R0-bootstrap; scope: <files>` in `docs/LOG.md`.
2. Test runs during the work are not attempts. Each declared design that fails counts one time. Write the count in the "Progress" line.
3. After the first failed design, ask the Architect one question (AGENTS.md section 6.4).
4. After the third failed design, write `R0 incomplete` in `docs/STATUS.md`, with the failing check and its evidence. Cite the Architect advice of item 3. Ask a new Architect question only if the bootstrap item has not used its one question.
5. Write one `BLOCKED ON OWNER` line in `docs/STATUS.md`: "approve a new bootstrap budget or the proposed design change".
6. Continue the independent work that needs no measurement. Never start Step 14 without a real pass of `scripts/gate R0-bootstrap`.

### Step 13a: commit the accepted corpus

Commit `corpus_dev/` (with `accepted.json` and `quick.txt`), the baseline settings and the Progress lines in one commit. Do not change `phoenix/` or `phoenix_eval/` between this commit and Step 15.

Check: `git status --short corpus_dev phoenix phoenix_eval` prints nothing.

### Step 14: experiment 1

Run this step immediately after Step 13a. Before the run, write the work-item line in `docs/LOG.md` (AGENTS.md section 9 Anti-stall rules). Declare the metric population: the D0 `-O0` cell (`docs/ROADMAP.md` section 6.1, rule 3). Do not commit the row yet.

```sh
scripts/loop --tier D0,D1 --opt O0,O2,Os --label "M1 path baseline"
```

Expected: a row with `exp` = `1/3`, `mode` = `m1`, the hashes of `corpus_dev/accepted.json`, and D0 and D1 values at each level. Create `docs/STATUS.md` in the form of AGENTS.md section 11 Measurement and status.

### Step 15: noise measurement

At the same `HEAD` as experiment 1, before any commit:

```sh
test "$(git rev-parse HEAD)" = "<commit of the experiment-1 row>"
scripts/loop noise
git add docs/SCOREBOARD.md docs/STATUS.md
git commit -m "docs: record R0 experiment 1 and noise"
```

Expected: one row with `loop` = `noise`, the commit of experiment 1 and the flips of each tier. One commit holds both rows and the status update. Later rows set `noise_ref` to this row. If the work stops between the two runs, run `scripts/loop noise` at the recorded commit of experiment 1.

### Step 16: integrity window fix

Change `phoenix_eval/integrity.py`, function `check_integrity`. Its name and signature stay the same:

1. Remove the built executables from the 64-byte window check of whole files.
2. Keep the window check of the source files and of each storage record (literals and initializers).
3. Add the window check of the non-executable data sections of each built executable: `.rodata`, `.data` and `.data.rel.ro`. Remove the ranges of the C runtime start-up symbols (`_IO_stdin_used`, `__dso_handle`, `data_start`, `__data_start`, `completed.0`, `__TMC_END__`) and the sections `.init_array` and `.fini_array`.

Add fixtures:

- `tests/test_integrity.py`, unit level with synthetic ELF files: a built `.text` that equals the original passes; a window in a built `.rodata` fails with `embedded_text`; a window in a storage record fails with `embedded_text`.
- `tests/test_compiler_integrity.py`, end to end with the pinned compilers: the original is a fixture C program built with GCC at `-O0` and stripped. The honest reconstruction is the same source with renamed functions. It passes. A cheat that holds 64 original `.text` bytes in a `static const unsigned char` array fails. A cheat that holds them in a writable array fails.

Apply the saved challenge patch: `git apply docs/plans/R0-integrity-window-fixtures.patch`. It adds `tests/test_integrity_window_challenge.py`.

Add the rescore command (`docs/ARCHITECTURE.md` section 12): `phoenix-eval rescore <run_id> --out <file>`. It runs no pipeline. It scores the captured projects and builds of the run with the integrity checker before and after the window fix. It writes, for each binary, both verdicts, and the count of binaries whose only change is the window decision. Add a case to `tests/test_run.py`.

Checks before the merge:

1. `uv run --locked pytest -q tests/test_integrity.py tests/test_compiler_integrity.py tests/test_run.py` passes.
2. `PHOENIX_COMPILER_INTEGRITY_ARCHES=amd64,arm64 uv run --locked pytest -q -rs tests/test_integrity_window_challenge.py` passes, and its output shows no skipped case. Record the image IDs and the test counts in `docs/LOG.md`.
3. Keep the window fix when the honest fixtures and the cheat fixtures pass.

Start the review with the review command of AGENTS.md section 8 Review. After the merge, rescore the experiment-1 captures, then run experiment 2:

```sh
uv run --locked phoenix-eval rescore <experiment-1 run_id> --out "$PHOENIX_ROOT/runs/r0-window-rescore.json"
scripts/loop --tier D0,D1 --opt O0,O2,Os --label "integrity window fix"
```

Compare rows 1 and 2 with the rule of `docs/ROADMAP.md` section 6.1. Report the rescore count beside the comparison. Expected: the D0 `-O0` value increases by up to the count of experiment-1 binaries whose only integrity category was `embedded_text`.

Experiment 3 is the reserve. If a defect of this item remains, use it for the fix. If D0 `-O0` stays below 80% and no defect remains, use it for a declared cold replication of the full matrix on the same code:

```sh
scripts/loop --tier D0,D1 --opt O0,O2,Os --llm-cache off --label "R0 cold replication"
```

### Step 17: mechanical gates

Write `scripts/check_gates.py`. `scripts/check` runs it after the existing commands. It checks:

1. **Stale row** (AGENTS.md section 9 Anti-stall rules, rule 3). Find the commit of the newest full-loop or quick-loop row in `docs/SCOREBOARD.md`. Let `N` be the count of commits after it, including the commit under check. Fail if `N` is above 10 and the commit under check changes a file under `phoenix/`. In the pre-commit hook, the commit under check is the staged change. In CI, it is `HEAD`.
2. **Enabling items.** `docs/plans/enabling.json` lists at most 2 active enabling items: `name`, `paths`, `acceptance` and `last_acceptance_commit`. `scripts/gate --enabling <name>` runs the acceptance command. Only when the acceptance passes, it writes the commit to `last_acceptance_commit`. For a change whose files are all inside the paths of one item, count `N` from the newer of the row commit and `last_acceptance_commit`.
3. **Code size**: the limits of `docs/ROADMAP.md` section 6.5.
4. **Status length**: `docs/STATUS.md` has 60 lines or less (AGENTS.md section 11 Measurement and status).
5. **Banned terms**: the two process terms of AGENTS.md section 8 Review, matched case-sensitively as whole words, in `README.md` and the files under `docs/`. The three report terms of AGENTS.md section 14 Writing, as whole words without case, in `docs/REPORT.md` when it exists. Keep both lists in `scripts/check_gates.py`.
6. **Program names**: no name of a `corpus_dev` program, and no string literal of 12 or more characters from `corpus_dev/*/src`, occurs in `phoenix/`.
7. **Import direction**: `phoenix_eval` never imports `phoenix`. `phoenix` never imports `tools`.
8. **Deleted modules**: reject each import, dynamic load and executable reference to a module of the deleted list of step 7 and step 11 in `phoenix/`, `phoenix_eval/`, `scripts/` and `tests/`. Permit the names in the prohibition registry of `scripts/check_gates.py` and in synthetic negative-test fixtures. Never permit a production import or a dynamic load.

Change `.github/workflows/public-tests.yml`: set `fetch-depth: 0` in each checkout step, so that the stale-row check can count commits.

Write `tests/test_check_gates.py` with a temporary git repository for gates 1 and 2, and small files for gates 3 to 8.

Check: `uv run --locked pytest -q tests/test_check_gates.py` passes. `time ./scripts/check` shows less than 5 minutes (performance requirement).

### Step 17a: gate changes

Change the `R0` target in `scripts/check_gates.py`. This is critical code (the gate decides the milestone result). Start the review of AGENTS.md section 8.

1. **Main-metric line.** When `docs/ROADMAP.md` section 7, rule 6 applies (3 experiments used and D0 `-O0` below 0.80), print `[missed] 1 main metric: R0 metric missed: success D0 O0 = <value> (gate 0.80, gap <points> points)`. Never print `[pass]` or `PASS` for that line. The last line is then `R0 gate: R0 metric missed; other conditions PASS`. Exit 0 only when each other line is `[pass]`.
2. **Condition 5.** Accept a warm time only when a priming row of the same selection, commit and image IDs comes first, each selected binary reached scoring, and the stage-cache hit count equals the count of cached stages. Otherwise the line fails.
3. **Condition 6.** Also run `PHOENIX_COMPILER_INTEGRITY_ARCHES=amd64,arm64 uv run --locked pytest -q -rs tests/test_integrity_window_challenge.py`. Fail the line if a pinned case is skipped or does not run.

Add one case to `tests/test_check_gates.py` for each of items 1 to 3: a missed metric after 3 experiments, a warm row without a priming row, and a skipped challenge case.

Check: `uv run --locked pytest -q tests/test_check_gates.py` passes.

### Step 18: gate and tag

```sh
scripts/loop --probe --tier D0 --opt O0 --label "R0 performance priming"
scripts/loop --probe --tier D0 --opt O0 --label "R0 performance"
scripts/loop --probe --quick --label "R0 quick performance priming"
scripts/loop --probe --quick --label "R0 quick performance"
scripts/gate R0
row=$(awk -F'|' '$7 ~ /^ *full *$/' docs/SCOREBOARD.md | tail -1)
git tag -a r0 -m "$row"
```

The tag message holds the final full-loop row, not a probe row (AGENTS.md section 12).

Then push as AGENTS.md section 12 Git states.

## Validation and Acceptance

`scripts/gate R0-bootstrap` prints one line for each check:

```
[pass] protection tests (main checkout and worker checkout)
[pass] phoenix-eval probe: <n> checks, each denied=true
[pass] instruction documents and protection on main
[pass] salvage: imports, reference grep, scripts/check
[pass] M1 smoke run: dev pass 1.0, replay identical
[pass] corpus: 176 binaries, held-out validation, 22 programs at the adequacy thresholds, accepted.json
[pass] evaluation loop: probe row, tests/test_run.py
R0-bootstrap: PASS
```

`scripts/gate R0` checks the conditions of `docs/ROADMAP.md`, R0, and prints one line for each:

```
[pass] 1 main metric: success D0 O0 = <value> (gate 0.80)
[pass] 2 newest full-loop row covers D0 and D1 at O0, O2, Os
[pass] 3 noise row for quick set 1
[pass] 4 scripts/check exit 0 in <minutes> min (limit 5)
[pass] 5 probe loop D0 O0 warm in <minutes> min (limit 30); probe quick loop <minutes> min (limit 20)
[pass] 6 protection and integrity tests; window challenge on amd64 and arm64, 0 skipped
[pass] 7 free <GiB> GiB (limit 15); resize record <status: dry_run_ok, ok or blocked_on_owner>
[pass] 8 source lines <n> (limit 11000); no reference to a deleted module
[pass] 9 corpus_dev 22 programs: meta, held-out validation, 8 builds, twins (<n> invalid), adequacy
R0 gate: PASS
```

Each gate exits 0 only when each line is `[pass]`. One exception: when `docs/ROADMAP.md` section 7, rule 6 applies, line 1 is `[missed] 1 main metric: R0 metric missed: ...` and the last line is `R0 gate: R0 metric missed; other conditions PASS` (Step 17a). The time limits in lines 4 and 5 are performance requirements of scripts.

Read the scoreboard row this way: `tier 0` holds D0 as `O0 a/b; O2 c/d; Os e/f`. The main metric cell states the value and the gate. `exp` shows the experiment count of 3, or `-` for a probe, quick or noise row. `data hash` shows the corpus and held-out hashes. If the budget is used and the gate fails, apply `docs/ROADMAP.md` section 7.

## Idempotence and Recovery

- `scripts/gc` is safe to run again. It deletes only the candidates of its rules. It deletes a run directory only after a verified archive exists.
- `scripts/resize-workspace --dry-run` changes nothing. The real procedure computes the size again. If the image already has that size, `hdiutil resize` changes nothing. Each exit path attaches the image and restarts Colima. If the image still does not attach, run `hdiutil attach -nobrowse -mountpoint /Volumes/PhoenixWork "/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`, then `colima start`.
- The protection tests create only temporary files. `phoenix-eval probe` reads nothing that a profile permits.
- Each salvage step is a set of git operations. To return to the state before a step, run `git checkout <start commit> -- <paths>` with the commit of step 0. The tag `archive/pre-restart` holds each deleted file. The tags `archive/branch/<name>` hold the old branch tips.
- `scripts/build-dev-corpus` writes the same bytes for the same source and `tools.lock`. Run it again after each change of a program.
- After the selection is fixed, the evaluator records each selected binary and writes a row even if the execution stops. Each binary that did not complete stays a failure in the denominator. An experiment counts one time. Resume the same run where possible. A retry never erases its failures or its cost.
- The Dev Author works on the branch `dev-corpus-1`. Each fix round works on its own branch `dev-fix-<program>`. A failed round changes nothing on `main`.
- `scripts/build-dev-corpus --check <program>` replaces only the entries of that program. A full run without program names resets the manifest. Never run a full `--check` to resume validation.

## Interfaces and Dependencies

Interfaces that this plan implements or changes:

```python
# phoenix_eval/protection.py
PROFILES: dict[str, Profile]   # "pipeline", "engineer", "dev-author", "corpus-author", "evaluator"
def guarded_command(workspace: Path, repo: Path, command: tuple[str, ...], profile: str,
                    allow: tuple[Path, ...] = ()) -> tuple[str, ...]
#   repo: the main checkout; the function also covers each registered worktree
#   allow: paths that the profile permits inside a denied class
def inherited_guard(workspace: Path) -> bool

# phoenix_eval/run.py
def evaluate(workspace: Path, run_id: str, selection: Selection, llm_cache: bool) -> Scoreboard
#   Selection: corpus, tiers, levels, quick (bool), probe (bool)
#   Scoreboard: the fields of docs/ROADMAP.md section 6.2

# phoenix_eval/quality.py
def register_named_locals(source: dict[str, bytes]) -> int      # SPEC.md section 2.5
def goto_density(source: dict[str, bytes]) -> float             # SPEC.md section 2.3

# phoenix_eval/integrity.py (name and signature unchanged, window rule changed)
def check_integrity(original: bytes, source: dict[str, bytes], executables: tuple[bytes, ...],
                    evidence: tuple[CompilerEvidence, ...], dev_outputs: frozenset[bytes],
                    origin: tuple[FunctionShape, ...]) -> IntegrityReport

# phoenix/config.py
ROLE_MODELS: dict[str, str]    # keys "runtime" and "strongest"
PRICES: dict[str, tuple[int, int, int]]
```

Command interfaces:

```
scripts/launch-role <role> -- <command...>
scripts/gc [--dry-run]
scripts/resize-workspace [--dry-run]           # the real procedure runs from memory, see step 3
scripts/build-dev-corpus [--check] [<program> ...]
phoenix-eval probe
phoenix-eval run --corpus corpus_dev --tier <tiers> --opt <levels> [--quick] [--probe] [--llm-cache on|off] --run-id <id>
phoenix-eval run --resume <run_id>
phoenix-eval --replay <run_id>
phoenix-eval rescore <run_id> --out <file>        # step 16
scripts/loop [--tier ...] [--opt ...] [--quick] [--probe] [--llm-cache on|off] [--label <text>]
scripts/loop noise                             # sealed-pre and sealed-import come in R2
scripts/gate R0-bootstrap | scripts/gate R0 | scripts/gate --enabling <name>
uv run --locked python tools/adequacy.py <program> [--seed N] | --summary
```

External tools, pinned in `tools.lock`: Python 3.12.13, uv 0.12.3, Colima 0.10.3, Lima 2.2.1, Docker CLI 29.7.2, Docker Engine 29.5.2, Buildx 0.38.2, Ubuntu 24.04 base image and package snapshot, Clang 18.1.3, GCC from the pinned snapshot (with `gcov`), QEMU 8.2.2 (oracle and coverage plugin), Ghidra 12.2 with the pinned Temurin JDK. `mull`, if step 12 selects it, gets a pin in `tools.lock` in the same commit.
