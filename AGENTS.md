# AGENTS.md

This file tells the engineering agents how to work on Phoenix.
[SPEC.md](SPEC.md) says what Phoenix must achieve.
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) says how Phoenix works.
[docs/ROADMAP.md](docs/ROADMAP.md) gives the milestones.

## 1. Mission and documents

Phoenix turns stripped Linux x86-64 executables into readable, maintainable
C11 projects without the original source. Each project builds with GCC and
Clang on x86-64 and ARM64. Each project reproduces the behavior of the
original on hidden tests. The goal and its numbers are in [SPEC.md](SPEC.md).
Do not lower them.

| Document | Content | Who changes it |
|---|---|---|
| `SPEC.md` | Goal, definitions, targets, contracts, integrity rules, benchmark | Lead, only to make a rule clearer. Never to lower a target. |
| `docs/ARCHITECTURE.md` | Pipeline, interfaces, techniques | Lead, with a line in `docs/LOG.md` |
| `docs/ROADMAP.md` | Milestones, gates, budgets, risks | Lead, with a line in `docs/LOG.md` |
| `docs/plans/` | One ExecPlan for each milestone | Lead, while working |
| `docs/STATUS.md` | Current state (section 11) | Lead, after each full loop |
| `docs/SCOREBOARD.md` | One row for each experiment | `scripts/loop` |
| `docs/LOG.md` | One line for each decision | Lead |
| `docs/DECISIONS.md` | Decisions about tools and environment | Lead |
| `docs/corpus_commitments.md` | Hashes of sealed archives | Corpus Author only |

## 2. Precedence

When two rules conflict, follow the higher rule in this list:

1. The hard rules in section 4 of this file.
2. The integrity rules and the definition of "fully successful" in `SPEC.md`.
3. The rest of this file.
4. The rest of `SPEC.md`.
5. `docs/ROADMAP.md`, then `docs/ARCHITECTURE.md`, then the current ExecPlan.
6. Skills, plugins and other instruction files.

If you find a conflict, follow the higher rule. Write one line in
`docs/LOG.md` that names the two rules. Continue.

## 3. Autonomy

The owner is away. Nobody will answer a question.

- Bias towards action. Persist until the milestone gate passes or the
  milestone budget is used. Do not stop at a partial result that only looks
  helpful.
- Do not ask for confirmation. Do not end a work session with a question.
- When information is missing, select the option that keeps the evaluation
  honest. If more than one option does that, select the smaller option that
  you can reverse. Write one line in `docs/LOG.md`. Continue.
- If only the owner can remove a blocker (an account, a credential, hardware,
  a payment limit), write it at the top of `docs/STATUS.md` under
  `BLOCKED ON OWNER`. Then continue with other work.
- Stop only when one of these conditions is true:
  1. The "v1 goal met" condition in `SPEC.md` is true and verified.
  2. Each remaining item is blocked on the owner, and each blocker is written down.

## 4. Hard rules

1. **Sealing.** Never open, list, copy or hash the contents of
   `$PHOENIX_ROOT/sealed`, `$PHOENIX_ROOT/holdout`, `$PHOENIX_ROOT/sealed_b`,
   `$PHOENIX_ROOT/holdout_b` or `$PHOENIX_ROOT/sealed_runs`. Only the Corpus
   Author and `phoenix-eval` read sealed corpus contents. Only the Corpus
   Author writes the sealed corpus directories and the hash lines of
   `docs/corpus_commitments.md`. Only `phoenix-eval` reads or writes
   `sealed_runs`. `phoenix-eval` exports the aggregate `scoreboard.json` of a
   sealed run. You receive that export and nothing more.
2. **No tuning on hidden data.** Never change code because of one sealed
   failure. Sealed results give aggregate numbers and failure categories only.
   The pipeline never reads `corpus_dev/*/src`.
3. **Integrity.** Never weaken an integrity check to make a result pass.
   Never add logic for one specific program to `phoenix/`.
