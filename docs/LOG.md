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
1a3716c | Use the R0 ExecPlan and this log instead of the additional pstack plan and TSV log. AGENTS.md sections 1, 2 and 14 take precedence over the pstack work-record rules. | Keep one project work record.
1a3716c | Do not delegate before scripts/launch-role exists. AGENTS.md section 7 takes precedence over the pstack how and architect delegation rules. | Protect hidden data before a worker starts.
1a3716c | Storage item: free storage, expected at least 15 GiB and a resize record, limit 3 attempts. | R0 steps 2 and 3.
1a3716c | Both model availability calls returned AVAILABLE with service_tier=default. | Logs are tmp/r0-astra-availability.log and tmp/r0-sol-availability.log.
1a3716c | Bootstrap item: bootstrap checks passed, expected scripts/gate R0-bootstrap PASS, limit 3 acceptance attempts. Attempt 1 of 3 uses the R0 plan interfaces and the M1 path. | No success measurement exists before this enabling item.
1a3716c | The evaluator profile denies writes to sealed corpora. SPEC.md section 10.5 takes precedence over the R0 plan statement that this profile denies nothing. | Only the Corpus Author writes sealed corpora.
1a3716c | Retry the protection review with the read-only command of AGENTS.md section 8. | An outer role profile prevented the reviewer command tool from applying its nested sandbox.
1a3716c | Keep the section 8 review scope and maximum of two rounds instead of the additional pstack comment review. AGENTS.md sections 2 and 8 take precedence. | Critical code has one independent reviewer.
1a3716c | Protection review round 1 found that Corpus Author could read twins and that a copied input could be inside protected evaluation records. | Add the development denial and copy inputs, the probe and the working directory into the pipeline run. Reserve m1-t0-* for sealed records.
1a3716c | Protection review round 2 found no remaining defect in the two fixes. The 72 targeted tests and all 88 real-directory probe checks passed. | Evidence is in tmp/r0-protection-review-2.log, tmp/r0-protection-tests-round2.log and tmp/r0-probe.log.
1a3716c | Isolate the synthetic Git repositories from inherited GIT_* settings in the protection fixtures. | The direct full check passed 1071 tests. The commit hook failed at worktree setup in 7 tests before the protection assertions.
1a3716c | The initial rg --files search from PHOENIX_ROOT did not exclude sealed directories. Its output contained only phoenix/AGENTS.md. No sealed file content entered the chat. All later searches use the checkout. | Record the search-scope error. Do not repeat a workspace-wide search.
a52db2c | Read six primary sources and the ASE 2026 PCodeTrans record. Add the prior art, qualify the in-situ check, and require equal-model, equal-budget behavior-only and plain-agent baselines before a pipeline-value claim. | Owner instruction. No target changed. PCodeTrans file-level success aggregates isolated function checks.
a52db2c | Use the R0 plan git worktree command after two managed-worktree requests did not return and Git reported no worker worktree. | The Dev Author runs at worktrees/dev-author under its role profile.
a52db2c | The lead runs full checks and commits the corpus branch after the Dev Author stages its files. | SPEC.md section 10.6 requires author independence. The author profile denies pipeline code that scripts/check reads. Both the protection rule and the commit checks stay active.
add07ce | Restore the M1 lift and generation and remove the checked-switch path, its tests and the removed CLI option. | R0 salvage. The two removed CLI test functions tested only the deleted option.
add07ce | Centralize the unchanged model identifiers and price tuples in phoenix/config.py. Replace model-name enum members with role keys at each caller. | R0 step 8. Both model identifiers remain as AGENTS.md section 6.1 specifies.
add07ce | Use one Architect response for the stopped-run persistence question. AGENTS.md sections 6 and 7 take precedence over the pstack architect design panel. | The lead retains the decision. No implementation is delegated.
add07ce | Delegate the corpus builder to a bounded engineer worktree at high effort while the Dev Author writes the corpus. | Its output is limited to the build command, the evaluator corpus helper and their tests. The lead will review and run acceptance.
