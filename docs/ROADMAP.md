# Phoenix roadmap

This document gives the milestones R0 to R7 from the current state to the v1 experiment, the recovery cycle R8 after R7, and the measurement rules for each milestone.

- `SPEC.md` gives the goal, the definitions and the commitments.
- `docs/ARCHITECTURE.md` gives the design of each deliverable.
- AGENTS.md section 9 Anti-stall rules gives the effort limits, the work-item limits and the rules for enabling items.
- AGENTS.md section 10 Milestones and ExecPlans gives the rule to write one ExecPlan for each milestone.
- AGENTS.md section 11 Measurement and status gives when to run each loop and how to report status.

If two documents conflict, apply AGENTS.md section 2 Precedence.

This roadmap has no dates and no calendar durations. Each limit is a count of experiments, attempts, rounds or dollars. A limit on machine run time (for example, "the quick loop ends in less than 20 minutes") is a performance requirement of a script. It is labeled as such. It is not a schedule limit.

---

## 1. Terms

| Term | Meaning |
|---|---|
| Experiment | One full loop on `corpus_dev` (section 5) that adds one row to `docs/SCOREBOARD.md`. A quick loop, a probe run, a noise run, a replay or a sealed run is not an experiment. |
| Experiment budget | The maximum count of experiments of a milestone. |
| Main metric | The one metric that the milestone must move. It is the first condition of the milestone gate. The budget-exhausted rule (section 7) uses it. |
| Gate | `scripts/gate R<n>`. It checks each condition of the milestone. It exits 0 and prints `R<n> gate: PASS` when all conditions are true. |
| Enabling item | Infrastructure that cannot move a success rate in the next loop. Each enabling item below has a scripted acceptance test and an intermediate metric. An acceptance attempt of an enabling item is not a full-loop row. The two-flat-rows rule of AGENTS.md section 9 Anti-stall rules does not count it. |
| Dev tiers | D0, D1, D2 and D3 (`SPEC.md` section 10.1). "Success" means the binary success rate with the `corpus_dev` held-out cases. |

---

## 2. Milestone summary

| Milestone | Main metric (the gate value is in section 3) | Experiment budget |
|---|---|---|
| R0 Reset | D0 `-O0` binary success rate | 3 |
| R1 Per-function pipeline | D1 `-O0` binary success rate | 8 |
| R2 Transplant | D1 `-O2` binary success rate | 12 |
| R3 Dev set, trace and claims | D1 `-O2` binary success rate | 10 |
| R4 Types and scale | D2 `-O2` binary success rate | 12 |
| R5 Maintainable projects | D1 maintainable rate | 8 |
| R6 Real programs and hardening | Commitment shortfall | 8 |
| R7 Frozen run and report | v1 experiment complete (`SPEC.md` section 14.1) | 1 frozen run, plus the crash reruns of `SPEC.md` section 10.7 |
| R8 Recovery cycle n (after R7, repeatable) | Commitment shortfall | 8 for each cycle, plus 1 frozen run |

The **commitment shortfall** is the largest value, over the D0, D1 and D2 cells at `-O0`, `-O2` and `-Os`, of (commitment value of the matching sealed tier in `SPEC.md` section 4.1 minus the dev success rate), in points. A value below zero counts as zero. The shortfall covers only the section 4.1 cells. The gates of R6 and R8 check the section 4.2 and 4.3 commitments separately.

Each milestone runs in this sequence. Start a milestone only after the previous gate passed or the budget-exhausted rule (section 7) moved the work forward.

---

## 3. Milestones

### R0 Reset

**Goal.** An honest and fast measurement loop, the first measured rows, and protected hidden data. The first measured row comes before any new subsystem.

**Deliverables**, in this sequence (`docs/plans/R0-reset.md` gives the steps):

1. Workspace storage cleanup, `scripts/gc`, and one test of the resize procedure.
2. The protected path list, the role profiles, the protection test and `phoenix-eval probe`.
3. The salvage of the repository: keep, change and delete lists.
4. The M1 path runs end to end.
5. `phoenix_eval/run.py`, `scripts/loop`, `scoreboard.json` and `docs/SCOREBOARD.md`.
6. `corpus_dev` batch 1 from the Dev Author, in parallel from deliverable 2: 10 D0 programs and 12 D1 programs, with held-out sets and twins. The corpus is accepted with the held-out validation and the adequacy pilot (`SPEC.md` section 10.6), with each added case and each replacement, before deliverable 8.
7. The acceptance of the R0 bootstrap item (deliverables 2 to 6).
8. The first full-loop row of the M1 path: D0 and D1 at `-O0`, `-O2` and `-Os`, immediately after deliverable 7.
9. The noise measurement (section 6.1), on the commit of the first full-loop row.
10. The integrity window fix with its fixtures (`SPEC.md` section 9, rule 1).
11. The mechanical gates of `scripts/check`.

