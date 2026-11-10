# Check integrity during development repair

## Decision

Run the source integrity checker for each buildable Phoenix candidate.
Use the source snapshot and the executable bytes used in development
tests. Give the checker the original binary, recovered function shapes,
and original development outputs.

Stop repair with a passing result when both behavior and integrity
pass. Give repair the integrity categories and static function limits.
Keep the evaluator's independent check of its frozen submissions.

Record the checker source digest and image identities with the worker
identities. Check these identities on resume and replay. A resumed
replay reads the original model log and keeps its replay lineage.

## Evidence

The earlier pipeline stopped after a development behavior pass. Its
integrity checks ran only during final evaluation. This omitted the
development integrity check required by SPEC.md section 4.2.

A synthetic test makes a behavior pass fail integrity. Repair then
produces a candidate that passes both checks. Other tests reject changed
source snapshots, tested executable bytes, and checker identities.
The parent process passed the full local quality gate.

## Limits

The source policy can reject valid rewrites. Every policy rejection
requires repair or a failed result. Linux integration and an independent
review are required before another sealed measurement.
