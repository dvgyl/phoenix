# Publish complete submission captures

## Decision

Stage each task's source, package report, development evidence, raw lift
evidence, and submission record in a private temporary directory. Publish
the complete capture with one directory rename. Read committed captures
on resume. Ignore abandoned staging directories.

The evaluator measures wall time from the first pipeline invocation
until its final completion. Preserve the start time across provider
limits and interruptions. Report elapsed time for failed tasks too.
The interval includes waits between attempts.

## Evidence

The earlier capture sequence could stop after freezing a report. Resume
then rejected a new elapsed-time field and stored a permanent project
failure. The regression reproduced this failure for both methods.

Tests interrupt source capture, report capture, record writing, and
publication. Resume converges to a valid submission. A committed capture
is reused. Tests also check abandoned staging, invalid timers, and
elapsed time across a provider wait followed by pipeline failure.

## Limits

Invalid committed artifacts stop evaluation. Replay requires the
recorded source revision and capture layout. Clean native builds still
require the pinned upstream package snapshot.
