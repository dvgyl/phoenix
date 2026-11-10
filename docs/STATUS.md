# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. The corrected run meets its numerical threshold.
Exact replay and final independent Astra review remain active at
`efcad059d362bc61a4069268e1122d74e89c6054`.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 8/20 | 8/20 | 8/20 |

These are the `-O0` results from `m1-t0-efcad05`. Two Phoenix variants
failed the exact-byte check. One failed behavior. Twelve raw variants
failed compilation. All 792 original cases per method were eligible.
There were zero emulator disagreements and evaluation errors.
Tests reached 790 of 1,079 recovered block entries. This measure is
separate from source branch adequacy.

The original model log has SHA-256
`728cf1a3f10b21b54c7c747f7dabbbaada85c68b286110d5b865bfe77dd23f44`.
It records 80 calls and $1.603504 of API-equivalent model cost.
There are zero unknown-cost reservations. Median reconstruction time
was 51.893 seconds across all 20 Phoenix variants, including failures
and waits. Replay `m1-t0-replay-efcad05` is active. Main and accepted
image IDs stay fixed through that replay.

The earlier `m1-t0-5695148` result remains Phoenix 17/20 and raw 0/20.
Its exact replay reproduced all stable fields. Final review held that
revision because its raw header conflicted with fortified glibc.
The correction passed the 393-test host gate and all 48 Linux
compiler-integrity checks. The first run, `m1-t0-ce6a34d`, remains
zero fully successful variants for both methods. Its replay also passed.

Both native CI jobs passed at the current revision after package-delivery
retries. The correct checksum pins stayed fixed. Native x86-64 and ARM64
outcomes match Mac M0 run `m0-43bba34c9d8d426aa1c029de0e5071c1`.
[CI run 42859828267](https://github.com/dvgyl/phoenix/actions/runs/42859828267).

The separate author completed T1 with 15 programs and 90 variants.
The lead checked release hashes and ELF contracts. Private sources
and inputs remain sealed. Source sizes are 304 to 316 C LOC.
This limited size range must remain visible in the final report.
Minimum source branch coverage is 184/197. Minimum mutation detection
is 11/12. The T1 archive hashes are committed before reconstruction.

M2 work remains isolated. The public trace fixture builder now works
without a shared host mount. All 16 builds and static plans passed.
Its host gate passed 496 tests. The observer image and live calibration
remain pending. Independent review held the static lift extension for
storage validation defects. A separate Astra worker is fixing them.
The parent live switch check confirmed separate arrays of 13 destinations
and 12 labels for both compilers. A dedicated T2 author has started
private design work. Its Linux validation remains gated until replay ends.
T3 candidates remain unqualified after the metadata survey.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.

## Next actions

1. Finish exact M1 replay and verify stable fields and the full model log.
2. Obtain final exact milestone review before tagging M1.
3. Integrate the committed T1 hashes after the main revision freeze ends.
4. Complete public trace runtime calibration and static evidence review.
5. Build M2 recovery from validated public evidence and evaluate T0 and T1.
