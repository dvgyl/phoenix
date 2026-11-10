# Bind accounting to complete model histories

## Decision

Use one typed event reader and charge calculation for runtime and
evaluation. Each attempt has one start and at most one terminal event.
Validate the history before cache lookup, budget calculation, and
summary calculation. Validate live completions with the same parser.

Keep crash and unknown-cost reservations. Record an invalid live
response as a failed attempt with its reservation. Include charges
from over-limit completions.

Derive each task's tokens, charges, and unknown reservations from bytes
that match the frozen log identity. Include failed and zero-call tasks.
Freeze the package report separately and bind its digest to the
submission. Use that copy for reconstruction time.

## Evidence

Synthetic regressions reproduced terminal charge erasure, a live model
mismatch, mutable reported cost, and missing failed-task charges.
Additional tests cover terminal transitions, reservations, report
mutation, and the fixed pricing boundaries.
