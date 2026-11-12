# Session log

## 2026-11-10

- Read the governing instructions and checked access to the empty public
  GitHub repository.
- Mounted the APFS sparse bundle on the external drive and created the
  checkout and cache directories there.
- Installed Python 3.12 in the workspace and installed Rosetta 2 through
  macOS Software Update. The first Colima start waited for Rosetta.
- Started separate Standard-tier Codex processes to study sandbox and
  coverage design.
- Verified that the Docker daemon runs on AArch64 and stores its data on
  the external VM disk. The VM has an active Rosetta registration and
  a disabled QEMU x86-64 registration.
- Added exact outcome comparison. The first quality gate passed 14
  tests, Ruff, and strict mypy.
- Confirmed x86-64 execution through Rosetta in an amd64 container.
- The default Docker policy rejected nested namespace creation. Recorded
  an alternate chroot design for per-test isolation.
- Added a versioned test protocol. The quality gate passed 29 tests.
- Added the isolated Docker worker and public test programs. The local
  quality gate passed 59 tests. The worker images are still building.
- Added native x86-64 and AArch64 CI jobs. CI compares exact public
  outcome hashes across the two architectures.
- Astra found ways that resource limits, persistent inter-process
  communication, emulator selection, and invalid controls could distort
  the public scores. The worker and acceptance checks now reject those
  cases.
- Verified the native AArch64, Rosetta, and distro QEMU sandbox probes.
  The Rosetta launcher uses a private proc mount and preserves signals.
  The distro QEMU package lacks plugins. The upstream plugin-enabled
  build is in progress.
- Both initial native CI jobs rejected a public mutation at compile
  time. Fixed the unused environment lookup in that variant.
- The preliminary Apple Silicon run matched all 16 public cases across
  Rosetta, QEMU, and the AArch64 builds. It detected all 20 deliberate
  mutation builds. Coverage failed in run
  `m0-4561081303ab4545b4c194d9f212922c`, so the run failed acceptance.
- Built the pinned QEMU release with plugin support. Astra identified
  why QEMU's entry address did not identify the original dynamic ELF.
  The corrected collector observed the original executable entry in
  a real public probe.
- The public evaluation now pins worker image IDs for the full run.
  The development case generator keeps mutations that add coverage.
- Apple Silicon run `m0-b4ff3a1a02104fc1bb49bd9057262c4c` passed
  the local harness. It matched 16 cases and detected 20 of 20 mutation
  builds. The native ARM64 CI report matched both Mac outcome hashes.
- The Astra review blocked the candidate because the emulator and
  worker image checks could accept a different handler or stale image.
  The reviewer also reported a nested Priority-tier subreview.
- The replacement candidate checks all active binary handlers and
  binds Docker commands to the verified endpoint. It requires an
  image source hash and checks QEMU in the sandbox gate. All three
  engines passed a separate timeout probe and ran the next case.
- Standard-tier GPT-6 Astra passed the code review of
  `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`. The replacement review
  disabled nested agents and both faster service tiers.
- Mac run `m0-46d58c78e11c4b2793a510f1fe00237f` passed on the same
  commit. Each original matched itself in three trials. Rosetta,
  QEMU, and AArch64 passed their sandbox and timeout checks.
- Native x86-64 and ARM64 passed in GitHub Actions run 42794652145.
  The saved comparison at `audit/m0-ci-4ef231a/compare-all.json` in the
  external workspace contains all three run IDs and matching hashes.
- macOS swap growth reduced internal free space. Stopping the idle
  Phoenix VM restored free space above the baseline. Use 4 GiB for
  the next VM session.
- Verified the published Ghidra 12.2 and Temurin 25.0.5+8 archive hashes
  and recorded both licenses before use. The tools will be installed
  on the external drive.
- Started ingestion, lifting, and integrity implementation in three
  separate external-drive worktrees. Each agent uses Standard service
  and has nested agents disabled.
- Verified the Temurin archive hash and the installed Java version.
- Added the runtime model interface and the private budget ledger.
  Public run `provider-probe-9d3b7e1b24ab4fe2b161b48952045086`
  completed through signed-in Codex. Replay returned the saved
  response from the run log.
- Integrated the ingestion worktree. It validates the ELF format,
  dynamic glibc linkage evidence, and stripping. A read-only check
  accepted the public `bitstats` ELF and reproduced its SHA-256.
- Added a CMake project builder that the pipeline and evaluator can
  share. It builds in an isolated Linux container and checks the output
  architecture. Public probe `build-probe-84249aa65e8d413c9cd57b0d0cac4333`
  built with both compilers on both architectures. Each result ran in
  the test sandbox and matched the expected output.
- Built the macOS ARM64 decompiler from the pinned Ghidra archive.
  The shared installation exported public `bitstats` raw C, p-code,
  control flow, imports, and string references. The public headless
  tests checked the `main` startup evidence and the unresolved target
  of a modified indirect call.
- Started the Standard-tier Astra Corpus Author in a separate external
  worktree. The author keeps source-side evidence and case data private.
- Public probe `public-reconstruction-24660e35059f42e2914b967546600bfb`
  sent the decompiled `bitstats` function and static evidence to the
  Standard-tier runtime model. Its portable C project built four ways
  with zero warnings. Each build matched the 10 public cases. Both
  x86-64 emulators agreed on the original outcomes.
- Integrated the development analysis worktree after checking the code
  and tests. Analysis accepts only matched emulator outcomes with a
  valid QEMU trace. It keeps input variety and coverage gains.
- The revised token scanner passed the first four adversarial probes.
  A second review found problems with aliases, macro expansion, and
  array storage. The scanner is not ready for scoring. The first
  follow-up review could not apply its nested macOS sandbox. The
  replacement used one outer sandbox that blocks the protected paths.
- Added `phoenix run` with private per-stage checkpoints, resume, and
  replay. Resume binds the saved input hash, checkout, and image IDs.
  Replay uses a read-only model ledger. The command backs off when the
  provider reports a usage limit and keeps the stage artifacts.
