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


## C-F2. Compare returned submissions with checkpoint bytes

The later combined M2 review identified C-F2 in the shared capture boundary.
Three synthetic M1 coordinator tests reproduced the defect at `6897e47`.
A later capture changed an earlier checkpoint before the batch freeze. The
coordinator retained the original `Submission`. The binding hashed the changed
checkpoint correctly. The report then used the old source identity or failure
category. The failure-category test used the real `_measure` branch.
This is partial replacement before freeze. It does not establish manipulation
of any real run.

Pass the returned submission map to `freeze_binding`. Require its keys to
match the ordered roster. For each checkpoint, `read_submission` returns the
parsed `Submission` and the SHA-256 of the same bytes. Compare that value with
the returned submission before publishing a frozen binding. Keep the original
returned value for measurement. A contradiction stops before archive access.

The reader rejects symbolic links and nonregular files. Strict physical path
resolution reports a symbolic link loop as an input error on Python 3.12.
The freeze rejects a symbolic link and uses the same strict physical path
resolution. This controls the error if a replacement occurs between checks.
The reader opens the file with `O_NOFOLLOW` and `O_NONBLOCK`. It checks the descriptor type before wrapping
it in a stream. Nonregular descriptors are closed. It reads at most 65,537
bytes and rejects content longer than 65,536 bytes. It parses that buffer and
hashes that buffer without another file read.

The metadata must contain exactly the `Submission` fields. The reader rejects
repeated fields, invalid field types, invalid digests, unsupported methods,
and contradictory source and failure status. Failed submissions retain either
`pipeline-failed` or `invalid-project`. Their origin evidence can remain bound.
Both normal submission resume and capture binding use this metadata parser.
Existing source, package report, and origin checks still run on resume.

Reconstruction time uses the existing `_seconds` normalization. Valid integers
and floating-point values can represent the same time. Boolean, negative, and
non-finite times remain invalid. Reconstruction time is still excluded from
stable replay comparisons. JSON whitespace does not change the parsed value,
but the binding records the exact checkpoint byte digest.

Existing checks still verify the binding immediately before archive access
and before report publication. A test replaces a checkpoint after its bytes
have been read. The binding retains the digest of the validated buffer. The
next check rejects the replacement before archive access.

Capture interruption, freeze interruption, completed resume, exact replay,
complete roster accounting, model lookup, and public report schema 1 retain
their definitions. Old bindings are not backfilled. C-F1 replay ancestry is
M2-only and belongs to a separate correction.

For the M2 merge, apply the shared `submission.py` and `capture_binding.py`
changes. Pass `submissions` as the fourth `freeze_binding` argument in M2's
shared coordinator. Keep M2's coordinator and replay ancestry changes.
Port the focused shared tests and update direct calls to the required freeze
argument. Do not replace M2's complete `m1.py` with this M1 file.

## Detected capture contradictions are terminal

The next combined M2 review found a retry defect in C-F2. The first freeze
rejected a changed failed checkpoint but left `phase` set to `capturing`.
On retry, the saved-submission reader returned that changed value. The next
freeze accepted it. A synthetic M1 coordinator probe reproduced this defect
at `f5f0608`. It used the real saved-submission reader and failed-result
measurement branch. The retry opened one synthetic archive and published
40 records. This does not establish a change in a real evaluation run.

A parsed checkpoint that contradicts its returned submission now ends an
unbound capture. Create `capture-rejected.json` in the run directory.
Its bounded record contains schema 1, reason `checkpoint-mismatch`, and
three SHA-256 digests. These identify the task key, rejected checkpoint
bytes, and returned submission. The returned submission digest uses UTF-8
JSON from `asdict` with sorted keys. The record contains no project text,
model response, or archive input.

Only an unbound `capturing` run can create this marker. Create it exclusively
and sync the directory before writing the record. Flush and sync the details.
The presence of the marker blocks reuse even if its details are empty or
incomplete. The next invocation rejects the run before reading saved
submissions or archives. Restoring a checkpoint does not remove the marker.
Keep the rejected run and use a new run ID.

An earlier synthetic experiment staged rejection in a temporary file.
An interruption before replacement left the old run resumable. A second
candidate invalidated the binding in place. The parent reproduced an
unwanted write through a hard link to that binding. Exclusive creation
of a separate marker blocks retry without changing any existing file.
The ordinary capturing and frozen binding records remain unchanged.
A normal interruption during valid freeze remains resumable.

This state records only an explicit comparison contradiction. It does not
turn every exception, missing file, invalid checkpoint, or interruption into
a terminal state. Existing safe path checks remain in force. Changed
checkpoint bytes, model ledger bytes, ledger identity, and published reports
are not edited. Existing frozen bindings retain their format. Historical
runs receive no retrospective binding. Public report schema 1, scoring,
accounting, replay comparison, and reconstruction time retain their meanings.

The existing evaluator lock serializes coordinator invocations. The evidence
model still does not authenticate a filesystem owner. It also cannot persist
a rejection if the process stops before its first durable state change.
This change makes no claim about a failed storage device or power-loss
behavior beyond the filesystem's `fsync` contract.

The minimal M2 port replaces only `phoenix_eval/capture_binding.py` with this
candidate. Its public function signatures are unchanged. Keep M2's existing
four-argument `freeze_binding` call and coordinator logic. Port the focused
retry and interruption tests, including the rejection marker checks.
Do not replace M2's `m1.py`, `model_ledger.py`, or `submission.py`. C-F1
publication and log-path corrections remain with the parent.