**Enabling item.** R0 has one bootstrap enabling item. It counts as one enabling item.

| Item | Acceptance test | Intermediate metric |
|---|---|---|
| R0 bootstrap: protection profiles, salvage, the corpus build, `corpus_dev` batch 1 with held-out validation and adequacy, and the evaluation loop | `scripts/gate R0-bootstrap` exits 0. Limit: 3 acceptance attempts. | bootstrap checks passed |

Experiment 1 runs immediately after the bootstrap acceptance.

**Gate** (`scripts/gate R0`):

1. Main metric: in the newest full-loop row, the D0 `-O0` binary success rate is 80% or more.
2. The newest full-loop row covers D0 and D1 at `-O0`, `-O2` and `-Os`.
3. A noise row exists for quick set version 1.
4. `scripts/check` exits 0. Performance requirement: it ends in less than 5 minutes.
5. `scripts/loop --probe --tier D0 --opt O0` with a warm cache exits 0. Performance requirement: it ends in less than 30 minutes. `scripts/loop --probe --quick` with a warm cache ends in less than 20 minutes (performance requirement).
6. `uv run --locked pytest -q tests/test_protection.py tests/test_integrity.py` passes. It includes the honest fixture where machine code from the same compiler equals the original, and the cheat fixtures.
7. The workspace image has 15 GiB or more free. `$PHOENIX_ROOT/runs/r0-resize.json` exists with the status `ok` or `blocked_on_owner`.
8. The pipeline and evaluator source has fewer than 9,000 lines. No file refers to a deleted module.
9. `corpus_dev` has 22 programs. Each has `meta.json`, a validated held-out set, 8 builds with twins, and an `adequacy.json` that meets the thresholds of `SPEC.md` section 10.6. The gate reports the count of invalid twins.

**The next milestone needs:** the M1-path rows as the baseline, the noise threshold, the accepted batch 1 and the protection profiles.

### R1 Per-function pipeline

**Goal.** Remove the whole-program prompt limit and the integrity conflicts with readable code. Draft each function separately. Check each draft by compilation and by the whole-program dev set (`compile_only` mode).

**Deliverables**, in this sequence:

1. Evaluator compatibility (the "R1 (first)" rows of `docs/ARCHITECTURE.md` section 12), with fixtures.
2. The minimal KB (`docs/ARCHITECTURE.md` section 4.2) with the JSON export.
3. The stage runner: `pipeline.py`, `cli.py`, checkpoints, resume and replay (`docs/ARCHITECTURE.md` section 2.3).
4. The target forms of `ingest` and `lift`.
5. Dev-set steps 1 to 3 (CLI surface, seeds, coverage loop) with edge coverage.
6. Static signatures, the data model and the data emitter (N3) with the byte check, and the import table with the arithmetic helpers (N10).
7. Per-function drafts in `compile_only` mode, with literal mode and region drafting.
8. The repair decision table, rows 1, 4, 5 and 6.
9. The rewritten LLM ledger, and the R1 metrics of `phoenix_eval/quality.py`.
10. Platform capabilities, the Linux protection profile, and the CI replay job (`docs/ARCHITECTURE.md` section 13).

In parallel, a worker builds the R2 enabling item: `tools/truth.py`, the truth-transplant harness, the thunk fixture suite and the tracer image.

**Enabling items.**

| Item | Acceptance test | Intermediate metric |
|---|---|---|
| Evaluator compatibility | `uv run --locked pytest -q tests/test_integrity.py tests/test_submission.py tests/test_compiler_integrity.py`: cheat suite 100% rejected, honest suite 100% accepted, end-to-end fixtures with multiple source files, helpers, structures, pointer initializers and indirect calls pass | fixture pass rate |
| KB and stage runner | `uv run --locked pytest -q tests/test_replay.py`: a replay from an empty run directory, with one interrupted stage, gives a byte-identical project | replay identity |
| Truth-transplant harness (worker) | `uv run --locked pytest -q tests/transplant/` runs the thunk fixture suite | fixture pass rate, truth transplant rate |

**Gate** (`scripts/gate R1`):

1. Main metric: the D1 `-O0` binary success rate is 50% or more.
2. The D0 binary success rate is 85% or more at each of `-O0`, `-O2` and `-Os`.
3. `integrity_failures` is 0 in the newest full-loop row.
4. The evaluator compatibility acceptance test passes.
5. The replay acceptance test passes.
6. The large-function fixture (a function with more than 24 KB of assembly text) ends with the status `compile_only` or later, or with `draft_failed` and the reason `too_large`. No binary fails because of the prompt size.
7. The byte check (`docs/ARCHITECTURE.md` section 8.4) passes for each emitted object of each `corpus_dev` binary.
8. `glibc_internal_symbols` is 0. `uv run --locked pytest -q tests/test_arith_helpers.py` passes on both architectures.
9. The CI replay job passes on both native runners.

