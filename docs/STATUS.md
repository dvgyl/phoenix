# Phoenix status

This branch retains the isolated public M2 trace prototype.
It is based on `5695148`. It is not the sealed-evaluation candidate.
Main is fixed at `baae648` while the new M1 run and replay proceed.
M0 passed. M1 and the v1 goal remain open.

Original run `m1-t0-efcad05` scored Phoenix 17/20 and raw 8/20 fully
successful. Its exact replay failed one stable record. Final Astra review
returned HOLD. The reviewed CMake feedback correction is on main.
Its new sealed run is `m1-t0-baae648`. No M1 tag exists.

The separate observer image built after the fixture transport and `ldd`
recipe corrections. The accepted oracle image IDs stayed fixed.
Its public calibration passed 96 positive cases with three repetitions.
It detected all eight mutant controls. The parent checked all 296 traces
and their plans and complete outcomes. This is public fixture evidence.
It is not a Phoenix-Bench result or M2 acceptance.

A fresh independent Standard-service Sol reviewer passed this isolated
prototype. It ran 104 focused tests and 10 independent tests.
The parent full gate passed 496 tests with 23 skips and 90.01% evaluator
coverage. The reviewer checked the saved runtime evidence independently.
The later wrong-API and missing-register controls also rejected their
invalid traces. A reusable command now binds control sources, plugins,
images, invocations, raw traces and outcomes. It retains partial evidence
on failure. Its parent gate passed 515 tests with 23 skips and 90.01%
evaluator line coverage. Fresh independent Sol review passed the source
and saved public evidence. A fresh Linux run of this command remains open
while M1 uses the VM.

The M2 evaluator remains separate and unmerged. Astra review held its
replay lineage and saved-report validation. A separate Astra task is
correcting inherited capture-freeze and accounting gaps. All sealed-use
gates remain closed until the corrections and closure reviews pass.

T1 is sealed. A dedicated private Astra author is preparing T2.
The T2 Linux resource gate remains closed during the official M1 work.
Source and held-out material stay private. T3 qualification remains open.

The internal-drive baseline is 14,432,616 KiB free.
The workspace is `/Volumes/PhoenixWork` on the external drive.
The dedicated Colima VM has four CPUs and 2 GiB of memory.

## Next actions

1. Finish and check the new M1 run and exact replay on main.
2. Correct and review the shared engine and M2 evaluator gaps.
3. Run the reviewed reusable observer controls after M1 releases the VM.
4. Integrate verified M2 work after the M1 gates pass.
5. Continue through M4 and SPEC.md section 9.
