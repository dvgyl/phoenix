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
