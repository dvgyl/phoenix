The owner requires verified Phoenix v1 completion through SPEC.md section 9. This report reviews the exact scope and pure-frame integration. The corpus remains agent-sealed by a separate Author on an honor system.

**PASS for this exact scope and pure-frame integration under its canonical checked-input contract.** I found no concrete integration defect. This PASS permits the supervisor to assess these seven files for integration. It does not approve production capture, a milestone, or SPEC section 9 completion.

**Full raw capture review remains OPEN. Production admission remains HOLD.** The isolated `admission.py` and `runtime.py` are absent from this revision. Their full independent review remains missing after provider screening. Neither the parser-only PASS nor this review replaces that review. No retry or rephrased review request was made. The direct Astra review of collector transport also remains OPEN.

The reviewed branch is `agent/m2-frame-integration-resume`. The exact revisions come from [revisions.json](revisions.json). No later head was substituted.

| Identity | Exact value |
| --- | --- |
| Reviewed commit | `e7c9450bd7f2a891c905048fa46064c684ea05ad` |
| Base and sole parent | `3939fbc0d928d7701b289d559835bb466497a69c` |
| Seven-file source commit | `94caeb4fcd8f7734b11da59c455f4e4d04dc9caf` |
| Base Git tree | `1ad3e92d8046ff419d3c06a4ed8dc69c3dc3d3ee` |
| Reviewed Git tree | `b9ae5fb9b8b8e03dd3fe3badb572c3827ea6e3cd` |
| Local main before and after | `3939fbc0d928d7701b289d559835bb466497a69c` |

Both endpoint checks found a clean checkout. All 206 tracked files match their committed blobs and executable modes. The complete [before record](before.json) and [after record](after.json) are equal. These checks establish endpoint identity. They do not attest continuous activity by other processes. No fetch or server check ran. The `server_verified` field is supplied metadata.

The base has 199 tracked paths. Exactly 197 retain their base blobs and modes. The two changed pre-existing paths are `docs/STATUS.md` and `docs/LOG.md`. Every pre-existing implementation, test, configuration, and pipeline file remains byte-identical to the base. Exactly seven paths are added. Each has mode `100644` and matches the source commit byte for byte. [source-proof.json](source-proof.json) records all Git identities, added-file hashes, and the two documentation changes. [integration.patch](integration.patch) contains the entire integration diff.

| Added path | SHA-256 |
| --- | --- |
| `phoenix/observe/scope.py` | `0cb93cadb4657dfeb776293fe823da439eb186c71978f9c74a7d0c1533867ef4` |
| `phoenix/observe/capture.py` | `580188caf5f6c45330a15db6f018337c59826d925599e32ca64b53b122133467` |
| `phoenix/observe/frames.py` | `08a60db74fdc7d03445b11bfe85ae6f7945d68f8acc8a5bbab042a211030c54b` |
| `tests/test_observe_scope.py` | `2a2ba8c115aeb852834b69e82da9a82a2303dbdf40e0a620a0ca7188a138bd6b` |
| `tests/test_observe_frames.py` | `82afd2cfdfba3f0db57414f766cacfc7708f3997b4bc43a8b272e0ca83a49c90` |
| `docs/adr/0030-requested-observation-scope.md` | `66ee8af0d38c090f9edab0e9165c60d84f28d45085a663a7412ce1dfb21e9905` |
| `docs/adr/0031-checked-frame-reduction.md` | `08417759fefb1cae481fa0f29ac38b512192f07f54cb63118c1e4ec30f5f12c1` |

Six shared files match the source branch exactly. They are observation plan, mapping, and wire, recovery imports and transfers, and lift index. Current main's `phoenix/lift/mapping.py` remains unchanged. Its SHA-256 is `400b0c21201a522133767b5505c02dc000d8ed25e7d5390744c1b383bd0df0aa`. The frame branch version has SHA-256 `0de522e7d34c921545c94087eae89a6ef7875079e8d3a16012342fb75c02956b`.

