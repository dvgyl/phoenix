# ADR 0020: One frozen M2 evaluation matrix

Date: 2026-11-10
Status: Implemented. Independent review and a sealed run are pending.

Phoenix must evaluate the full T0 and T1 release rosters in one frozen run.
A later submission must not receive information from an earlier measurement.

## Decision

Extend the existing independent evaluator. Keep its submission capture,
development proof, original oracle, four builds, integrity checks, and model
accounting. Do not copy the engine. The evaluator does not import `phoenix`.
It invokes the existing guarded pipeline command.

`Tier` defines the required program counts and optimization flags. `Batch`
contains one tier, its complete variant roster, and three SHA-256 identities.
These identify the release manifest, committed source archive, and committed
input archive. `Scope` contains exactly T0 followed by T1. Its versioned record
also contains both methods, all task keys, all four rebuild configurations,
and the fixed project CMake content.

M2 configuration schema 2 adds this scope to the existing provenance fields.
Those fields bind the clean checkout, pipeline source, evaluator source, lifting
tools, runtime, worker images, integrity images, and pipeline settings.
The T0 archive fields remain present and agree with the T0 batch.

M2 has 130 original variants and 260 method tasks. Each valid submission uses
the existing four-build evaluator. A failed submission remains a result with
its failure category. Its required builds do not count as successes.

M2 prefixes task keys with `t0-` or `t1-`. The prefix also applies to original
bytes, development evidence, lift evidence, case selection, and model-log keys.
Independent batches can thus use the same program names.

All tasks use one pipeline run and its one model ledger. The default budgets
remain $5 per binary and $200 per run. The evaluator captures every submission
and freezes the complete model-log hash before it reads either input archive.
It verifies development evidence before that read. A frozen run cannot capture
a missing submission. A resumed capture must retain its configuration.

## Results and acceptance

The report keeps each variant result, all four build results, all evaluation
errors, and all emulator disagreements. Grouped results separate tier, original
optimization flag, method, and rebuilt architecture. Architecture success
requires both compilers to match every eligible case with no original error
and no error for that architecture. An ARM64 error does not erase an x86-64
success. This distinction exposes ARM-only failures.

Full success still requires the existing behavior and integrity verdicts.
Coverage still counts recovered block entries. Source adequacy is separate
author evidence. This extension does not derive source coverage from blocks.

The Phoenix thresholds are 16/20 for T0 `-O0`, 16/20 for T0 `-O2`, 18/30 for
T1 `-O0`, and 12/30 for T1 `-O2`. T1 `-Os` has no numerical success threshold.
It still has architecture results and a portability check.

For each tier and flag, compare the absolute architecture success-count
difference with five percent of the denominator. Use integer arithmetic.
This check does not round a difference down. Record ARM-only variant keys with
the category `arm_only_behavior_failure`. Do not record failing inputs or an
assumed cause. Any ARM-only failure keeps `accepted` false and sets the
root-cause gate to `required`. The parent must assess causes separately.
These numerical results alone do not establish completion of the M2 milestone.

## Replay and compatibility

`phoenix-eval m2 --run-id ID` runs M2. `m2 --replay ID` and root-level
`--replay ID` use recorded responses. Root-level dispatch requires exactly one
supported report kind. It rejects mixed, missing, malformed, or conflicting
reports. M2 report records must match the exact scope and result roster.

Replay requires a new run ID. It follows the recorded M2 lineage to the original
pipeline run. Every link must have the same configuration and frozen log
identity. Every replay ancestor must have `reproduced=true`. Every ancestor
must retain the same stable report fields as the selected reference. A failed
replay cannot replace the original reference. These checks occur before
submission capture and held-out archive access.
Serialize the complete stable projection with JSON types preserved. Use the
same projection for ancestor and final replay comparison. Configuration checks
also preserve JSON types. An integer and an equal float, or a Boolean and an
equal integer, are distinct frozen evidence. Reject non-finite values.
Cycles and conflicting origins are errors. Replay cannot create a
model log or call a fresh model provider. Source hashes must match before the
evaluator opens held-out cases. Replay compares all stable report fields.
Run identity, replay status, and elapsed reconstruction time can differ.
Timing does not decide acceptance.

The saved M2 report reader validates both result forms. A failed capture has
no source identity and has a pipeline or project failure category. A measured
capture has behavior and integrity evidence. The reader requires exactly four
supported builds. It validates tested executable hashes, case and error counts,
coverage counts, model token and cost fields, and consistent verdicts. Full
success requires complete passing integrity evidence. Compiler failures,
artifact-read failures, oracle errors, partial behavior, and short integrity
error records remain valid failures. These checks apply at the saved-data
boundary. The trusted measurement path retains its existing rules.

The M1 entry point, schema-1 configuration and report fields, task names,
threshold, and replay comparison remain unchanged. M1 still selects T0 `-O0`.
`t0_manifest()` remains the T0 wrapper. `heldout_cases()` still defaults to
`t0/cases`. The loader also accepts an explicit tier. Both tiers reject
unknown fields, duplicate members, links, traversal, missing cases, and invalid
hashes. Existing file and archive size limits remain unchanged.

## Validation and limits

Tests use synthetic metadata, opaque bytes, and synthetic archives. They cover
scope round trips, changed scopes, exact rosters, tier collisions, atomic
capture interruption, resume, shared budgets, log lineage, report dispatch,
and stable replay fields. Existing pair and integrity tests remain in place.
A synthetic test sends all 260 tasks through the existing measurement and pair
functions. It observes 1,040 mocked compiler builds. It does not execute targets.

No sealed release, source archive, held-out input, or real run artifact was read
for this change. No container, pipeline model provider, or target was run.
The parent must run the complete gate and obtain independent Astra review
before a sealed M2 run. The separate M1 replay investigation is outside this
change. Existing saved M1 results were not opened.

The original matrix work block received an independent Sol HOLD for replay
lineage and contradictory saved evidence. The correction has synthetic
regressions. A different independent reviewer must assess the correction.
The separate R3 capture-binding and R4 ledger-reconciliation fixes remain
shared-engine integration gates. This correction cannot certify sealed use
before those fixes are integrated and reviewed.