**The next milestone needs:** a `compile_only` row on D1 `-O2` as the comparison for N1, the KB, the dev set with edge coverage, and the truth-transplant harness.

### R2 Transplant

**Goal.** Check each function inside the running original.

**Deliverables:**

1. Instrumentation mode (`docs/ARCHITECTURE.md` section 6.2).
2. The shim, the thunk, the binding, `transplant.check` and `transplant.theseus` (N1, N2).
3. The draft loop with transplant feedback, and repair decision table rows 2 and 3.
4. Negative transplants and the 30 injected faults of N2.
5. Sealed-A run 1 on T0 and T1 (section 6.4).
6. The R7 budget reservation (section 8), recorded as one line in `docs/LOG.md`.

The Dev Author writes `corpus_dev` batch 2 in parallel: 8 D2 programs with held-out sets and twins.

**Enabling item.**

| Item | Acceptance test | Intermediate metric |
|---|---|---|
| Instrumentation mode and thunk (the N1 mechanism) | `uv run --locked pytest -q tests/transplant/`: 100% of the thunk fixtures pass. Limit: 3 acceptance attempts (the kill criterion of N1). | truth transplant rate |
| ELF-copy pivot (only if the N1 pivot condition is true) | the same acceptance test on patched ELF copies. Limit: 3 acceptance attempts. | truth transplant rate |

**Gate** (`scripts/gate R2`):

1. Main metric: the D1 `-O2` binary success rate is 60% or more.
2. The D1 `-O0` binary success rate is 80% or more.
3. 100% of the thunk fixtures pass.
4. The truth transplant rate is 95% or more at `-O0`, and 85% or more at `-O2` and `-Os`, on D0 and D1. The transformed-interface truth rate is reported.
5. First-suspect accuracy on the injected faults is 70% or more. The negative transplant detection rate is 90% or more.
6. The median Theseus fraction on D1 `-O2` is 0.85 or more.
7. The scoreboard has the Sealed-A run 1 row. This row has no threshold.

If N1 is killed, apply its fallback (`docs/ARCHITECTURE.md` section 15.2). Conditions 3 to 6 then do not apply. Conditions 1, 2 and 7 stay.

**The next milestone needs:** the `transplant` mode (or its fallback), the Theseus metric, the first Sealed-A numbers and batch 2.

### R3 Dev set, trace and claims

**Goal.** Make the dev set reach the behavior that the hidden tests reach, and use values from the original in recovery and repair.

**Deliverables:**

1. Dev-set step 4: LLM generators (N4).
2. The `funcio` and `libc` tracer, and its use in signatures and draft context (N5).
3. Claims and their resolution (`docs/ARCHITECTURE.md` section 4.3).
4. Trace-guided fault localization (N7).
5. The ARM64 sanitizer check (N11).
6. Batch 2 (D2) in the full loop. Quick set version 2 and a new noise row.
7. The N8 start decision: the share of `corpus_dev` held-out failures that `static_only` functions cause.

**Enabling items.**

| Item | Acceptance test | Intermediate metric |
|---|---|---|
| Tracer with `funcio` | `scripts/build-tracer` passes its plugin-interface check, and `uv run --locked pytest -q tests/test_trace.py` passes | share of reached functions with `obs_funcio` rows |
| Claims | `uv run --locked pytest -q tests/test_claims.py`: resolution, invalidation and the reversal of a refutation | KB digest identity on replay |

**Gate** (`scripts/gate R3`):

1. Main metric: the D1 `-O2` binary success rate is 75% or more.
2. The D1 `-Os` binary success rate is 75% or more.
3. The D2 `-O0` binary success rate is 40% or more.
4. The median `dev_edge_coverage` is 90% or more on D1 and 80% or more on D2.
5. The escape rate is 10% or less on D1.
6. The N8 start decision is recorded in `docs/LOG.md`.

If the escape rate on D1 is above 15% at the end of R3, start the N4 pivot (section 9).

**The next milestone needs:** D2 programs in the loop, trace observations and claims.

### R4 Types and scale

**Goal.** Recover whole-program types, and make large binaries complete within the cost caps.

**Deliverables:**

1. Heap shape tracing and struct unification (N9).
2. Parallel drafting for binaries with 300 functions or more, through the global concurrency budget.
3. Cost controls: per-stage cost records and the repair stop rule of `docs/ARCHITECTURE.md` section 5.7, and the cost cap of each stage.
4. N8, if its start condition is true.
5. Sealed-A run 2 on T0, T1 and T2.
6. The updated R7 budget reservation.

**Enabling item.**

| Item | Acceptance test | Intermediate metric |
|---|---|---|
| Heap tracing | `uv run --locked pytest -q tests/test_heap_trace.py` passes | share of true struct fields with an `obs_heap` row |

**Gate** (`scripts/gate R4`):