The independent abstract syntax tree check confirms the mapping difference. [read_companion at line 320](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/lift/mapping.py:320) delegates to `read_selected_generation`. The helper preserves the exact selector read and validation statements. It assigns the old inline directory expression to `generation` and passes that value to the same `read_generation` call. The binary argument and companion return are unchanged. All other definitions and top-level statements match the frame branch. Fresh controls exercise both readers with a valid generation, five malformed selectors, and three changed generation artifacts. The valid generation feeds the installed scope compiler and produces the same certificate as the direct fixture.

The policy identity binds installed current main source. Its independently calculated value is `51b6e8997390608328232495dcfd4c82b4b422c80cbacc3d5151cfb796780c9e`. It matches [policy_implementation_sha256 at line 361](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/scope.py:361). The calculation uses canonical JSON with the ordered nine relative source names and their complete byte hashes. It does not use a copied certificate or saved digest as the result.

The frame branch policy is `d958b7093004c7688813a350b8a24f0f1be7010fb781bf7da8c044f2dae855c0`. The policy difference is required by the retained mapping helper. The installed value equals the previously reviewed capture-port value because their declared policy source bytes agree. The names and individual hashes are in source-proof.json. Each of nine independent in-process source-read mutations changes a newly compiled certificate's policy and scope digests. Every other certificate field and full-plan identity remains equal. No source file was mutated.

The compatibility and contract findings are as follows. The line links refer to the exact reviewed checkout.

| Review area | Finding and evidence |
| --- | --- |
| Static evidence reconstruction | [scope.py line 778](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/scope.py:778) reconstructs the full plan. Line 784 checks exact proof field types and values. The compiler retains full-plan identity, every site disposition, and every original gap. Existing tests and fresh canonical controls pass. |
| Stricter ordinary flow | [scope.py line 681](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/scope.py:681) requires positive evidence. Empty MOV and XOR translations remain rejected. Exact neutral forms retain their restricted path. XABORT and XBEGIN retain rejecting guards. Operation shapes do not prove operand semantics or translation completeness. |
| Current identity and stale mixtures | [frames.py line 263](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/frames.py:263) binds the receipt to the supplied scope digest. Fresh user and transit controls reject an old-policy selection with a current receipt, and an old-scope receipt with a current selection. Both APIs return no local values. |
| Private-input trust limit | [capture.py line 61](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/capture.py:61) declares `_CheckedCapture` as private boundary input or synthetic test input. Fresh controls deliberately construct a coherent old selection and receipt. The pure reducer admits that synthetic object and reports its old policy. This is a demonstrated contract limit, not authentication or a new integration defect. A trusted boundary must rebuild scope and compare current identities before construction. |
| Uniform rejection | [frames.py line 924](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/frames.py:924) returns `Rejected(rejection, ()), ()`. Both public functions share this decision. Fresh canonical controls test all six call fields, missing roles, duplicate entries, missing terminal pairs, open frames, early shared-value errors, guard failure, counters, outcome mismatch, and root inconsistencies. Every reached rejection stays unadmitted and exports no local values. |
| Successful local values | [frames.py line 882](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/frames.py:882) exports only Entry, CallAttempt, and Continuation snapshots after successful closure. Fresh controls check exact bits, sites, event sequences, scope identity, wire identity, and immutability. ReturnAttempt values remain excluded. |
| Frame grammar | [frames.py line 528](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/phoenix/observe/frames.py:528) enforces shared roles. The reducer uses one stack and new frame IDs. It checks call RSP minus eight, the other five fields, top-frame returns, continuation identity, return RAX, and root closure. Transit remains exact and eager-only. No second reducer or repair scan is added. |
| Source closure | Static traversal resolves 32 local modules, including package initializers and conditional imports, within this checkout. The closure is recorded in source-proof.json. A fresh runtime import check confirms that loaded project modules use matching reviewed files. This is source compatibility evidence, not runtime capture identity. |
| Default pipeline and generation | No pre-existing implementation changes. No pre-existing project module imports the three added modules. Existing entry points and generation settings remain unchanged. The new APIs have no pipeline caller or public raw-capture adapter. Source inspection supports unchanged default behavior. No live pipeline regression claim is made. |
| Pure API effects | A fresh control disables subprocess creation, shell execution, network sockets, and file writes while it calls scope compilation and both frame APIs. The control passes. Policy compilation reads installed source bytes. It does not execute the synthetic target bytes. |
| Maintainability and comments | Frozen records define evidence boundaries. One reducer owns frame admission. The two source comments preserve necessary limits on byte vetoes and boundary authenticity. Module and API docstrings state the pure-input limits. No actionable comment defect was found. No reviewed comment or source was edited. |

