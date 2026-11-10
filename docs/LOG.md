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

## 2026-11-10. Isolated public M2 trace prototype

- Added `experiments/m2_trace/` on `agent/m2-trace-prototype`, based on
  `5695148`. The experiment has a fixed two-unit public fixture, source
  and case commitments, a versioned wire contract, a bounded QEMU API 4
  observer, a strict parser, and a separate image recipe and driver.
- Recorded the official QEMU 9.2.0 archive hash and file licenses before
  implementation. ADR 0018 and THIRD_PARTY_NOTICES describe the reuse.
  The accepted QEMU 8.2.2 oracle and all production paths are unchanged.
- All 31 focused host tests passed. Lint, format, strict type checks,
  host C syntax checks, and shell syntax checks passed.
- The final project host gate reported 422 passed tests, 23 skipped
  tests, and one failure. The outer OS guard blocked the protection
  test with `sandbox-exec: sandbox_apply: Operation not permitted`.
  Evaluator line coverage was 90.01%. No suppression was added.
- No Docker command, target execution, image build, agent, commit, push,
  or tag was used. Runtime calibration and independent review remain
  pending for the parent. This work makes no milestone or sealed result
  claim. The handoff memo is in the external M2 survey audit directory.

## 2026-11-10. Public M2 trace review fixes

- Fixed the four accepted prototype findings. The observer has an exact
  file allowlist for its Docker context. Calibration checks physical call
  targets and the fixed fixture's call counts and order. Positive and
  control observations now use one evidence record constructor.
- Added direct calibration tests for both operations and every fixed case,
  including empty input. Added wrong-target, repeated-call, reordered-call,
  mutant, outcome, and malformed-trace tests. Build-context tests check
  required inputs, import dependencies, and the production ignore rules.
- Expanded C branches, named register indexes and limits, and replaced the
  overloaded return register slot with explicit pending-transfer data.
  Fixture sources, cases, commitments, licenses, and production code are
  unchanged. Moved the work checklist to the external task directory.
- The focused suite passed 103 tests. Ruff, strict mypy, C syntax-only
  checks, and shell syntax checks passed. The full host gate reported
  494 passed, 23 skipped, and one failed test, with 90.01% evaluator
  coverage. The outer guard blocked the nested protection test with
  `sandbox-exec: sandbox_apply: Operation not permitted`, exit status 71.
  No test suppression was added.
- No Docker, VM, target execution, agent, staging, commit, or push was used.
  The parent retains the complete host gate outside the guard, fixed-diff
  review, and all Linux runtime gates. No runtime or shipping claim is made.
  The fix report is in the external M2 survey audit directory.

- The first real public fixture build failed because the VM cannot read
  a worktree bind mount. The builder now streams its fixed source archive
  through Docker standard input. A host transport regression failed on
  the previous script and passed after this change.
- The next build reached Clang and failed because its temporary directory
  was on the read-only root. The script now sets `TMPDIR=/work`, as the
  existing worker build does. All 16 fixture builds and their plans then
  passed. GCC and Clang at O0 and O2 retained the direct stdio calls,
  program call, and indirect byte-operation call. No target was executed.
- The updated parent gate passed 496 tests with 23 skips and 90.01%
  evaluator coverage. The observer image build, live calibration, and
  independent review of the fixture transport correction remain pending.

## 2026-11-10. Public observer runtime calibration

- The separate QEMU observer build failed on an `ldd` file heading.
  Separate calls removed that heading from the library list.
- The corrected image built. Accepted worker and checker tags stayed fixed.
  The observer guest-runtime hash check passed.
- The public calibration passed all 96 positive cases with three repetitions.
  It detected both mutants in every compiler and optimization configuration.
  The parent checked all 296 saved trace hashes and parsed each trace again.
  Each observation matched both oracle outcomes and its fixed plan.
- Public evidence is under `tmp/m2-public-calibration/observation-1`.
  Parent checks are under `audit/continue-v1/observer-*` in the workspace.
  Wrong-API and missing-register runtime controls remain open.
  Independent review is required before integration.

## 2026-11-10. Independent public observer review

- A fresh Standard-service Sol reviewer passed the isolated prototype.
  It checked all 296 trace hashes, 192 agreed oracle pairs, 288 positive
  observations, and eight rejected mutant controls.
- The review ran 104 focused tests and 10 independent synthetic tests.
  It also checked source streaming, temporary paths, library selection,
  isolated imports, stale samples, outcome changes, and synthetic load bias.
  The parent full gate passed 496 tests with 23 skips and 90.01% coverage.
- The parent later ran two additional Linux controls using separate images.
  A wrong plugin API produced no accepted trace. A missing register
  produced a register gap while preserving the original oracle outcome.
  The accepted observer and oracle images stayed unchanged.
  These later controls remain subject to independent review.
- Public artifacts are under `tmp/m2-observer-negative-controls` and
  `audit/continue-v1/observer-negative-controls.*` in the workspace.
  No production trace integration or milestone acceptance is claimed.