1. Main metric: the D2 `-O2` binary success rate is 50% or more.
2. The D2 `-O0` binary success rate is 65% or more.
3. Struct field accuracy is 60% or more on D2.
4. The non-default type share is 70% or more on D1.
5. One D2 binary completes a cold pipeline run with the default `PHOENIX_JOBS` in less than 60 machine minutes (performance requirement).
6. The scoreboard has the Sealed-A run 2 row.

**The next milestone needs:** recovered types for `polish`, and cost records for each stage.

### R5 Maintainable projects

**Goal.** Make each successful project as easy to change as the original source.

**Deliverables:**

1. The `polish` stage (`docs/ARCHITECTURE.md` section 5.8).
2. The edit-task harness (N12).
3. 3 edit tasks for each D1 and D2 program (60 tasks) from the Dev Author.
4. The maintainability conditions in the scoreboard (`SPEC.md` section 2.2).

**Gate** (`scripts/gate R5`):

1. Main metric: the D1 maintainable rate is 60% or more.
2. The D2 maintainable rate is 35% or more.
3. No binary success cell decreases after `polish`. Compare the rows before and after `polish` with the comparison rule (section 6.1).
4. The literal-mode byte share is 10% or less in the fully successful projects.
5. The edit-task parity over the fully successful D1 and D2 programs is 0.70 or more.
6. The isolation test of the edit-task harness passes.

**The next milestone needs:** the maintainability numbers on `corpus_dev`, and the harness for Sealed-B.

### R6 Real programs and hardening

**Goal.** Reach the commitment values on `corpus_dev`, and prepare the frozen run.

**Deliverables:**

1. D3: 4 or more real programs first published after the training cutoff, with visible source, not in a sealed set.
2. Fixes for the top 3 failure categories.
3. Tuning of the execution budgets and the effort table.
4. `-O3` in the full loop.
5. Sealed-A run 3 on all tiers.
6. The updated R7 budget reservation.
7. Sealed-B from the Corpus Author, with its commitments and its adequacy aggregates.

**Gate** (`scripts/gate R6`):

1. Main metric: the commitment shortfall is 0 points. For this metric, a gain is a decrease of the shortfall on the same binaries (section 6.1, rule 7).
2. The D1 and D2 maintainable rates reach the T1 and T2 values of `SPEC.md` section 4.2.
3. The edit-task parity over the fully successful D1 and D2 programs reaches the value of `SPEC.md` section 4.2.
4. The ARM gap of each of D0, D1 and D2 is at or below the value of `SPEC.md` section 4.3.
5. The confidence byte share and the glibc-internal symbol count reach the values of `SPEC.md` section 4.3.
6. The median cost per binary of D1 and of D2 is at or below the T1 and T2 values of `SPEC.md` section 4.3.
7. One D3 program is fully successful.
8. `phoenix-eval --replay` reproduces 3 sampled binaries byte for byte.
9. The scoreboard has the Sealed-A run 3 row.
10. Sealed-B is sealed: its hash commitments are in `docs/corpus_commitments.md`, and its adequacy aggregates meet `SPEC.md` section 10.6.

**The next milestone needs:** a tagged commit that passes this gate, and the final R7 budget.

### R7 Frozen run and report

**Goal.** The v1 experiment (`SPEC.md` section 14.1).

**Deliverables:**

1. The tag `v1-freeze` and its preregistration row (section 6.4).
2. One cold run on Sealed-B with the baselines and the ablations (`SPEC.md` section 11), in the cell order of section 8.
3. A replay of each binary with `phoenix-eval --replay`.
4. `docs/REPORT.md` (`SPEC.md` section 12).
5. The publication of the source archives, the held-out sets and the edit tasks, with verified hashes.

**Gate** (`scripts/gate R7`):

1. Each headline number reproduces with `phoenix-eval --replay`.
2. The hashes of the published archives equal `docs/corpus_commitments.md`.
3. `docs/REPORT.md` follows `SPEC.md` section 12, and `scripts/check` passes on it.

When the gate passes, the v1 experiment is complete. The v1 goal is met only under `SPEC.md` section 14.2. If the frozen run misses a commitment, publish the partial result (`SPEC.md` section 14.2) and start R8 Recovery cycle 1.

### R8 Recovery cycle n (after R7, repeatable)

Start cycle 1 when the R7 gate passed and the v1 goal is not met. Start cycle n + 1 when cycle n ends and the v1 goal is still not met.

**Goal.** Reach each commitment that the last frozen run missed, and measure it again on a new sealed set. Earlier results are never replaced or deleted.

**Deliverables:**