- Chose compiler-resolved C storage checks after two token-scan reviews.
  ADR 0007 records the pinned Clang interface and the limits of byte
  checks. The independent evaluator and compiler checker are in
  separate worktrees.
- The Standard-tier Astra Corpus Author delivered 10 T0 programs and
  40 stripped variants. Checked the release manifest, all 40 SHA-256
  hashes, and the aggregate adequacy records. The author's minimum
  source branch coverage was 9 of 10. The minimum mutation score was
  8 of 8. The author's worktree could not create the Git index lock.
  The lead agent staged the author's exact archive commitments from
  the worktree. The source and held-out archives remain private.
- Ran `phoenix run`, resume, and replay on public `bitstats` at
  `efc821b4976e4a2e1fdd85565cdf48318ec60b3b`. The replay generated
  identical C and CMake files. The original model log stayed unchanged.
- The Ghidra-raw public probe matched 10 cases across four builds.
  Its compatibility header adds C types, declarations, and an entry
  wrapper. The decompiled function bodies stay intact.
- Added an independent evaluator. It freezes source snapshots before
  opening the committed held-out archive. Its child process can read the
  stripped release but cannot open the protected paths. A Standard-tier
  public model request passed inside this file guard.
- The compiler checker worktree passed its first ARM64 test batch.
  macOS swap growth forced two Phoenix VM stops. One stop interrupted
  the checker's image load. The VM now has 2 GiB of memory. The lead
  agent took over the final checker builds and tests.
- The two pinned checker images passed 38 synthetic checks. Native
  x86-64 and AArch64 CI passed for `2ce518a` in run 42808964131.
- Public run `m1-integrated-public-1ebbdfa6c70f41fb875b6e3a5b273c28`
  matched all 16 public cases for both methods and exposed source-check
  failures. Added the missing `chmod` entry and corrected the raw format
  pointer declarations. Public probe
  `m1-public-integrity-fix-7bf237b0737344e8ad00b00796254157` passed
  the focused retest. The binary data export also identified the exact
  unsigned format in `bitstats`. The earlier signed format matched the
  small public cases by coincidence.
- Astra held the preflight review for pipeline identity, replay
  lineage, artifact mutation, and integrity checks for short tables and
  the newline that `puts` adds. The evaluator now binds the reviewed
  checkout, method, settings, tools, and replay origin. It uses fixed
  bytes and independently replays the frozen development inputs.
- The revised source policy checks original data, external function
  references, and function structure from a separate Ghidra lift.
  It rejects unsupported source and missing evidence. The sealed
  evaluation remains pending.
- The revised checker passed 40 real compiler checks across x86-64 and
  AArch64. The local quality gate passed 241 tests and reached 88.95%
  evaluator line coverage. The opt-in compiler and Ghidra tests run
  separately from the local gate.
- Run `m1-integrated-public-b7ec0dfd2f364770b14e01a0aa327b9d` passed
  behavior and integrity for both public programs and both methods.
  A separate public probe recovered `main` from all four GCC and Clang
  `-O0` variants.
- The first compiler-based follow-up review closed the byte, development
  oracle, implementation identity, and replay findings. It found that
  a string pointer or string index could bypass the literal check.
  The policy now requires original data for every nonempty literal.
  The evaluator freezes the raw lift summary with its input hash and
  checks the summary hash on resume. Repair feedback gives output
  positions and lengths. It keeps original output bytes in the test
  artifacts.

## 2026-11-10 M1 first sealed measurement

- Run `m1-t0-ce6a34d` completed at the reviewed `ce6a34d` revision.
  Phoenix scored 0 of 20 fully successful variants. Ghidra-raw also
  scored 0 of 20. Phoenix passed behavior on 19 variants. Ghidra-raw
  passed behavior on 8. Every submission failed integrity.
- Both methods evaluated 792 original cases. All were eligible. The
  oracle reported zero emulator disagreements and evaluation errors.
  Coverage was 790 of 1,079 recovered block entries.
- Exact replay `m1-t0-replay-ce6a34d` reproduced the stable records.
  The original model log retained SHA-256
  `4180ee08ac59dd63131533e5f636a7e84e1e83627ba737deaf4569fb49023ccc`.
  Replay created no model log. A wrapper used zsh's reserved `status`
  variable after evaluation and stopped before its final check. The
  lead checked the log hash and absence separately, then fixed the
  wrapper variable.
- A Standard-configured Astra review held the M1 tag for the threshold
  miss. It found no demonstrated false score in that report. It also
  reproduced a replay-lineage defect and acceptance of altered cached
  model metadata. The follow-up code preserves replay on resume and
  binds evaluation to a frozen model log identity.
- The first native ARM64 CI run passed. Three native x86-64 attempts
  stopped on snapshot package delivery. One rejected a wrong CA
  bootstrap hash. The other two received HTTP 503 for package files.
  Standard-configured Astra diagnosed the package transport. A separate
  Sol worktree added APT's package-only mirror fallback.
- A synthetic signed repository tested the fallback on APT 2.8.3 in
  both pinned Linux images. It accepted correct package bytes and
  rejected a same-size mutation. An unavailable index and a modified
  index signature both stopped the update. The fallback received no
  index requests.
- The signing probe used the installed GnuPG 2.5.21 tool before its
  prior-art and license entries were added. The entries and ADR now
  record that test-only use. The tool occupies 15,784 KiB on the host.
- Public `-O0` binaries reproduced the byte-match issue. The GCC
  `bitstats` comparison shared 166 bytes of C runtime startup code.
  The largest match in the public matrix was 297 bytes. The strict
  64-byte rejection remains in force.
- Public run `m1-public-hardened-e675da21dc2a43f4ba29dd132b067fd4`
  tested four public original variants against the hardened CMake
  profile. All behavior and integrity checks passed. The checker
  detected typed initializers with 64 and 65 copied code bytes.
- A separate Sol worktree added the development integrity check
  required by SPEC.md section 4.2. Behavior and integrity must both pass
  before repair stops. The evaluator keeps its independent check.
