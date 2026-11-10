# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 remains open. Final Astra review held `5695148` because the generated
Ghidra-raw header conflicts with fortified glibc declarations. The measured
Phoenix score meets the numerical threshold. The baseline needs correction
and a new measurement before the milestone can pass.

| Method | Behavior passed | Integrity passed | Fully successful |
| --- | --- | --- | --- |
| Phoenix | 19/20 | 18/20 | 17/20 |
| Ghidra-raw | 0/20 | 0/20 | 0/20 |

These are the `-O0` results from `m1-t0-5695148`. Two Phoenix variants
failed the exact-byte check. One failed behavior. The baseline compiled
zero GCC builds and eight Clang builds per architecture. Its support-header
defect prevents a fair comparison at this revision.

Replay `m1-t0-replay-5695148` reproduced every stable result field.
The original model log stayed unchanged, and the replay created no model
log. All 792 original cases per method were eligible. There were zero
emulator disagreements and evaluation errors. Tests reached 790 of 1,079
recovered block entries. Source branch adequacy is recorded separately.

The first sealed run, `m1-t0-ce6a34d`, remains in the record. It scored
zero fully successful variants for both methods. Its exact replay also
reproduced that result.

The header correction is committed at `ff4e427`. It uses the glibc format
argument types. The public regression failed with the old declarations
on both compilers and architectures. The correction passed the 393-test
host gate and all 48 Linux compiler-integrity checks. A new independent
preflight review and sealed measurement are pending.

The earlier public matrix at `5695148` passed all 14 Phoenix variants.
Raw passed zero variants with the defective header. The fixed optimized
profile and the 64-byte integrity threshold remain in force.

Both native CI jobs passed at `5695148` after an ARM64 package-delivery
retry. Their exact public outcome hashes match the current Mac M0 run,
`m0-661c1aae6ac84a3a86a37e6f466217a3`.
[CI run 42837009179](https://github.com/dvgyl/phoenix/actions/runs/42837009179).

A separate author is preparing the private T1 batch. The public trace
prototype is in a separate worktree with review fixes in progress.
Its Linux calibration is pending. T3 candidate qualification also remains
pending after the metadata survey.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the case-sensitive APFS mount at `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.

## Next actions

1. Verify the corrected raw public pipeline and obtain preflight review.
2. Measure the corrected M1 candidate on the fixed sealed T0 batch.
3. Replay and review that exact result before any M1 tag.
4. Complete public trace calibration and review before M2 integration.
5. Finish the private T1 adequacy checks and commit only its archive hashes.