1. Fixes for the unmet commitments, measured on `corpus_dev`.
2. A new sealed set from a new Corpus Author session, with the rules of `SPEC.md` sections 10.3, 10.4 and 10.6: Sealed-C in cycle 1, Sealed-D in cycle 2, and so on. It has new paths, for example `$PHOENIX_ROOT/sealed_c` and `$PHOENIX_ROOT/holdout_c`. Add these paths to the protected path list before the Corpus Author starts. The new set contains no program of an earlier sealed set.
3. A new freeze tag (`v1-freeze-c` for Sealed-C, and so on) and its preregistration row (section 6.4).
4. One cold frozen run on the new set with the baselines and the ablations, with R7 deliverables 3 to 5 for this set. `docs/REPORT.md` gets a new section for the cycle.

**Gate** (`scripts/gate R8`), before the frozen run:

1. Main metric: the commitment shortfall is 0 points.
2. Each commitment that the last frozen run missed reaches its value on `corpus_dev`.
3. Each condition of the R6 gate passes again, with the new sealed set in condition 10.

After the gate, the frozen run on the new set follows the R7 gate. If that run reaches each commitment, the v1 goal is met (`SPEC.md` section 14.2). Otherwise, start the next cycle.

---

## 4. Parallel work

These items run in parallel and do not block the lead model. AGENTS.md section 6 Models, roles and reasoning effort defines the roles. AGENTS.md section 7 Delegation gives the rules.

| Work | Role | Starts | Ends at |
|---|---|---|---|
| `corpus_dev` batch 1 (10 D0, 12 D1) | Dev Author | R0, after the protection change is on `main` | the R0 bootstrap acceptance |
| Sealed-A adequacy check with `tools/adequacy.py`; new versioned held-out archives where needed | Corpus Author | R0, after the adequacy pilot | before Sealed-A run 1 |
| `tools/truth.py`, truth-transplant harness, thunk fixtures, tracer image | worker | R1 | R2 start |
| Challenge suite of the integrity checker | Reviewer | R1 | grows each time a new cheat form is found |
| `corpus_dev` batch 2 (8 D2) | Dev Author | R2 | R3 start |
| Sealed-B (programs, held-out sets, edit tasks) | Corpus Author | R3 start | R6 gate |
| 60 dev edit tasks | Dev Author | R4 | R5 |
| D3 programs | Dev Author | R5 | R6 |

---

## 5. The dev loop

```
scripts/loop [--tier D0,D1,D2,D3] [--opt O0,O2,Os,O3] [--quick] [--probe] [--llm-cache on|off] [--label <text>]
scripts/loop noise
scripts/loop sealed-pre --corpus <set> --tag <tag> --cells <list> --budget-usd <amount>
scripts/loop sealed-import <run_id>
```

`scripts/loop` does these steps:

1. Select the binaries from `$PHOENIX_ROOT/dev_bin/manifest.json`, or from `corpus_dev/quick.txt` with `--quick`. The selection is then fixed.
2. Run `phoenix-eval run --corpus corpus_dev` on them. The evaluator runs `phoenix run` under the `pipeline` profile for each binary, through the global concurrency budget, then scores the project with the `corpus_dev` held-out cases.
3. Write `$PHOENIX_ROOT/runs/<run_id>/scoreboard.json`. Add one row to `docs/SCOREBOARD.md`.

`scripts/loop` and its subcommands are the only writers of `docs/SCOREBOARD.md`. Nobody writes a row by hand.

- `scripts/loop noise` runs the quick loop two times with `--llm-cache off` and writes one noise row that aggregates the two runs (section 6.1).
- `scripts/loop sealed-pre` writes the preregistration row of a sealed run (section 6.4).
- `scripts/loop sealed-import <run_id>` imports the aggregate scoreboard that `phoenix-eval` exported for a sealed run, and writes its row.
- `--probe` writes a row with `loop` = `probe` and `experiment` = `null`. Use it for smoke runs, acceptance runs and performance runs.

Failed and stopped loops:

- After the selection is fixed, the evaluator records each selected binary. If the execution stops, it still writes the row. Each binary that did not complete is a failure in the denominator.
- An experiment counts one time, also when it stops.
- Resume the same run where possible (`phoenix-eval run --resume <run_id>`). A retry never erases recorded failures or recorded cost.

Loop kinds:

| Kind | Command | Binaries | Experiment |
|---|---|---|---|
| Full loop | `scripts/loop` with the tiers and levels of the current milestone | all `corpus_dev` binaries of these tiers and levels | yes |
| Quick loop | `scripts/loop --quick` | the quick set | no |
| Probe run | `scripts/loop --probe ...` | as selected | no |
| Noise run | `scripts/loop noise` (two quick runs, one row) | the quick set | no |
| Replay | `phoenix-eval --replay <run_id>` | the binaries of an earlier run | no |
| Sealed run | `phoenix-eval run --corpus sealed-a` or `--corpus sealed-b`, from a tagged commit, then `scripts/loop sealed-import` | the sealed release | no |

The full-loop levels are `-O0`, `-O2` and `-Os`. R6 adds `-O3`.

The quick set:

