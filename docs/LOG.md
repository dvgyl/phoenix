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

## 2026-11-10. Corrected M1 measurement and M2 preparation

- Re-read all governing documents after compaction. Main stayed clean at
  `efcad05`. Storage remained above the internal-drive threshold.
- Native CI run `42859828267` passed on its third transport attempt.
  Earlier attempts rejected incorrect CA package bytes. The pinned hash
  stayed fixed. The exact native outcome hashes match Mac M0 run
  `m0-43bba34c9d8d426aa1c029de0e5071c1`.
- Corrected sealed run `m1-t0-efcad05` scored Phoenix 17/20 fully
  successful and Ghidra-raw 8/20. Phoenix behavior passed for 19 and
  integrity passed for 18. Two variants failed `embedded_text`. One
  failed behavior. Twelve raw variants failed compilation.
- Both methods had 792 eligible original cases, zero emulator
  disagreements, and zero evaluation errors. Recovered block entry
  coverage remained 790/1079. All earlier failed or held runs remain.
- The original full model log SHA-256 is
  `728cf1a3f10b21b54c7c747f7dabbbaada85c68b286110d5b865bfe77dd23f44`.
  It records 80 calls and $1.603504 of API-equivalent cost. There are
  zero unknown reservations. Median reconstruction time was 51.893
  seconds across all 20 Phoenix variants. Exact replay and final Astra
  review are active. No M1 tag was made.
- The dedicated T1 author completed 15 programs and 90 stripped variants.
  The lead checked the manifest, all release hashes, ELF contracts and
  aggregate adequacy records. Only permitted metadata was opened.
  Minimum branch coverage was 184/197. Minimum mutation detection was
  11/12. One of 180 non-equivalent mutants survived. Source sizes are
  304 to 316 C LOC. This narrow range is a report limitation.
- The lead committed the author's T1 archive hashes in a separate public
  worktree before any T1 reconstruction. Main remains fixed through M1
  replay. Neither source archives nor held-out contents were opened.
- A fresh T2 author started private design under a separate guard. The
  contract requires 10 independent multi-file programs with a size spread
  across 1,500 to 6,000 real C LOC and at least 20 meaningful mutants each.
  Linux validation is gated until M1 replay finishes. An initial brief
  named the wrong archive root. The lead stopped that process, corrected
  the root to `t2/cases`, and launched a fresh author. No private output
  was read.
- The public trace prototype passed independent source review for runtime
  experimentation. The real fixture build then exposed a host bind-mount
  assumption and a missing writable Clang temporary path. The lead
  reproduced both failures and corrected the fixture transport. All 16
  builds and static plans passed. The parent gate passed 496 tests with
  23 skips and 90.01% evaluator coverage. Live trace calibration remains
  pending in its separate worktree.
- The static lift extension passed the parent host gate with 454 tests,
  26 skips, and 90.06% evaluator coverage. Isolated parent Ghidra runs
  preserved every legacy export field and recovery output. Independent
  review then found invalid storage intervals and register-base records
  that its new reader accepted. A fresh Astra worker is fixing them.
- A new public switch fixture retained indirect jumps under both pinned
  compilers. The first parent check incorrectly required equal target and
  label counts. Ghidra exports the default destination without a label.
  The corrected check confirmed 13 destinations and 12 labels, preserving
  both arrays separately. No target execution was used for this check.

## 2026-11-10. Isolated M2 replay corrections

- Verified all eight original matrix candidate hashes before editing. The
  independent Sol review recorded HOLD. Synthetic coordinator probes reproduced
  both R1 lineage defects. Seven saved-report probes reproduced R2.
- Added corrected-behavior tests before production changes. The first run had
  23 failures and 14 passes. Two further red tests exposed numeric type equality
  in saved summaries and ledger identities. Three red tests exposed inconsistent
  cost, token, and storage-evidence counts at the saved-report boundary.
