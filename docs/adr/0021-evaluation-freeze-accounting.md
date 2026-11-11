# 0021. Bind captures and reconcile the complete model ledger

## Problem

Independent Astra review identified R3 and R4 in the shared evaluation engine.
Synthetic M1 tests reproduced both findings at `baae648`.

A completed resume accepted changed source bytes when the same capture's
checkpoint contained the new source digest. Resume then replaced the completed
report. The engine had no separate binding for the complete capture roster.

The engine hashed the complete model ledger. Its task summaries selected only
known task keys. A valid event with another task key contributed to the budget
but had no reported charge. This finding does not demonstrate a budget bypass.
Neither finding establishes that real evaluation evidence was manipulated.

## Decision

Use `capture-binding.json` as separate evidence in each evaluation directory.
The shared `capture_binding` module takes the run directory and ordered task
keys. It does not import the M1 engine. The M2 engine can use this same boundary.

Reject duplicate JSON fields. Require the schema value to have integer type
and value 1. Boolean and floating-point values cannot identify this schema.

The first record has exactly these fields:

```json
{"schema": 1, "phase": "capturing"}
```

Create this record before the configuration file or any submission. An existing
evaluation without this record cannot resume under the new code. The only
permitted pre-existing file in a new evaluation directory is `evaluation.lock`.

After all submissions finish, freeze the model ledger identity and validate its
complete attempt history against the task roster. Then replace the capture
binding atomically with this record shape:

```text
schema: 1
phase: "frozen"
configuration_sha256: SHA-256 of configuration.json bytes
model_ledger_sha256: SHA-256 of model-ledger.json bytes
captures: ordered list of
  key: task key
  files: map from capture-relative file path to SHA-256 of file bytes
```

The file map includes `submission.json`, all project files, the package report,
development evidence, and origin evidence when present. It also includes files
retained in failed captures. Hashing the checkpoint binds its failure category,
all submission identities, replay origin, and reconstruction time. Every task
must have a capture directory and checkpoint. Task keys cannot repeat.
Symbolic links and nonregular evidence files are rejected. Empty directories
have no content identity. Build output and abandoned staging directories are
outside the capture and are not included.

The model ledger identity names the pipeline run and the complete log hash, or
the log's absence. The capture binding therefore also binds this log identity.
The existing log validation still checks the complete log bytes independently.

Check the frozen binding before submission reuse, immediately before archive
access, and before report publication. Keep its exact bytes in memory during
measurement. Check both the saved binding and current evidence against that
copy. A mismatch stops the evaluation before it can replace a completed report.
Replay also requires a frozen binding at its original evaluation directory.

The `capturing` state permits recovery from an interrupted submission or freeze
publication. No archive can be read in that state. A completed report cannot
resume with that state. Once the `frozen` record is published, missing or changed
evidence cannot start a new freeze. The existing submission capture transaction
and reconstruction timer remain unchanged.

## Complete accounting

`bound_summaries` reads the complete frozen log through the existing event
parser. It rejects any task key outside the fixed roster. It also rejects
duplicate roster keys. It returns a summary for every roster task, including
failed tasks and tasks with no calls.

The parser validates every event and attempt transition. An attempt cannot
change its task key. Each validated attempt therefore belongs to exactly one
task summary. Started, failed, retry, completed, and limit-exceeded attempts
retain their existing charge rules. Unknown-cost reservations remain separate
from measured charges. No event is removed or edited.

Compute these summaries before archive access. Before report publication,
recompute them from the same frozen log. Require every reported task summary
to equal its corresponding complete-log summary. This checks calls, token
counts, measured charges, and reservations. It prevents omitted charges and
charge transfer between tasks, even when aggregate totals would match.

## Compatibility and limits

The M1 API, schema-1 report fields, task keys, scoring, and stable result fields
retain their definitions. Recorded-response lookup is unchanged. Reconstruction
time remains excluded from stable replay comparisons. Tool, source, image, and
pipeline configuration identities retain their existing checks.

Compare configuration and reported model summaries with type-preserving JSON
serialization. Python dictionary equality treats some Boolean, integer and
floating-point values as equal. Those types are distinct in frozen evidence.
Reject non-finite values during serialization.
On completed resume, validate the saved report configuration before capture
reuse or archive access. Checking the separate configuration file does not
validate the report. Preserve an inconsistent completed report when rejecting it.

Older evaluation directories without a complete binding are not migrated.
Use their recorded revision to preserve historical evidence. Do not create a
new binding from a changed checkpoint. New evaluation and replay runs are
required after integration and review.

The separate binding detects partial evidence replacement. It does not protect
against a filesystem owner who rewrites the binding and every other trust
anchor. It does not independently authenticate provider usage. These are limits
of the evidence model, not new protection claims.

The two M2-only findings, R1 and R2, are outside this change. Independent Sol
review, Astra closure review, the full parent gate, combined M2 integration
review, and new candidate measurements remain required. This change does not
establish M1 acceptance or any benchmark score.

## Recheck the selected M2 replay chain

An M2 replay uses the same stable report and capture records from each
ancestor. Retain the verified capture binding bytes and exact report
digest for each run. The recorded report reader parses and hashes one
bounded regular-file read. Verify each ancestor again before the T0
archive, before the T1 archive, and after staging the result. A changed
report or capture stops publication. A cyclic origin log or identity
path is an input error.

These checks detect changed evidence at the stated boundaries. They
do not authenticate the filesystem or provide a filesystem snapshot.