- Version 1 (R0): 12 binaries. For each of D0 and D1, for each of `-O0`, `-O2` and `-Os`, and for each compiler, take the binary with the lowest SHA-256.
- Version 2 (R3): 18 binaries, with the same rule for D0, D1 and D2.
- Each new version needs a new noise row.
- After each change of the corpus (a program, a build or a held-out case), rebuild the quick set and run `scripts/loop noise` again before any comparison.

Performance requirements: the quick loop with a warm cache ends in less than 20 minutes. `scripts/loop --probe --tier D0 --opt O0` with a warm cache ends in less than 30 minutes. The quick loop never runs Ghidra or rebuilds a dev set when neither the binary nor the stage version changed.

---

## 6. Measurement rules

### 6.1 Comparison and noise

1. **Noise measurement.** `scripts/loop noise` runs the quick loop two times on one commit with `--llm-cache off`. For each cell, the flips are the binaries whose fully successful result differs between the two runs. The flip rate of a cell is flips divided by the binaries of the cell. Measure the noise again when the runtime model, an effort setting, the quick set or the corpus changes.
2. **Same binaries.** Compare two rows only on the binaries that both rows contain with the same binary SHA-256 and the same held-out hash.
3. **Threshold.** The threshold `T` of a comparison is the sum over cells of (flip rate of the cell x compared binaries of the cell), rounded up. For a cell without a measured flip rate, use the largest measured flip rate.
4. **Decision.** Let `d` be the count of fully successful binaries in the new row minus the count in the old row, on the compared binaries.
   - If `d > T`, the new row is a gain.
   - If `d < -T`, the new row is a loss.
   - Otherwise, the result is a tie in the success metric. Report a change in held-out cases passed separately. Such a change is not a gain for the 3-experiment rule, the two-flat-rows rule or a budget extension.
5. **Other metrics.** Apply the same rule to the maintainable counts. For each other metric, compare the values on the same binaries directly.
6. **Replays.** A cached replay is deterministic. Use cached replays for regression checks. A replay of an earlier run must reproduce its success numbers exactly.
7. **Commitment shortfall** (R6, R8). A gain is a decrease of the shortfall on the same binaries. The success count of the cell that set the old shortfall must also rise by more than the threshold of that cell.

### 6.2 Scoreboard fields

`phoenix-eval` writes one `scoreboard.json` object for each run. Lines are non-blank lines.

| Field | Content |
|---|---|
| `row` | Sequence number of the row in `docs/SCOREBOARD.md` |
| `run_id`, `commit`, `tag` | The run, the full commit hash, the tag (sealed runs only) |
| `corpus` | `corpus_dev`, `sealed_a` or `sealed_b` |
| `loop` | `full`, `quick`, `probe`, `noise`, `replay`, `sealed` or `sealed-pre` |
| `run_state` | `complete`, or `stopped` when the execution stopped before each binary completed |
| `corpus_hash`, `heldout_hash` | SHA-256 of the binary manifest of the run, and SHA-256 of the held-out cases of the selected binaries |
| `cache` | `warm` or `cold` |
| `milestone`, `experiment` | For example `R1` and `[3, 8]`; `experiment` is `null` for a row that is not an experiment |
| `quick_set`, `noise_ref` | The quick set version; the row of the noise measurement in force |
| `mode` | `m1`, `compile_only` or `transplant` |
| `models` | The model identifier of each role used |
| `success` | Binary success for each tier and level, as `[n, N]` |
| `program_success`, `maintainable` | For each tier, as `[n, N]` |
| `held_out_cases` | `[passed, total]` |
| `failure_categories` | Count for each category of `SPEC.md` section 10.7 |
| `integrity_failures`, `glibc_internal_symbols`, `register_named_locals` | Counts |
| `arm_gap_points` | For each tier |
| `dev_edge_coverage_median`, `function_reachability_median` | For each tier |
| `escape_rate` | For each tier, as `[n, N]` (`corpus_dev` only) |
| `truth_transplant_rate`, `transformed_interface_rate` | For each level, as `[n, N]` |
| `theseus_fraction_median` | For each tier (`transplant` mode) |
| `function_status` | Count for each status |
| `literal_mode_byte_share`, `nondefault_type_share` | For each tier, over the fully successful projects |
| `goto_per_100_lines` | For each tier, the median over projects |
| `edit_task` | For each tier: parity over all programs, parity over fully successful programs, pass rate of each arm |
| `cost_usd`, `binary_minutes` | For each tier: median, first quartile, third quartile |
| `loop_minutes`, `peak_memory_gib`, `peak_storage_gib`, `free_storage_gib` | Machine minutes of the loop; resource peaks; free space after the loop |
| `source_lines`, `test_lines` | Lines of `phoenix/**/*.py` and `phoenix_eval/**/*.py`; lines of `tests/**/*.py` |
| `noise` | For each tier and level, `[flips, N]` (noise rows only) |
| `dev_set_hashes`, `binaries` | For each binary: SHA-256, held-out hash, dev-set hash, tier, level, compiler, result, categories (`corpus_dev` only) |