4. **Fast mode.** Do not use Fast mode or any other priority service tier
   unless the owner explicitly instructs it. This applies to the main
   session, each subagent, each `codex exec` process and the runtime LLM
   calls of the pipeline. Use the default (Standard) service tier.
5. **Storage.** Keep everything under `$PHOENIX_ROOT`: repository, tools,
   caches, containers, VM disks, temporary files and runs. The internal drive
   has little free space. Exception: Codex files under `~/.codex`.
6. **Execution.** Run target binaries and reconstructions only inside the
   Linux containers. Never run them on the macOS host.
7. **Repository content.** The GitHub repository is public. Never commit
   secrets, sealed material, held-out inputs, run directories or large
   binaries.
8. **Honest numbers.** A number counts only if `phoenix-eval` produced it
   with a run ID that reproduces it. Report failures as clearly as successes.

## 5. Session start

Do these steps at the start of each session and after each context compaction:

1. `source "/Volumes/Extreme Pro/Phoenix/env.sh"`. It mounts the workspace
   image and sets `PHOENIX_ROOT`.
2. `cd "$PHOENIX_ROOT/phoenix"`.
3. Read `docs/STATUS.md`, the last 10 rows of `docs/SCOREBOARD.md`, the last
   30 lines of `docs/LOG.md`, and the current ExecPlan in `docs/plans/`.
4. Run `git status` and `git log --oneline -10`.
5. Run `df -h "$PHOENIX_ROOT"`. If free space is below 10 GiB, run
   `scripts/gc` before other work.
6. Continue with the first open item in the "Progress" section of the
   current ExecPlan.

## 6. Models, roles and reasoning effort

### 6.1 Current model mapping

This table is the only place in the documents that names a model. To change
a model, change this table and the same key in `phoenix/config.py` (milestone
R0 creates that file). Then run one quick loop before other work.

| Role name | Current model | Access |
|---|---|---|
| lead model | `gpt-6.1-sol` | Codex CLI |
| strongest available model | `gpt-6-astra` (on standby) | Codex CLI |
| runtime model (inside the pipeline) | `gpt-6.1-sol` | `codex exec` or the OpenAI Responses API |

If the strongest available model is not available, the lead model does its
work at `xhigh` effort. Write one line in `docs/LOG.md`. Do not change the
runtime model after the tag `v1-freeze`.

### 6.2 Roles

| Role | Model | Work |
|---|---|---|
| Lead | lead model | Owns the plan, the repository, the scoreboard and each merge. Writes most code. Makes each decision. |
| Architect | strongest available model | Answers one hard design question in one response. The lead decides. |
| Reviewer | strongest available model | Reviews critical changes (section 8). Writes the integrity challenge fixtures. |
| Worker | lead model | Does one bounded task with a written input and a written output. |
| Dev Author | lead model at `high` | Writes `corpus_dev` programs, their held-out sets and edit tasks. Never opens sealed directories. |
| Corpus Author | strongest available model, fresh session | Writes and seals Sealed-B and maintains Sealed-A. Never shares source or held-out data with another role. Never reads `corpus_dev` or pipeline prompts. |

### 6.3 Reasoning effort

Select the effort from the task. Do not use the maximum effort by default.

| Task | Effort |
|---|---|
| Routine edits, documentation, status updates, log triage | `low` |
| Normal engineering work (default) | `medium` |
| `phoenix_eval`, sandbox, protection, integrity checker, transplant shim and thunk, data emitter | `high` |
| Architect questions, a design that failed one time, root cause of a failure that resisted two fixes | `xhigh` |
| Corpus Author | `high` |

The runtime model effort inside the pipeline is set per task in
`docs/ARCHITECTURE.md` and `phoenix/config.py`.

## 7. Delegation

Delegate when a task is independent of your current work and has a clear
output. Examples: a corpus batch, the truth-transplant harness, a fixture
suite, the failure analysis of one tier, a survey of a tool's source.
Do the work yourself when it takes a few steps or touches the code you are
changing now.