The current `docs/LOG.md` statement about old certificates must be read within that private-input contract. The compiler always derives current policy identity. The reducer does not independently authenticate a coherently supplied old certificate. [ADR0031 line 18](/Volumes/PhoenixWork/worktrees/m1-ledger-identity/docs/adr/0031-checked-frame-reduction.md:18) states the required boundary work. No public production path is added that could claim to perform it.

All fresh tests are in [test_integration_controls.py](test_integration_controls.py). They use synthetic public fixtures. They add assertions for current-main integration. They do not edit old controls or test private capture modules. [commands.jsonl](commands.jsonl) records actual argument vectors, working directories, separate cache paths, log paths for repeated commands, and child exits.

| Check run by this reviewer | Actual exit | Actual result |
| --- | --- | --- |
| Scope, frame, observation mapping, observation plan, observation wire, and transfer tests | 0 | 1,009 passed. [Log](focused.log). |
| Final fresh integration controls | 0 | 72 passed. The final repeat also passed 72. [First complete log](independent.log), [final log](independent-repeat-1.log). |
| Ruff check on the five added Python files | 0 | Passed. [Log](ruff.log). |
| Ruff format check on the same files | 0 | Five files already formatted. [Log](format.log). |
| Strict mypy on the same files | 0 | No issues in five source files. [Log](mypy.log). |
| Complete integration diff check | 0 | Passed. [Log](diff-check.log). |
| Source proof and final state comparison | 0 | Exact source copies, compatible helper, unchanged main, and equal endpoint records. [Proof](source-proof.json). |

The supplied mandatory hook log was read in full. [integration-commit-hook.log](/Volumes/PhoenixWork/audit/resume-20261112/integration-commit-hook.log) says `Phoenix quality checks` passed and records commit `e7c9450`. Its named [exit file](/Volumes/PhoenixWork/audit/resume-20261112/integration-commit.exit) contains `0`. The hook log is a summary. It does not contain expanded per-test counts. I did not infer a full-suite count from it or rerun runtime-dependent checks.

The supplied [integration-focused-v2.log](/Volumes/PhoenixWork/audit/resume-20261112/integration-focused-v2.log) records the parent's 1,009 passes. This review independently repeats that exact six-file suite. The parent dependency repeats record exit 0 for 27 frame controls with five skips and 32 capture controls. Their full logs and parent-independent-repeat.json were read. Those capture checks remain dependency evidence only.

The complete three required prior reports were read. Their exact inputs are bound in [input-identities.json](input-identities.json). The dependency-port PASS covers exact copies and compatibility. The scope PASS covers its explicit, stricter static contract. The frame PASS covers its revised pure checked-input contract. Historical HOLDs and prior process errors remain in their original records. The frame report's old scope HOLD is historical. The later scope and dependency reviews address that static correction. They do not close production admission.

The withdrawn positives remain withdrawn. The unchanged older scope suites report 177 passes with two failures and 517 passes with one failure, each at exit 1. Their empty-translation MOV and XOR expectations are outside the current contract. The unchanged older broad frame script reports 20 of 21 controls passing at exit 1. Its local-retention positive is outside the revised contract. This review neither reruns nor edits those older broad suites. It does not claim they fully pass. No issue is closed by this report.

The parent's initial preflight refused a source mismatch before copying files. The retained integration-focused.log then shows zero collected tests because the new test file was absent on the unchanged old branch. The user records exit 4 for that command. That record is neither a product failure nor a passing test. The actual candidate suite and AST check supply the relevant evidence. The supplied zsh reserved-variable error occurred before commit and changed no source.

One fresh audit-driver assertion also failed before tests started. It compared an old inline argument with the helper's local variable. The corrected verifier checks the exact assignment expression and call forwarding. [process-errors.md](process-errors.md) records the error and its limit. No product source changed. Audit-script formatting and unused-import cleanup affected only this audit directory. The final 72 controls were repeated after that cleanup.