- Bound every replay ancestor to the same stable report fields. A replay
  ancestor must have reproduced its reference. These checks occur before
  submission capture and held-out archive access. Valid chains retain the
  original ledger identity. Exact chains of failed results remain supported.
- Added M2 saved-report validation for the two result forms, four build
  configurations, tested artifact hashes, integrity evidence, verdicts, case
  and coverage counts, and model token and cost fields. M1 schema 1 and the
  trusted measurement path retain their existing contracts.
- The final focused suite passed 247 tests. It includes exact replay chains
  of failed results. Fourteen real measurement round trips used synthetic compiler
  and oracle boundaries. No target, container, or real provider was run.
- The final scripts/check run passed Ruff, format, strict mypy, and 581 tests.
  It skipped 25 tests. Evaluator coverage was 92.25%. The unchanged nested
  protection test failed because the outer guard denied sandbox-exec with
  exit status 71. The full gate is not green. The parent must rerun it with
  the required sandbox capability.
- R3 capture binding and R4 ledger reconciliation remain separate integration
  gates. Correction review and the parent combined gate remain required. The
  full check result and exact file hashes are recorded in
  `/Volumes/PhoenixWork/audit/m2-matrix-fix-sol/report.md`.

## 2026-11-10. Complete stable M2 replay projection

- The parent full gate for R1/R2 passed 582 tests with 25 opt-in skips and
  92.25% evaluator line coverage. The unchanged protection test passed
  outside the reviewer's outer sandbox. A fresh independent Sol reviewer
  passed that exact correction after the first Sol review had held it.
- Astra closure found B1. Python dictionary equality accepted an integer
  budget and an equal floating-point budget in frozen configuration.
  Direct replay and replay through an ancestor opened synthetic archives
  and reported success. Both new rejection tests failed before correction.
- The parent also reproduced this type mismatch during completed resume.
  Its rejection test failed. The correction serializes the whole stable
  projection and compares saved, live and ancestor configuration with JSON
  types preserved. Non-finite values are rejected. Ancestor and final replay
  still use the same stable projection. Result timing remains excluded.
- All four focused checks passed. They cover three rejection paths and a
  valid full original and replay chain. The parent full gate passed 585 tests
  with 25 opt-in skips and 92.30% evaluator line coverage. Ruff, format,
  strict mypy and the unchanged protection test passed.
- The corrected matrix is retained on its isolated branch. Fresh independent
  review of B1, shared R3/R4 integration, combined source review and new
  measurements remain open. Main remains fixed for exact M1 replay.

## 2026-11-10. Combined evaluation capture guards

- Started this isolated merge from reviewed shared correction `05d362f`.
  Merged reviewed matrix `11da284`. Preserved the T1 hash commitments.
  Resolved coordinator and progress-document conflicts. Kept both histories.
- The coordinator builds the complete ordered task roster before opening its
  binding. It freezes all 260 M2 captures and full-log summaries before any
  archive read. It checks the binding and log before each archive and before
  publication. It reconciles every task summary with the full ledger.
- Each replay ancestor now retains its own capture binding. A modified root
  capture cannot pass through an unchanged intermediate replay. M1 task keys,
  report fields and acceptance rules retain their definitions.
- Added eight integration checks. Seven negative requirements failed against
  exact previous matrix `11da284`. They cover both archive barriers, unknown
  charged and zero-charge attempts, direct and ancestor capture replacement,
  and charge transfer with the aggregate unchanged. The eighth checks the
  full 260-key roster and 130 synthetic model calls before each archive.
- The focused integration suite passed all eight tests. The initial combined
  selection passed 146 tests. The parent full gate passed 655 tests with 25
  opt-in skips and 92.27% evaluator line coverage. Ruff, format, strict mypy
  and protection passed. Evidence is in `audit/m2-evaluation-guarded/`.