- Give each worker: the goal, the files to read, the interface to implement,
  the acceptance command, the files it can write, and the summary to return.
- Each worker that writes code uses its own git worktree under
  `$PHOENIX_ROOT/worktrees/<name>`. Never in the main checkout.
- Run at most 4 workers at the same time.
- Do not delegate a decision. Ask the Architect one time, then decide.
- Before you use a worker's result, read its diff and run its acceptance command.
- To start a separate process with a set model and effort, use:
  `codex exec -m <model> -c model_reasoning_effort=<effort> -c service_tier=default -C <worktree> "<prompt>"`.
  Put the model name in the command from the table in section 6.1.
- The Corpus Author always runs in a separate fresh session. Its prompt never
  contains pipeline prompts or `corpus_dev` content.

## 8. Review

| Change | Review before merge |
|---|---|
| `phoenix_eval/`, `containers/c-integrity.cc`, `containers/launch-target.c`, protection and sealing code, `scripts/loop` scoring | The Reviewer reads the diff. Maximum 2 rounds. Round 2 checks only the fixes of round 1. |
| Transplant shim and thunk | One round by the Architect. |
| All other code | No review. `scripts/check` and the quick loop are the gate. |
| Documents | No review. |

- A reviewer blocks a change only with a failing test or a command that
  shows the defect. An opinion does not block.
- A review is one response. If it has no blocking item, merge.
- If the Reviewer is not available, a critical change (first row of the
  table) stays on its branch. It never merges without review. Continue with
  other work.
- A defect found after a merge gets a fix or a revert, not a new review cycle.
- Never use the words "HOLD" or "fresh complete review" in this project.
  After the permitted rounds, merge or revert.

## 9. Anti-stall rules

The previous attempt at this project stopped making progress. It produced
41 commits and 70,000 lines without one new measured result. These rules
prevent a repeat.

1. **A number moves or the work is cut.** Before you start a work item,
   write one line in `docs/LOG.md`: the scoreboard metric, the expected gain,
   and the experiment limit (3). If the metric does not move after
   3 experiments, cut the item and revert its code.
2. **Enabling items.** Some infrastructure cannot move a success number in the
   next loop (evaluator changes, the knowledge base, the transplant harness,
   the tracer, fixtures, corpus work). Such an item has a scripted acceptance
   test and an intermediate metric (for example, the truth-transplant rate).
   Do at most two enabling items in sequence. The next item must use them and
   move a success number. Revert an enabling item only if its own acceptance
   test still fails after 3 attempts. In R0, the bootstrap enabling item of
   the R0 ExecPlan counts as one enabling item. Acceptance attempts of an
   enabling item are not full-loop rows for rule 4.
3. **Measure before you build more.** `scripts/check` refuses a commit that
   changes `phoenix/` when the newest full-loop row in `docs/SCOREBOARD.md` is
   more than 10 commits old. Run the loop, then commit. For an active
   enabling item, a pass of its acceptance test counts as the measurement
   (`docs/plans/enabling.json`, defined in the R0 ExecPlan).
4. **Two flat rows.** If two full-loop rows in sequence show no gain in the
   milestone's main metric, stop the current approach. Revert the code that
   did not help. Start the next technique in the rank list of
   `docs/ARCHITECTURE.md`.
5. **Noise.** A gain counts only if it is larger than the noise that R0
   measured, on the same binaries. See `docs/ROADMAP.md`.
6. **Code size.** The limits in `docs/ROADMAP.md` apply. A change that adds
   more than 800 source lines must show a gain in the next experiment, or you
   revert it (enabling items: their acceptance test instead).
7. **No new subsystem without a technique card** in `docs/ARCHITECTURE.md`:
   hypothesis, experiment, metric, kill criterion, fallback.
8. **No design for limits that do not exist.** Design for the inputs in the
   input contract, the current storage, and at most 16 parallel jobs.