- The lead reviewed each returned diff and ran the full local gates.
  The development integrity branch passed 254 tests with 21 opt-in
  skips. The model log branch passed 285 tests with 21 opt-in skips.
  Their parent-process gates included the protection test that the
  outer-sandboxed workers could not run.
- The original Downloads attachment paths were missing after compaction.
  The lead read the unchanged repository copies of AGENTS.md and
  SPEC.md. Both have been tracked since commit `2623d48`.
- A Standard-configured Sol survey checked QEMU register and memory
  APIs and AFL++ QEMU mode against the current runner. The proposed
  first trace experiment uses public fixtures and a separate trace
  runner. No additional tracing tool was installed.
- The integrated follow-up passed 295 tests with 21 opt-in skips.
  Evaluator line coverage was 89.88%. Ruff and strict mypy also passed.
  The new worker and checker image builds remain pending.
- The next Astra preflight held `e07ec17` for cost accounting and
  development evidence defects. Synthetic tests showed charge erasure
  through an invalid ledger transition, a live model mismatch, mutable
  package costs, trusted saved differences, and annotation changes
  after source testing. Two separate Astra worktrees are fixing these
  paths with synthetic regression tests.
- The package fallback reached an upstream signed-index outage. Both
  native CI jobs failed on indexes, and the local build also stopped.
  Direct probes of the official DNS addresses returned intermittent
  successes, timeouts, and server errors. Restored the previous pinned
  image recipes to use their verified local build cache. ADR 0015 records
  the decision. Clean native builds still depend on the snapshot service.
- The restored image recipes built both worker images and both checker
  images from the verified cache at `9878356`. The pinned source
  checkers passed all 40 integration tests across the two architectures.
- Normal public CLI run `m1-public-cli-9878356` passed behavior and
  integrity. Its replay and plain resume preserved the original model
  log and created no replay log.
- Public controls run
  `m1-public-controls-e07-84666602217d4729a9ef1ca72314462d`
  used the reconstruction library with retained worker and checker
  images. All six variants passed their fixed public behavior cases.
  Five passed development integrity. The GCC decimal variant reached
  the repair limit on a byte match and unsupported diagnostic strings.
  The probe's first summary used the wrong integrity field name. Its
  corrected aggregate reads the saved package reports.
- Public run `m1-public-decimal-profile-5f0189f210fd4772ab5155335d0fb73a`
  compared the same candidate with empty static-assertion messages at
  `-O0` and `-O2`. Both passed behavior across four builds. The first
  failed the exact-byte check, and the second passed integrity.
- Added a fixed optimized profile and explicit literal constraints.
  The durable Docker regression failed at the byte-window assertion on
  the previous GCC profile. All four compiler and architecture tests
  passed under the new profile.
- Integrated the Astra accounting fix. Complete histories have one
  start and at most one terminal event per attempt. Live and cached
  responses use the same validation. The evaluator derives tokens
  and costs from the bound log, including failed submissions. It freezes
  package report metadata separately.
- Integrated the Astra development evidence fix. Checkpoint loading
  derives differences from outcomes and binds the development cases.
  Verification requires all four distinct build configurations. Packaging
  copies the exact tested source snapshot. Historical source comments
  direct the reader to the report for final function confidence.
- The combined parent-process gate passed 367 tests with 23 opt-in
  skips and 90.00% evaluator line coverage. The new independent review
  and Linux public integration run remain pending.
- Recorded the upstream reuse survey with pinned source references,
  licenses, and open permission questions. Primary papers qualify
  several claims in the specification's prior-art table. Optional
  experiments stay on public fixtures.
- Astra verified closure of all five earlier preflight findings at
  `6c73a7a`. It found one new recovery defect. An interruption during
  report capture could turn a valid project into a permanent failure.
- Submission evidence now stages in a private directory. One rename
  publishes the source, report, development evidence, raw lift, and
  submission record together. Interruptions and I/O faults before or
  after publication converge to a valid completed capture on resume.
- The evaluator now records wall time from the first pipeline invocation
  through final pipeline completion, including waits. Failed tasks have
  timing records too. Invalid timers stop capture.
- The new interruption regression failed on the previous code for both
  methods with `invalid-project`. The fixed parent gate passed 392
  tests with 23 opt-in skips and 90.01% evaluator line coverage.

## 2026-11-10. M1 measurement, replay, and baseline correction

- Re-read the complete repository instructions and specification after
  compaction. Main was clean and pushed at `5695148`. All four worker
  and checker image builds passed from the verified cache.
- Independent Astra preflight passed that revision. The lead ran its
  80 synthetic regression tests. All passed. The Linux compiler-integrity
  suite passed all 44 checks.
- Public run `m1-public-matrix-5695148-e8d8134ccd5a40a4b60e3f63d06cac95`
  used the normal guarded command path. It covered 14 original variants
  and both methods. Phoenix passed behavior and integrity for all 14.
  Raw passed zero. All submissions were captured before measurement.
- Native CI run `42837009179` passed on both architectures after one
  ARM64 retry for Ubuntu snapshot HTTP 503 errors. Mac M0 run
  `m0-661c1aae6ac84a3a86a37e6f466217a3` matched native x86-64 run
  `m0-ac3140b377c248ce89abf2c45219f1f0` and native ARM64 run
  `m0-40f1d15a47364e52a205d9145defb376`. The scripted comparison is
  saved under `audit/m1/ci-5695148/compare-all.json` in the workspace.
- Sealed run `m1-t0-5695148` scored 17 of 20 fully successful Phoenix
  variants. Behavior passed for 19, and integrity passed for 18.
  Two variants failed `embedded_text`. One failed behavior. Raw scored
  zero fully successful variants and zero behavior passes.
- Both methods had 792 eligible original cases, zero emulator
  disagreements, and zero evaluation errors. Coverage was 790 of 1,079
  recovered block entries. The first `ce6a34d` result and its replay
  remain in the record.
- Replay `m1-t0-replay-5695148` reproduced every stable result field.
  The complete original model log SHA-256 stayed
  `13fea13ce172e21cb02fc4ffa864a5cef8759d79d9c90ce4f40efce529ed0e6b`.
  The replay created no model log. Original accounting was 66 calls
  and $1.5418888 of API-equivalent model cost, with zero unknown-cost
  reservations. Median reconstruction time was 46.676 seconds across
  the 20 Phoenix variants. Timing is excluded from stable replay fields.
