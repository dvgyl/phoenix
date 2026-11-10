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
