# Log

One line for each decision, cut, conflict or surprise. Newest line last.
Form: `<commit or run ID> | <decision or fact> | <reason>`.
The history before the restart is in the tag `archive/pre-restart`.

e591d41 | Restart from the M1 core. Delete unreachable evidence code (52,664 lines) and the stalled process records. | The post-M1 work added 70,000 lines and no measured result.
e591d41 | Disable Hypothesis time limits in `tests/conftest.py`. | The 200 ms default deadline failed the gate under host load without a code change.
restart | Keep the existing sealed corpora as Sealed-A (validation only). Headline numbers come only from a new Sealed-B. | Sealed T0 was used at M1. T1 to T3 were never evaluated.
restart | Replace milestones M2 to M4 with R0 to R7 (docs/ROADMAP.md). | The new plan measures before it builds and limits each item by experiments.
restart | Add technique N13 (mutant-adequate dev set) to R3. | Edge coverage alone misses wrong constants and boundaries that the hidden sets detect.
restart | An enabling-item attempt is one declared design, not one failed test run. | Normal test failures during work must not kill a technique.
restart | Measure noise per tier with a quick set of 24 binaries. | Two binaries per cell give a threshold of 0 or of the whole cell.
restart | In R0, test the workspace resize as a dry run only. | A real detach of the workspace can end an unattended session. 31 GiB are free.
