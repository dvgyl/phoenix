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

1. Integrate the Ghidra exporter and the reviewed integrity checks.
2. Install the native Ghidra decompiler from the pinned source.
3. Build and test the first public binary-to-C reconstruction.
4. Assign T0 corpus work to a separate Standard-tier Corpus Author.
5. Run the M1 evaluation and report the Ghidra-raw baseline.

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