A sealed row holds only aggregate fields. It never holds `dev_set_hashes`, `binaries` or `escape_rate`.

### 6.3 Row format of `docs/SCOREBOARD.md`

The file starts with this header. Each run adds one row.

```
| row | run_id | commit | corpus | data hash | loop | cache | milestone | exp | main metric | tier 0 | tier 1 | tier 2 | tier 3 | maintainable | held-out passed | integrity | edge cov | escape | literal % | goto/100 | cost median | free GiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

Cell rules:

- `commit`: the first 12 characters of the hash.
- `data hash`: the first 8 characters of `corpus_hash` and of `heldout_hash`, as `<corpus>/<held-out>`.
- `exp`: `n/budget`, or `-` for a row that is not an experiment.
- `main metric`: `<metric> = <value> (gate <value>)`.
- `tier 0` to `tier 3`: D0 to D3 for `corpus_dev`, T0 to T3 for a sealed set. Format: `O0 a/b; O2 c/d; Os e/f`, and `; O3 g/h` when `-O3` ran. A noise row gives the flips in the same format.
- `maintainable`: `1: a/b; 2: c/d` for tiers 1 and 2.
- `edge cov`, `escape` and `cost median`: one value for each tier that ran, as `D1 88; D2 79`.
- `literal %` and `goto/100`: one value over all tiers.
- A cell that does not apply holds `-`.

### 6.4 Sealed runs

1. Tag the commit. Run `scripts/loop sealed-pre`. It writes the preregistration row: `loop` is `sealed-pre`, `run_id` is the planned run, `commit` is the tagged commit, and `main metric` is `tag <tag>; cells <list>; budget $<amount>`. Commit this row before the run starts.
2. Run the evaluation cold. It writes only to `$PHOENIX_ROOT/sealed_runs/<run_id>/`. `phoenix-eval` exports the aggregate scoreboard of the run to `$PHOENIX_ROOT/runs/<run_id>/scoreboard.json`.
3. Run `scripts/loop sealed-import <run_id>`. It writes the result row. The lead model never copies a file from a sealed directory and never lists one.
4. Run a sealed evaluation only on a host whose oracle is `dual` (`docs/ARCHITECTURE.md` section 13).
5. Sealed-A runs: run 1 in R2 (T0, T1), run 2 in R4 (T0, T1, T2), run 3 in R6 (all tiers). `SPEC.md` section 10.2 limits the count to three.

### 6.5 Code size limits

`scripts/check` enforces these limits. AGENTS.md section 9 Anti-stall rules gives the rule for a large change.

| Scope | Limit |
|---|---|
| `source_lines` (non-blank lines of `phoenix/**/*.py` and `phoenix_eval/**/*.py`) | below 15,000 until v1 |
| `phoenix/cli.py` | 80 lines |
| `phoenix/pipeline.py` | 200 lines |
| `phoenix/llm/ledger.py` | 250 lines |
| `phoenix_eval/run.py` | 250 lines |
| The import table in `phoenix/lift/imports.py` | 200 lines |

The R0 gate has its own salvage limit (R0, condition 8). Test lines have no limit. AGENTS.md section 13 Code and test quality gives the test rules.

---

## 7. Budget-exhausted rule

When the experiment budget of a milestone is used and the gate did not pass:

1. If the last experiment was a gain in the main metric (section 6.1), run at most 1 extra experiment. This is the only extension of a budget.
2. If the main metric is then within 10 points of its gate value, continue to the next milestone. Record the gap in `docs/STATUS.md`. The gap becomes work item 1 of the next milestone, with a limit of 2 experiments.
3. If the gap is larger, apply the kill criterion and the fallback of the technique that failed (`docs/ARCHITECTURE.md` section 15), or the pivot in section 9. Then continue to the next milestone.
4. A failed gate condition other than the main metric becomes a work item of the next milestone. An enabling item follows AGENTS.md section 9 Anti-stall rules.
5. Never lower a gate value, a commitment or the definition of success. The R6 gate still requires each commitment value. Never stop to wait for a person (AGENTS.md section 3 Autonomy).

---

## 8. LLM budget

### 8.1 Caps and the frozen-run budget

- Each pipeline run has the cost cap of its tier (`SPEC.md` section 12.3). The cap is a safety limit.
- The frozen-run budget is 1.5 x the sum over tiers of (median cost per binary of the tier in the last Sealed-A run x the count of Sealed-B binaries of the tier), plus the baselines and the ablations computed the same way.
- For a tier without a measured median, use the cost cap of the tier as the median.
- Compute and record the R7 reservation at R2. Update it at R4 and at R6.
- Reference value: the M1 pipeline cost about $1.60 for 20 sealed T0 binaries.

### 8.2 Reduction sequence

Apply these steps in sequence when the LLM budget decreases (a notice from the owner, or usage-limit errors that stop 3 runs in sequence):

1. Keep the caches. Lower the effort of draft attempt 1 by one step.
2. Run full loops only for the tiers and levels in the current gate. Use quick loops for the other cells.
3. Do not run `-O3` before R7.
4. Run the frozen run cells in this priority: T1 `-O2`, T2 `-O2`, the edit tasks of T1 and T2, T0 at all levels, T3, T1 `-O0` and `-Os`, T2 `-O0` and `-Os`, the baselines, the ablations, `-O3`.
5. Never skip `polish`. Reduce the matrix breadth instead.
6. Never lower a commitment. A cell that did not run is "not run" in the report. Its commitment is "not measured", and the v1 goal is not met (`SPEC.md` section 14.2).

---

## 9. Risks, kill criteria and pivots

| Risk | Signal | Action |
|---|---|---|
| Code patching fails under QEMU user mode | Truth transplant rate below 50% at `-O0` after the 3 acceptance attempts of the R2 mechanism item | The ELF-copy pivot of N1 (`docs/ARCHITECTURE.md` section 15.2), a separate enabling item. Limit: 3 acceptance attempts. |
| Transplant fails at `-O2` | The kill criterion of N1 | The fallback of N1 (`compile_only` mode). No target changes. |
| The dev set misses behavior that the hidden tests reach | Escape rate above 15% on D1 at the end of R3 | The N4 pivot: AFL++ in QEMU mode as a second generator (limit: 3 experiments, image below 1.5 GiB). Start N8. |
| Large optimized functions fail | `draft_failed` with the reason `too_large` causes more than 20% of the failures | Halve the region size limit for one experiment. If the share stays above 20%, record X2 for after v1. |
| ARM64-only failures | ARM gap above 3 points | Find the root cause of each ARM64-only failure on `corpus_dev`. Add a rule to `docs/ARCHITECTURE.md` section 10 or to the lint. |
| Floating-point output differs between architectures | `behavior_arm_only` on numeric programs | Keep `-ffp-contract=off`. Check the `libm` calls that differ. If a result needs x87 precision, record a known divergence. Add no normalization. |
| The tracer interface is missing | The plugin-interface check of `scripts/build-tracer` fails | Kill N5. There is no `gdbstub` fallback. |
| The model reproduces memorized code | A T3 program with an earlier public ancestor | The ancestor rule of `SPEC.md` section 10.4. |
| Weak hidden tests | Adequacy below `SPEC.md` section 10.6 | The author of the corpus adds cases before the run. |
| A gamed metric | The challenge suite finds a new cheat form | Add the form to the suite. Fix the checker with the review of AGENTS.md section 8 Review. |
| A critical change has no review | The Reviewer is not available | The change stays on its branch (AGENTS.md section 8 Review). Other work continues. |
| The LLM budget decreases | A notice from the owner, or usage-limit errors that stop 3 runs in sequence | Section 8.2. |
| Storage ends | Less than 10 GiB free in the workspace image | Run `scripts/gc`. If less than 10 GiB is still free, run `scripts/resize-workspace` (at most 100 GiB, and only if the external drive keeps 20 GiB free). If neither works, record the item as blocked on the owner (AGENTS.md section 3 Autonomy). Keep each evaluation run below 2 GiB. The design limit is the actual size of the image. |
| The provider refuses binary-analysis prompts | Refusal responses | The refusal rule of `docs/ARCHITECTURE.md` section 11. |
| Emulators differ from real hardware | CI differences on `corpus_dev` | Exclude and count the case. Find the cause in the runner. |
| A single-runner host | `capabilities().oracle` is `single_runner` | Record `single_runner` in the dev set and the report. Run no sealed evaluation on this host. |
| Overfit to `corpus_dev` | The overfit alarm of `SPEC.md` section 10.7 | The action of `SPEC.md` section 10.7, item 5. |
| The engineers stall | The signals of AGENTS.md section 9 Anti-stall rules | The actions of AGENTS.md section 9 Anti-stall rules. |

---

## 10. Ladder after v1

Do not start a ladder item before the v1 goal is met (`SPEC.md` section 14.2).

| Step | Capability |
|---|---|
| L1 | External comparison on the coreutils set. `-O3` and link-time optimization as commitments. ARM64 inputs as a commitment (a port of the shim and the thunk). Tier T4: real programs of 25,000 to 100,000 lines. |
| L2 | Static binaries (libc identification), threads, signals. |
| L3 | C++ inputs (virtual tables, exceptions). Rust as an output language. Symbolic proof for selected functions (X3). |
| L4 | Shared libraries with ABI-compatible reconstructions. Servers with protocol-level differential tests. |
| L5 | Windows PE and Mach-O inputs. A migration service for software without source. |