- Final independent Astra review held the milestone. The raw header
  declared two format arguments as `const void *`. Fortified glibc
  declares them as `const char *`. This support-code defect prevented
  every GCC baseline build at the fixed profile. The raw zero score
  needs a corrected measurement. The review preserved the Phoenix score
  and all three Phoenix failures. The declarations are in the
  [glibc 2.39 header](https://raw.githubusercontent.com/bminor/glibc/glibc-2.39/libio/bits/stdio2-decl.h).
- Corrected the declarations at `ff4e427`. A public host syntax
  regression failed before the change. The same defect failed all four
  Linux compiler and architecture combinations. After correction, the
  host gate passed 393 tests with 25 opt-in skips and 90.01% evaluator
  coverage. All 48 Linux compiler-integrity checks passed. The fixed
  build profile and all integrity thresholds retain their values.
- Main stayed fixed during exact measurement and replay. The next
  candidate needs a public command check, independent preflight, sealed
  measurement, replay, and final milestone review.
- A separate Standard-configured Astra task designed a public trace
  experiment. A Sol worker prepared its isolated prototype. Parent host
  verification passed 423 tests. Independent review found a build context
  error and three calibration or reporting defects. A fresh Astra worker
  is fixing those findings in the separate worktree. Runtime calibration
  and production integration remain pending.
- A metadata-only Sol survey found the official `gpt-6.1-sol` knowledge
  cutoff of 2026-04-30. The lead checked the same model page. Seven T3
  metadata candidates remain unqualified. A separate author must check
  publication history and the full input contract before selection.
  [Official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
- A dedicated Astra Corpus Author started private T1 preparation. Its
  guard passed synthetic allow and deny checks. Source and held-out
  contents stay in its private namespaces. Linux validation was gated
  until the M1 replay and public compiler regression completed. Only
  aggregate status and permitted release metadata reach the lead.

## 2026-11-10. Exact replay failure and repair feedback correction

- Continued from `origin/agent/thread-handoff`. Main stayed at `efcad05`
  until its replay checks and final Astra review finished.
- Original run `m1-t0-efcad05` scored Phoenix 17/20 and raw 8/20 fully
  successful. Phoenix had two integrity failures and one behavior failure.
  The corrected raw header closed the earlier baseline review finding.
- Replay `m1-t0-replay-efcad05` did not reproduce. One stable record changed
  from a measured behavior failure to `pipeline-failed`. The other 39
  records matched. Final independent Astra review returned HOLD.
  Matching success counts did not satisfy the exact replay requirement.
- The full original model log stayed unchanged at SHA-256
  `728cf1a3f10b21b54c7c747f7dabbbaada85c68b286110d5b865bfe77dd23f44`.
  Replay created no model log. Both frozen reports remain intact.
- An independent Standard-service Sol worker proved the development cause.
  CMake elapsed-time text changed the next repair request. Exact ledger
  lookup correctly raised `ReplayMissing`. The parent reran all six
  synthetic diagnosis tests. All six passed without provider calls.
- A separate Sol worker removed only the known CMake timing suffixes from
  failed-build feedback before truncation. Raw diagnostics retain their
  values. No source, outcome, ledger, or integrity check was relaxed.
- The regression first produced six expected `ReplayMissing` failures.
  The corrected focused suite passed all nine tests. The parent full
  quality gate passed 401 tests with 25 opt-in skips and 90.01% evaluator
  coverage. The unchanged protection test passed in the parent process.
- A fresh independent Standard-service Sol reviewer passed the exact diff.
  It ran the nine focused tests and 28 independent probes. It reproduced
  the six timing failures with the base function. This review does not
  certify M1. A new candidate measurement and exact replay are required.
- The defect is tracked in
  [issue 1](https://github.com/dvgyl/phoenix/issues/1).
  Full review and test evidence remain under `audit/m1/` in the workspace.
- Established a fresh independent Sol review after every major work block.
  Astra milestone, algorithm, and integrity roles remain required.
  All new CLI workers request Standard service. Fast mode and nested
  agents are disabled. Source and held-out material stay private.

## 2026-11-10. Evaluation capture binding and complete accounting

- Worked only in `worktrees/m1-follow-up-review-e07ec17` at `baae648`.
  Main remained frozen. No commit, push, delegation, or real evaluation ran.
- Reproduced inherited findings R3 and R4 with the actual M1 coordinator and
  synthetic captures, opaque bytes, and archives. R3 replaced a completed
  report's source hash after a source and checkpoint change. R4 omitted a valid
  task charge while the complete model log hash still matched. These probes
  do not establish real source manipulation, real costs, or a budget bypass.
- Added a separate capture binding for the complete ordered task roster and
  every captured file. Check it on resume, before archive access, and before
  report publication. Preserve atomic capture and freeze publication.
- Added strict roster validation for the complete model log. Require each
  reported summary to match the corresponding complete-log summary. Preserve
  failed-call reservations and all existing accounting validation.
- ADR 0021 records the data shape and compatibility limits. Older checkpoints
  without the binding cannot migrate to this engine. Historical runs must use
  their recorded revisions. Schema-1 report fields and scoring remain unchanged.
- Synthetic regression and property tests cover replacement, interruption,
  archive access, completed-report preservation, replay, and full accounting.
  Detailed commands and outcomes are in
  `$PHOENIX_ROOT/audit/evaluation-freeze-accounting`.
- The focused suite passed 167 tests. Ruff, format, and strict mypy passed.
  `scripts/check` reported 442 passed, 25 skipped, and one failure. Evaluator
  coverage was 90.29%. The unchanged nested sandbox test failed because the
  outer guard denied `sandbox_apply`. It was not excluded or modified.
- Independent Sol review, Astra closure review, the full parent gate, combined
  M2 integration review, and new candidate measurements remain parent gates.
  No benchmark score or M1 acceptance is claimed.

## 2026-11-10. Capture schema and replay type correction

- The parent full gate for the initial binding correction passed 443 tests
  with 25 opt-in skips. The unchanged protection test passed outside the
  reviewer's outer sandbox. Evaluator line coverage was 90.29%.
- Independent Astra review closed R3 and R4 within their isolated scope.
  Independent Sol review held the binding reader. Boolean and floating-point
  schema values and duplicate JSON fields were accepted. Eight rejection
  regressions failed before the correction and passed after it.
- The binding reader now rejects repeated fields at each JSON object. It
  requires an integer schema value of 1. Raw binding bytes remain the frozen
  identity. There is no checkpoint migration or retrospective binding.
- Astra also found that the separate M2 stable projection used Python
  dictionary equality for configuration values. The parent reproduced the
  same weakness in M1. An integer and equal float, or a Boolean and equal
  integer, could compare as equal. Two M1 rejection regressions failed.
- Configuration and model-summary comparisons now use JSON serialization
  with sorted keys and non-finite values prohibited. This preserves JSON
  types. Existing stable result fields and exact model lookup are unchanged.
- The corrected focused suite passed 52 tests. The parent full gate passed
  453 tests with 25 opt-in skips and 90.39% evaluator line coverage. Ruff,
  format and strict mypy passed. Evidence is in
  `audit/evaluation-freeze-schema-fix/` outside the repository.
- Fresh independent Sol and Astra review remain required for this exact
  correction. Combined M2 integration and new measurements remain open.
- At unchanged main `baae648`, public pipeline checks passed for both methods
  in all four build configurations. Native CI run 42883642379 passed. The
  native AMD64 and ARM64 M0 reports matched the current Mac M0 report.
- Original `m1-t0-baae648` finished with Phoenix 17/20 and raw 8/20 fully
  successful. Phoenix retained two `embedded_text` failures and one behavior
  failure. Raw retained 12 compiler failures. Both methods had 792 eligible
  cases, zero emulator disagreements and zero evaluation errors. Coverage
  was 790/1079 recovered block entries. Its exact replay is active.
- The original model ledger has 69 calls and $1.4249648 API-equivalent cost.
  Its SHA-256 is
  `56f1b86a7056cb03d2a3607ac4dae09bdbd1e6051f4baafa845fd9ed4a73851e`.
  Unknown-cost reservations are zero. This run predates automatic capture
  binding. No retrospective binding or milestone acceptance is claimed.

## 2026-11-10. Completed M1 resume configuration check

- Fresh independent Sol review passed the nine-file shared candidate.
  It ran 65 fresh coordinator checks and 205 selected regressions.
- Fresh Astra review held A-F1. Completed M1 resume checked ledger identity
  but omitted the saved report configuration. Equal integer/float and
  false/zero substitutions opened the archive and replaced the altered
  report. The parent reproduced both failed rejection requirements.
- The coordinator now reads the completed report once and compares its
  configuration before capture reuse or archive access. It uses the existing
  type-preserving JSON comparison. Ledger identity is checked as before.
- Both rejection cases now pass. Tests also require no new capture, no
  archive read and unchanged report bytes. The focused suite passed 54 tests.
  The full parent gate passed 455 tests with 25 opt-in skips and 90.40%
  evaluator line coverage. Ruff, format, strict mypy and protection passed.
- Evidence is in `audit/evaluation-completed-resume-fix/`. Fresh Sol and
  Astra review of this exact correction remain open. Prior HOLD reports
  remain intact. Main and its active exact M1 replay remain unchanged.

## 2026-11-10. Final shared evaluation review

- Fresh independent Astra review passed the exact final nine-file candidate.
  It reran six prior rejection requirements, 37 fresh coordinator controls,
  68 preservation cases and 281 selected regressions. A-F1 is closed.
- A different fresh independent Sol review also passed the exact candidate.
  It ran 40 fresh probes and 281 selected regressions. Both reviewers checked
  unchanged hashes before and after review. Both retained their separate
  outer-guard protection failure. The parent full gate passed that test.
- Reports are in `audit/evaluation-resume-closure-astra/` and
  `audit/evaluation-resume-final-sol/`. Earlier HOLD reports remain intact.
- Retained the reviewed correction on its branch. Main stays at `baae648`
  through its active exact replay. The correction still needs public/native
  checks, a new original evaluation, exact replay and milestone review.
  Combined M2 integration also requires a full gate and fresh reviews.

## 2026-11-10. Exact timing-correction replay and shared integration

- Exact replay `m1-t0-replay-baae648` reproduced every stable field from
  `m1-t0-baae648`. Both retain Phoenix 17/20 and raw 8/20 fully successful.
  Phoenix retains two `embedded_text` failures and one behavior failure.
  Raw retains 12 compiler failures. Both methods have 792 eligible cases,
  zero emulator disagreements and zero evaluation errors. Recovered block
  coverage remains 790/1079.
- The original model log stayed unchanged at SHA-256
  `56f1b86a7056cb03d2a3607ac4dae09bdbd1e6051f4baafa845fd9ed4a73851e`.
  Replay created no model log. All 40 per-task summaries reconcile with
  the complete log. Original use is 69 calls and $1.4249648 API-equivalent
  cost, with zero unknown-cost reservations.
- An independent read-only capture observation remained unchanged. It was
  made during the original run. It does not prove a freeze before held-out
  access. No historical run file was modified or given a new binding.
  Full evidence is in `audit/m1/final-baae648/`.
- Kept main and accepted images fixed until exact replay and these checks
  finished. Then integrated reviewed shared correction `05d362f` by a
  fast-forward merge. The parent gate and both fresh independent reviews
  passed. A new guarded original and exact replay are still required.
  No M1 tag or milestone acceptance is claimed.
- Pushed matrix `11da284` and observer helper `c76cc59` on separate branches.
  Final matrix Sol and Astra reviews passed. Its merge with the shared
  guards is isolated and uncommitted. Combined review remains open.
- Started the reusable observer controls after the replay released the VM.
  A separate Sol worker is implementing the stripped-binary evidence adapter
  from the completed Astra design. Private Astra authors are preparing T2
  and qualifying T3. Their sources and detailed logs remain sealed.

## 2026-11-10. Accept M1 at the measured revision

- The guarded original and exact replay at `6897e47` each returned
  Phoenix 17/20 and Ghidra-raw 8/20 fully successful. The threshold is
  16/20 Phoenix variants. All 40 stable rows and all stable report fields
  match. Each method measured 792 eligible cases with no emulator
  disagreements or evaluation errors. Coverage is 790/1079 recovered
  block entries.
- Phoenix retains two `embedded_text` failures and one behavior failure.
  Raw retains 12 variants with compiler errors. Phoenix compiled 80/80
  rebuilds with eight warnings. Raw compiled 48/80 rebuilds. Every
  compiled raw rebuild matched its eligible cases.
- The parent checked the checkpoint hashes and report fields for all 40
  rows in each run. Both bindings stayed unchanged. Every model summary
  reconciles with the complete original log. The log stayed unchanged
  at SHA-256
  `ceed478c6f304e4cb388bc6b8599b475ea5e8b701f9d76e1d1b3c7024a2771db`.
  Replay created no model log. Original cost is $1.7865956 API-equivalent
  across 86 calls, with no unknown-cost reservations.
- Public pipeline checks passed for both methods in all four build
  configurations. Native CI run 42905864046 passed. Both native M0
  reports match Mac run `m0-3df6909b7713419c9e23110752fb9c4f`.
- Independent Astra and Sol passed the exact measured source and frozen
  evidence. The known pre-freeze checkpoint defect and the later
  synthetic retry defect do not invalidate these checked results.
  Both actual invocations exited zero with no recorded rejected attempt
  or restart. Preserve the defects and correct them before future sealed
  measurement. The verdict does not claim general filesystem integrity.
- The `m1` tag identifies the measured commit only. Do not assign these
  results to a later evaluator revision. Earlier HOLDs remain valid for
  their own runs. Frozen category, binding, and review evidence is under
  `audit/m1/final-6897e47/` and both milestone review directories outside
  the repository. No sealed source or held-out input was published.
- The Linux VM then built all 16 public E1 fixtures. Private T2 validation
  now has the VM. Host static checks passed the exact E1 fixture matrix.
  M2 evaluation and production recovery remain open.

## 2026-11-11. Preserve accepted capture evidence on retry

- Integrated the shared capture checks from the reviewed checkpoints
  `f5f0608` and `99d581b`. The exact source, tests, and capture ADR
  match the latter branch. The original and replay measurements stay
  at `6897e47`, and the `m1` tag does not move.
- The capture reader parses and hashes the same bytes. The freeze
  compares them with the returned submission before opening held-out
  archives. A contradiction creates a separate rejection marker and
  blocks retry. It does not overwrite the existing binding.
- Independent Sol and Astra reviews passed the exact source and test
  files. The isolated parent gate passed 533 tests, 25 opt-in skips,
  and 90.59% evaluator line coverage. Preserve all earlier failed
  evidence. No new sealed result is claimed.

## 2026-11-11. Integrate reviewed static lift evidence

- Integrated the exact U1 source, tests, schema, and ADRs from
  `49202a7`. Independent Sol and Astra reviews passed. The local
  publication check for the shared evaluator had one test deadline
  failure under concurrent load. The serial retry passed without a
  code change. Keep the first failure in the session record.
- The mapping companion checks Ghidra instruction addresses against
  original ELF file spans. The opt-in plan binds supported import
  transfers to their original instruction and relocation evidence.
  Unproved transfers remain gaps.
- The public static gate used GCC and Clang for 16 PIE, fixed-entry,
  PLT, GOT, standard, and split-layout combinations. It retained
  1,404 original instruction witnesses. The exact controls and prior
  transport failures are recorded in `audit/m2-production-u1-e1/`.
- This integration does not enable switch recovery or production
  traces. No target execution or new benchmark result is claimed.

## 2026-11-11. Integrate reviewed static switch evidence

- Integrated the exact recognizer files from `4978a41` and optional
  graph publication files from `81c9cfe`. Fresh independent Sol
  review passed both static blocks. Preserve all earlier HOLDs.
- The recognizer uses admitted original instructions, a read-only
  table, and known transfer evidence. It assumes ordinary function
  entry and return behavior. It retains every proved selector,
  including repeated destinations.
- The optional export binds graph files to the same lift generation.
  The saved public GCC and Clang plans retain all 24 cases and both
  defaults. The ordinary lift bytes match the earlier exports.
- Production C generation does not use this evidence yet. The
  default pipeline and M1 tag are unchanged. No target ran or
  new benchmark result is claimed.

## 2026-11-11. Integrate the reviewed M2 evaluator

- Integrated exact evaluator source, tests, and evaluation ADRs from
  `05979af`. Independent Sol and Astra reviews passed. Keep earlier
  HOLDs and timing failures. The M1 tag stays at `6897e47`.
- The evaluator fixes the T0 and T1 roster, verifies the exact replay
  ancestry and origin log, and checks bound evidence before each archive
  and report publication. A replay cannot select a new ledger identity.
  Restore the exact origin bytes before resuming an interrupted replay.
- Integrated only the committed T1 archive hashes and allowed aggregate
  records. No sealed source or held-out input was read. The Linux VM
  still belongs to private T2 validation. Worker refresh and public
  checks are required before the next sealed measurement.
- This is evaluator code approval. No M2 milestone result or tag is
  claimed.

## 2026-11-11. Remove a Mac-only path from the replay tests

- Both native CI jobs for `3880478` failed in the same 13 replay property
  tests. The tests required `PHOENIX_ROOT` and a scratch directory named
  for an earlier review. The evaluator code did not cause the failure.
- Reproduced the failure with `PHOENIX_ROOT` unset. Replaced the test path
  with the standard temporary directory. All 13 affected tests then
  passed with the variable unset. On the Mac, `TMPDIR` still points to
  the external workspace. The measured M1 revision remains unchanged.

## 2026-11-11. Integrate the reviewed observation wire reader

- Fresh Sol passed the exact structural reader at `b09c23d`.
  Its 14 existing tests and 596 added controls passed. The reader
  checks the wire structure and identity. It does not establish
  runtime mapping, frame validity, accepted outcomes, or live support.
- Integrated the exact reader and tests. The static observation plan
  remains on its isolated correction branch. No target ran.
- The same Sol review passed the test portability correction at
  `53ee7de`. Native CI run 42943227090 passed on x86-64 and ARM64.
  The native outcome comparator passed. Both downloaded artifact
  hashes match GitHub's digests.
- Native public case counts and full outcome digests equal the
  historical Mac M0 run. The three-mode comparator correctly rejected
  different evaluator revisions and worker sources. Do not count this
  as a same-revision Mac check. That check still needs refreshed images
  after the private author releases the Linux VM.

## 2026-11-11. Integrate reviewed checked switch generation

- Fresh Sol passed source observations at `1a5df5b`, schema 3
  publication at `5ede39e`, and bounded binding, emission, and the
  protected writer at `328b4f0`. Earlier HOLDs remain in the audit.
  Integrated the exact reviewed source, tests, and two ADRs.
- The reader proves exact identified UTF-8 source slices. The bounded
  parser proves complete C syntax and exact marker correspondence.
  Schema 3 binds ordinary and normalized artifacts to one generation.
- The emitter retains every proved label and the unchanged arm, break,
  and return bytes. Protected definitions and typed data precede model
  declarations. The model cannot replace those definitions in cleanup
  or repair. Both saved public fragments and writers passed the review.
- Fresh controls rejected stale source, conflicting markers, wrong
  selectors and data widths, aliasing, relocation overlaps, changed
  protected bytes, and model replacements. Legacy initial and repair
  prompts and project bytes stayed identical in direct comparisons.
- The runtime pipeline caller remains isolated. No Linux behavior or
  new evaluation result is claimed. M2 acceptance remains open.

## 2026-11-11. Integrate reviewed physical transfer admission

- Fresh Sol passed `4697be6`. It reproduced the corrected false-call,
  skipped-thunk, replaced-proof, and continuation controls. The prior
  HOLDs stay unchanged. Integrated the reviewed plan, classifier, and
  tests. No target ran.
- The shared import file also needs the switch proof's relocation
  write-size metadata. A direct patch failed because main had a
  different earlier binder. A three-way application exposed three
  binder conflicts. Selected the reviewed binder in those conflicts.
- Compared the combined import file with `4697be6`. Its only two
  additions are the existing relocation write-size field and the
  existing width value returned by the relocation reader. The
  combined focused suite passed all 277 tests.
- Shared proof revalidation and physical byte classification now gate
  import and observation plans. Static imports still identify symbol
  requests only. Live capture, runtime mapping, and frame admission
  remain open. No M2 result or new milestone tag is claimed.

## 2026-11-11. Integrate the reviewed opt-in switch caller

- Fresh Sol passed the exact caller at `d3485cd`. It passed 96
  focused tests and 81 fresh controls. It checked malformed generation
  selectors, source and settings changes, per-function gaps, repair and
  replay persistence, and final source identity. Integrated the exact
  caller, tests, README option, and ADR 0027.
- The new option remains off by default. It cannot change Ghidra-raw.
  Resume and replay retain the recorded value. The checked path reads
  one schema 3 generation and passes its retained definitions through
  every cleanup and repair. The package remains the tested snapshot.
- Both actual saved public plans retain their complete protected
  source and 12 selectors. Host syntax checks and synthetic orchestration
  do not establish target behavior. Public dual-oracle, four-way build,
  unvisited-case, and duplicate-destination gates remain open.
- The earlier combined main transfer plans also matched all 16 reviewed
  public plans byte for byte. Their proof and relocation-width metadata
  stayed consistent. No target ran or sealed result changed.

## 2026-11-11. Integrate the reviewed observation mapping gate

- Fresh Sol passed the exact mapped-observation gate at `d5e1870`.
  It passed 42 existing observation tests and 113 fresh controls.
  Integrated the exact source, tests, and ADR 0029.
- The gate binds raw wire, source, plan, invocation, and runtime identity.
  It requires the full supplied observer outcome to match the accepted
  development outcome. It checks runtime bias, executable ranges,
  opaque external targets, event roles, and transfer confirmations.
- An internal target identifies executable bytes. It does not establish
  an instruction start or function entry. The mapped result does not
  admit frames, target closure, runtime calibration, or inference.
  A later collector and receipt must bind actual capture evidence.
- No target ran. The separate Corpus Author health check reported a
  healthy bounded validation batch, progress, and no owner action.
  The Linux VM remains private. Source and held-out inputs stay sealed.

## 2026-11-11. Allow the native image checks to finish

- Native run 42954976284 passed its arm64 job. The amd64 job passed the
  source gate and worker image build. It reached the 30-minute job limit
  while downloading pinned integrity toolchain packages. The log reports
  cancellation at 04:17:07 UTC. No amd64 M0 report was produced.
- Increased the native job limit to 60 minutes. Every existing build,
  integrity, M0, and outcome comparison step remains required. The package
  pins and verification rules remain unchanged. The new run must pass.

## 2026-11-11. Integrate the reviewed public switch driver

- Fresh Sol passed the complete public caller gate at `63515a7`.
  Its host checks passed 497 tests with one optional Ghidra check skipped.
  All 64 independent host controls passed. These are software controls.
  No target, model provider, Docker command, or Ghidra process ran.
- Integrated the exact reviewed source and tests. Clarified the source
  check as byte retention. An inactive definition can retain those bytes.
  The complete driver keeps both positive and negative behavior checks.
- The 56-case public roster has 53 development cases. Selector 11 remains
  unvisited during development. All four builds, both oracle engines,
  exact replay, and the compiled negative control remain required.
- The Linux VM stays with the private T2 Author. The option remains off
  by default. No new sealed measurement or later milestone is accepted.

## 2026-11-12. Prepare scope and pure-frame integration

- The owner resumed the complete SPEC section 9 goal. The parent checked
  the canonical checkpoint, all ten pending files, branch tips, workers,
  VM state, and storage before it removed the pause marker.
- Both exact scope dependency ports passed full checks and commit hooks.
  Frame `94caeb4` and capture `a2af90c` are pushed and clean. The ADR is
  tracked in both. Fresh independent Sol dependency review is running.
- This isolated candidate copies exact scope, pure-frame records, reducer,
  tests, and ADR bytes from `94caeb4`. Six shared files match main exactly.
  The shared mapping reader differs only by an extracted selector helper.
  Abstract syntax tree checks confirm unchanged selector validation and
  all other module definitions. Current main mapping code is retained.
- The policy digest must use the installed source. No old certificate is
  copied or accepted by this integration. No frame algorithm changed.
- The raw capture boundary remains on its isolated branch. Its full
  review is open after provider screening. The parser-only PASS does
  not close that review. All live collector gates remain open.
- The corpus remains agent-sealed on an honor system. Separate private
  Authors resume T2 validation and T3 source qualification. The parent
  reads only approved aggregate status and handoffs.
- Internal free space crossed the required threshold. The parent moved
  the inactive Homebrew download cache to external storage. All 3,785
  file and link records matched. The original path resolves through a
  link. Internal free space recovered above the required threshold.

- The combined scope, frame, mapping, plan, wire, and transfer suite
  passed all 1,009 tests. The earlier preflight refusal changed no source.
  A test command on the unchanged old branch collected no tests because
  the new files were absent. The corrected command tested this candidate.

## 2026-11-12. Reconstruct complete static collector data

- This delegated unit adds only `collector_data.py`, its synthetic host
  controls, and ADR0035. The raw boundary rebuilds complete plan and scope
  records with installed policy bytes. It preserves all nested fields.
- Frozen data includes checked ELF geometry, exact transport limits, and
  every source record. Canonical output has an incremental 16 MiB bound.
  Caller-supplied lower limits remain binding. Snapshot width is eight.
- The initial collector suite passed 88 tests. Expanded controls passed
  119 tests. The combined affected suite passed 1,128 tests. Two later
  metadata controls passed in the final 121-test collector suite. Final
  affected checks are recorded in the external implementation report.
- Initial lint found 42 issues before formatting and import cleanup.
  Strict mypy found two dynamic replacement annotation errors. A later
  mypy run found two intentional invalid-address fixture annotations.
  All were corrected. No product test failed in those runs.
- Full capture review remains OPEN after provider screening. The pure
  data unit issues no runtime authority or tree admission. Renderer,
  independent decoder, build issuance, native collection, calibration,
  and production gates remain separate work. The supervisor owns review,
  the full gate, commits, and integration. No Git write was performed.
- Final affected checks passed all 1,130 tests. Ruff check, Ruff format
  check, strict mypy, and the whitespace diff check passed with exit 0.
  Only the five allowed worktree paths changed. Independent review and
  the supervisor's complete quality gate remain required.

- The parent read the complete module and implementation report, checked
  the exact allowed diff, and confirmed unchanged earlier implementation
  files. The parent repeated all 1,130 affected tests successfully.
  The full commit gate and fresh independent Sol review remain required.

## 2026-11-12. Render and decode complete typed collector headers

- This delegated unit adds fixed declarations, the bounded pure renderer,
  an independent reader, synthetic host controls, and ADR0037. Every
  complete logical table has a fixed directory entry. No runtime code
  or production integration is added.
- The source reader decodes complete immutable records. It validates
  tags, slices, byte lengths, table references, and the complete directory.
  Tests compare the result with the original complete logical record.
  Shared call routes retain distinct route identities and path positions.
- Geometry retains an exclusive end of `2**64` through a start/size pair.
  A size of `2**64` explicitly refuses. Signed tag/magnitude fields retain
  `INT64_MIN`. Caller limits remain binding before table materialization.
- The first header suite had 13 test failures and 432 passes. The failures
  came from tuple/list comparisons, invalid fixture construction, and an
  equal gap limit. Corrected controls passed all 445 tests. The expanded
  suite had one diagnostic-message assertion failure and 467 passes.
  The affected suite then passed all 1,389 tests. Early lint and strict
  type-check failures were corrected. The external report retains them.
- Four headers passed C11 syntax-only checks with warnings treated as
  errors. All fixed structure sizes matched their logical storage sizes.
  No link, target execution, VM access, Docker, Ghidra, model call, nested
  agent, commit, push, tag, or branch change occurred.
- Full capture review remains OPEN after provider screening. Independent
  review, compiled-data inspection, trusted build issuance, native
  collection, calibration, and production admission remain required.
  These host checks are not Phoenix evaluation results.
- Final affected checks passed all 1,391 tests after the fixed-source read
  failure controls. Ruff check, Ruff format check, and strict mypy passed
  with exit 0. The exact allowed diff and unchanged documentation prefixes
  were checked before return. The external report records final hashes.
- Final source review found missing internal reference checks. The renderer
  now compares continuation users, disposition route IDs, omission metadata,
  and guard roles with the complete retained records. Five new rejection
  controls passed. The affected suite passed all 1,396 tests with exit 0.
  These checks establish internal consistency and grant no runtime authority.

## 2026-11-12. Parent check of the typed collector header

- The parent read the full worker report, renderer, independent reader,
  fixed C declarations, and ADR. The source hashes match the report.
  Every previous implementation file remains unchanged.
- The parent inspected the complete record and table contract and selected
  controls. All 1,396 affected host tests passed again. Four separate C11
  syntax-only checks passed. No original or reconstructed target ran.
- The data dependency passed fresh Sol review at exact `63dd985`. The
  worker report retained its earlier open-review statement. Its source
  stayed unchanged after that independent data review.
- The directory references all 47 typed tables. Complete source decoding
  and syntax checks do not prove compiled retention. Actual plugin data
  inspection, trusted issuance, launch identity, calibration, full capture
  review, and production gates remain open.
- Full commit checks, fresh independent Sol review, and mandatory Astra
  critical review remain required before reliance on this unit.
