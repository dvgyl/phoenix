# Log

One line for each decision, cut, conflict or surprise. Newest line last.
Form: `<commit or run ID> | <decision or fact> | <reason>`.
The history before the restart is in the tag `archive/pre-restart`.

e591d41 | Restart from the M1 core. Delete unreachable evidence code (52,664 lines) and the stalled process records. | The post-M1 work added 70,000 lines and no measured result.
e591d41 | Disable Hypothesis time limits in `tests/conftest.py`. | The 200 ms default deadline failed the gate under host load without a code change.
restart | Keep the existing sealed corpora as Sealed-A (validation only). Headline numbers come only from a new Sealed-B. | Sealed T0 was used at M1. T1 to T3 were never evaluated.
restart | Replace milestones M2 to M4 with R0 to R7 (docs/ROADMAP.md). | The new plan measures before it builds and limits each item by experiments.