The following command reproduces the review checks. It refuses a changed head or dirty checkout. The command arrays in commands.jsonl give each actual child command separately. The external audit test uses both `--rootdir` and `--confcutdir` set to this audit directory. Repository tests use the repository root. All tests use the existing private-data guard without modification.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd /Volumes/PhoenixWork/worktrees/m1-ledger-identity
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/Volumes/PhoenixWork/tmp/m2-frame-integration-sol-20261112
/usr/bin/sandbox-exec -f /Volumes/PhoenixWork/audit/continue-v1/review-guard-v3.sb \
  .venv/bin/python -B /Volumes/PhoenixWork/audit/m2-frame-integration-sol-20261112/review_checks.py \
  before source focused independent quality after
```

All production and live gates remain OPEN. A trusted pinned runner must associate the actual process with exact binary, lift, mapping, plan, scope, policy, receipt, raw schema 2 wire, runtime, collector, plugin, QEMU, image, and installed admission identities. Both root addresses need independent classification. The saved root stack target needs an independent entry-time read. It cannot be derived from the later return. Complete accepted-outcome checks must include the declared invocation, stdout, stderr, termination, paths, file bytes, and modes.

Live controls remain required for instruction starts, faithful translation, instruction size, next PC, all guards, root-read calibration, all six register fields, role order, recursion, root closure, reentry, post-root monitoring, counters, limits, exact neutral transit, omitted code, and callbacks. Actual collector mutations must test disabled guards and missing activations. A coherently omitted activation with a rewritten receipt cannot be detected by the pure reducer alone. Runtime association, collector transport, deployment binding, full capture review, and recovery integration remain unapproved.

The fixed public GCC and Clang matrix at O0 and O2 remains required. It must retain both operations, all required lengths, every emitted main call, invalid arguments, early returns, empty and cap inputs, standard I/O errors, and rejected development cases. Separate recursion and four-argument patterns, three repetitions, both independent oracle engines, native x86-64 and AArch64 checks, and complete outcome comparisons remain required. Preserve the archived v1 observer and accepted oracle identities. Public switch-caller source retention does not replace its positive and negative behavior checks or exact replay.

The supported profile contains RDI, RSI, RDX, RCX, RAX, and RSP. Four are argument registers. This review establishes no provider identity, branch conditions, complete indirect target set, or automatic application binary interface inference. General callbacks, tails, nonlocal returns, nonreturn contracts, signals, threads, R8/R9, vector registers, stack arguments, aggregate values, and memory snapshots remain unsupported or unproved. Local output after rejection remains unsupported. Default lazy-resolution rejection remains visible. An eager positive needs its own declared invocation and accepted development outcome.

No program reconstruction success score or new `phoenix-eval` result is supplied. All test counts describe local software controls. They do not measure target behavior or portability. M2 through M4 remain incomplete. SPEC section 9 still requires M4, held-out T0 through T3 results against every baseline, costs, a failure taxonomy, publication of the required artifacts, and replay of every headline result. Sealed adequacy work remains with the separate Author. This PASS closes none of those requirements.

The full AGENTS.md, SPEC.md, installed poteto-mode skill, source, tests, ADRs, required reports, and named supplied logs were read. The Prove It Works principle led to direct Git-object checks, independent policy calculation, executed controls, and final state verification. Its leaf skill was read. Technical-writing and unslop guidance was applied with ASD-STE100 Issue 9. [todo.md](todo.md) records the user limits that replace nested-agent, source-edit, history, and shipping steps.

The requested GPT-6.1 Sol role and Standard service tier are launch settings. This report does not independently attest routing. No provider or safety setting changed. No nested agent, delegation script, model CLI, model-provider call, Docker command, Ghidra process, target execution, network call, commit, push, or tag occurred. No private source, held-out input, archive, Author output or history, private run file, or session history was read. No private-data guard was weakened. All new outputs are in this audit directory or the permitted temporary directory. Final internal free space was 15,697,712 KiB, above the recorded investigation threshold. No storage change was required.
