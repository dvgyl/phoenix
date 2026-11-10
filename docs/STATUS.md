# Phoenix status

M0 passed on commit `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 starts with binary ingestion, Ghidra lifting, and output integrity.

Apple Silicon run `m0-46d58c78e11c4b2793a510f1fe00237f` matched
16 public cases and detected 20 of 20 mutation builds. It reached
30 of 45 recovered block entries in `bitstats` and 30 of 51 in
`filemarks`. The native reports have the same exact outcome hashes.

- Native x86-64 run `m0-8e0df68331b946d298d3b6f6ec25b09f`.
- Native ARM64 run `m0-63fc6335bda44a55a1894926d30644db`.
- [Continuous integration run 42794652145](https://github.com/dvgyl/phoenix/actions/runs/42794652145).

The baseline for free space on the internal drive is 14,432,616 KiB.
The workspace uses the case-sensitive APFS mount at `/Volumes/PhoenixWork`.

## Next actions

1. Verify the integrated Clang checker on both Linux architectures.
2. Run the independent evaluator and source checks on public projects.
3. Review the evaluator and integrity controls with GPT-6 Astra.
4. Run the sealed T0 evaluation and report the Ghidra-raw baseline.
5. Replay the evaluation and review the exact candidate commit.

The Standard-tier Codex provider passed public run
`provider-probe-9d3b7e1b24ab4fe2b161b48952045086`. The ingestion,
lifting, and integrity worktrees are under
`/Volumes/PhoenixWork/worktrees`.

The ingestion stage accepted the stripped public `bitstats` ELF
from the M0 run. Static checks provide format and linkage evidence.
Runtime restrictions remain the job of the test sandbox.

Public build probe `build-probe-84249aa65e8d413c9cd57b0d0cac4333`
built one CMake project with GCC and Clang on x86-64 and AArch64.
All four builds returned the expected output in the Linux sandbox.

The Ghidra exporter passed its public headless tests with the native
ARM64 decompiler. The separate Standard-tier Corpus Author delivered
10 T0 programs with 40 builds. The author measured at least 9 of 10
source branches and 8 of 8 non-equivalent mutants in the lowest-scoring
programs. The lead agent checked the release binary hashes.

Public probe `public-reconstruction-24660e35059f42e2914b967546600bfb`
built the decompiled `bitstats` project four ways. All 10 public cases
matched in each build.

Public CLI run `m1-public-656fa7d8-38f2-4c69-86eb-72e612730d7a`
passed five generated development cases across four builds. Replay run
`m1-replay-656fa7d8-38f2-4c69-86eb-72e612730d7a` reproduced the C and
CMake files and preserved the model ledger.

Public probe `ghidra-raw-public-55e5cf11170c4257ba1d48e5cfe3851a`
built the raw baseline four ways and matched 10 public cases.