- Fresh independent Sol and Astra reviews of this combined source are queued.
  The source stays outside main. No sealed M2 result or acceptance is claimed.
- Main advanced only after the `baae648` exact replay and ledger checks passed.
  Current main `6897e47` has public/native checks active. Original and replay
  measurements with the new automatic guard remain required before M1.

## 2026-11-10. Require no model log in M2 replay ancestry

- Fresh Sol review passed combined base `0ee21d7`. Fresh Astra review held
  two findings. An earlier replay could retain an unreported local model log.
  An early submission checkpoint could also change before the capture freeze.
- Reproduced five Astra ancestry rejection requirements on the exact combined
  base. Five additional parent requirements also failed there. They cover
  earlier and selected replays, including writes during capture, between
  archive reads, and during measurement.
- The evaluator now distinguishes the original pipeline from all replay
  pipelines in its lineage. It requires no local model log in any replay.
  It checks before capture, after capture, before archive access, and before
  report publication. It still validates and uses the original ledger.
- All ten rejection requirements passed after the correction. The parent gate
  passed 660 tests, with 25 opt-in skips and 92.30% evaluator line coverage.
  Ruff, format, strict mypy, and the unchanged protection test passed.
  The initial gate caught a tuple annotation error before the full run.
  Both logs remain in `audit/m2-lineage-no-log/`.
- The correction stays on the isolated branch. The shared capture correction
  and fresh combined Sol and Astra reviews remain open. Main and the active
  guarded M1 measurement stay fixed. No sealed M2 use or acceptance is claimed.

## 2026-11-10. Port capture consistency to the guarded M2 evaluator

- Reproduced all three prior Astra capture mismatch requirements at
  `532d93a`. A new parent control used the real failed measurement branch.
  All four requirements failed before the port.
- The combined coordinator now checks returned submissions against the
  same checkpoint bytes it hashes. It passes the full 260-key roster and
  returned submission map to the shared freeze. The replay ancestry
  correction and both archive barriers stay in place.
- Applied the shared path correction after a fresh Sol reviewer reproduced
  a concurrent symbolic link loop. Four shared path controls pass. No
  archive opens and no report is written when the capture is invalid.
  Fresh independent Sol passed the exact shared M1 correction.
- The first combined gate caught a strict typing error in the new test.
  Corrected the test type. Initial passing gates had 723 and 725 tests.
  The final parent gate passed 726 tests with 25 opt-in skips and 92.38%
  evaluator line coverage. Ruff, format, strict mypy, and protection passed.
  All attempts are retained in `audit/m2-capture-consistency-port/`.
- The port stays in the isolated M2 branch. Fresh combined Sol and Astra
  reviews remain required. Main and its exact guarded M1 replay stay fixed.
  No sealed M2 use or milestone acceptance is claimed.

## 2026-11-10. Verify final replay evidence after rendering

- Fresh combined Sol review of `1cf064b` reproduced a new retry defect and
  two replay publication defects. A retry could accept a previously rejected
  checkpoint. A replay could also publish after a local model log appeared
  during final comparison. A cyclic replay log path caused a traceback.
- The parent reproduced four Sol rejection requirements and four local
  requirements. They cover current and earlier replays, stable comparison,
  report serialization, and cyclic log paths.
- The evaluator now stages the complete report before its final evidence
  checks. It verifies the capture binding, ledger identity, per-task model
  summaries, and absence of replay-local logs before atomic replacement.
  The absence check inspects the directory entry without opening a log
  or following its final symbolic link. Valid replay still uses the
  original ledger.
- All eight focused requirements passed. The complete parent gate passed
  730 tests with 25 opt-in skips and 92.27% evaluator line coverage.
  Ruff, format, strict mypy, and protection passed. Prior failure logs
  remain in `audit/m2-replay-publication/`.
- A separate Astra worker owns the shared durable capture rejection fix.
  The combined evaluator still needs that port and exact independent
  reviews before any new sealed measurement.