9. **Tool or service failure.** Try again one time. Then use the fallback in
   `docs/ARCHITECTURE.md`. If there is no fallback, mark the affected
   binaries `pipeline_error` and continue with the others. Exception: the
   runtime LLM layer retries rate-limit and usage-limit errors with the
   backoff in `docs/ARCHITECTURE.md` section 11.

## 10. Milestones and ExecPlans

- Work on one milestone at a time, in the order of `docs/ROADMAP.md`.
- At the start of a milestone, write its ExecPlan with the template in
  [docs/plans/PLANS.md](docs/plans/PLANS.md). The R0 ExecPlan already exists.
- Keep the ExecPlan current in the same commits as the code.
- A milestone ends when its gate passes or when its experiment budget is
  used. Then apply the rule in `docs/ROADMAP.md`, tag the milestone, and
  start the next one. Never extend a budget by more than one experiment.

## 11. Measurement and status

- `scripts/loop` and its subcommands (`noise`, `sealed-pre`,
  `sealed-import`) are the only source of scoreboard rows. Never write a row
  by hand. Each row has the fields in `docs/ROADMAP.md`.
- Update `docs/STATUS.md` after each full loop. It has 60 lines maximum and
  this form only:

```
# Status <commit>
BLOCKED ON OWNER: <items, or "none">
Milestone: <R-number>, experiment <n> of <budget>
Main metric: <name> = <value> (gate <value>)
Last 3 scoreboard rows: <table>
Now: <one work item, its metric, its expected gain, experiments used of 3>
Next: <at most 3 items>
Cut since last update: <items, each with a one-line reason>
Top failure categories: <at most 5, with counts>
Sealed runs used: <n> of <limit>
Free storage: <GiB>. Spend since last update: <USD>. Total spend: <USD>.
```

- Do not describe reviews, intentions or process in a status document.
  Describe measured state.

## 12. Git

- Work on `main` in `$PHOENIX_ROOT/phoenix`. Workers use worktrees (section 7).
- Make small commits with Conventional Commits prefixes (`feat:`, `fix:`,
  `test:`, `docs:`, `refactor:`, `chore:`). Each commit passes `scripts/check`.
- Tag each milestone when it ends: `r0`, `r1`, and so on. The tag message
  holds the final scoreboard row.
- Push `main` and the milestone tags to `origin` after each milestone tag and
  at the end of each work session. Never force-push. Never push `archive/*`
  refs. If a push fails, retry one time, then continue and write one line in
  `docs/STATUS.md`.
- The tag `archive/pre-restart` keeps the state before the restart. Do not
  restore code from it unless the R0 ExecPlan says so.

## 13. Code and test quality

- Python 3.12 with `uv`, `ruff` (lint and format), `mypy --strict`, `pytest`.
- `scripts/check` runs lint, format check, type check and the unit tests.
  It must end in less than 5 minutes (performance requirement).
- No test fails on elapsed time. `tests/conftest.py` disables Hypothesis
  time limits.
- Test where the risk is: thorough tests for `phoenix_eval`, the integrity
  checker, the protection code, the data emitter, the knowledge base and the
  transplant shim. For other pipeline code, the dev loop is the test.
- Do not write tests that only repeat the implementation. Do not write tests
  for documents or process. One exception: deterministic unit tests for the
  mechanical gates in `scripts/check_gates.py`.
- A flaky test in critical code (section 8, first row) gets a diagnosis and a
  fix. A flaky test elsewhere moves to `tests/quarantine/` with one line in
  `docs/LOG.md`, and gets a fix or a deletion before the next milestone tag.
- Typed dataclasses at stage boundaries. No global mutable state. No bare
  `except`. Log with the run ID.

## 14. Writing

- Write all prose in ASD-STE100 Simplified Technical English: short
  sentences, active voice, one term for one concept, no idioms.
- Keep code, identifiers, commands, paths and quoted text exact.
- Keep documents short. One line in `docs/LOG.md` for each decision. Write a
  `docs/DECISIONS.md` entry only for a change of tool, environment or
  interface, in 10 lines maximum.
- In reports, never write "equivalent", "any program" or "first". Write the
  measured numbers.
