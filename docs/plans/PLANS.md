# ExecPlans

An ExecPlan is the working plan for one milestone or one large work item.
Write one before you start a milestone. Keep it current while you work.
A new engineer with only the repository and the ExecPlan must be able to
continue the work without other context.

## When to write an ExecPlan

- At the start of each milestone in [the roadmap](../ROADMAP.md).
- For a work item that changes more than one package, or that adds a new
  interface to [the architecture](../ARCHITECTURE.md).

Do not write an ExecPlan for a fix that takes one commit.

## File name and location

`docs/plans/<milestone>-<short-name>.md`, for example `docs/plans/R1-per-function.md`.
When the milestone ends, keep the file. Add the result to its
"Outcomes and Retrospective" section.

## Rules

1. The plan is self-contained. Define each term that the architecture
   does not define. Give each path, command and interface in full.
2. The plan is a living document. Update "Progress", "Surprises and
   Discoveries" and "Decision Log" at each stopping point, in the same
   commit as the code.
3. Each step ends in a state that a command can check. Write the command
   and the expected result.
4. The plan names the scoreboard metric that the milestone must move, the
   value before the work, and the gate value.
5. The plan obeys the experiment budget and the anti-stall rules in
   [AGENTS.md](../../AGENTS.md). A plan never extends a budget.
6. Do not ask the owner for the next step. Continue with the next item in
   "Progress".
7. Use prose for the reasoning. Use checklists only in "Progress".

## Template

Copy this skeleton. Keep the section names. Write "None yet." in a section
that has no content.

```
# <Milestone>: <short action-oriented title>

## Purpose
What a user of Phoenix gets when this plan is complete. The scoreboard
metric that must move, its value now, and the gate value.

## Progress
- [ ] Step 1: <step> (check: <command> -> <expected result>)
- [x] Step 0: <step> (done <commit>)

## Surprises and Discoveries
Facts found during the work that change the plan. One line each, with
the evidence (a run ID, a command output, a file).

## Decision Log
One line for each decision: the decision, the reason, the alternative
that was not selected.

## Outcomes and Retrospective
Fill in at the end: the gate result, the final scoreboard row, the cut
items, and what the next milestone must know.

## Context and Orientation
The files and interfaces that this plan touches. The state of the code
at the start, with the commit.

## Plan of Work
The sequence of work items. For each item: the metric, the expected
gain, and the experiment limit (3 experiments maximum for one item).

## Concrete Steps
The exact commands and edits for each work item.

## Validation and Acceptance
The gate script, its expected output, and how to read the scoreboard row.

## Idempotence and Recovery
How to run each step again safely. How to return to a known good state
after a failed step (the commit or tag to return to).

## Interfaces and Dependencies
The interfaces from the architecture that this plan implements or
changes, with their exact signatures. External tools and their pinned
versions.
```
