# Phoenix status

M0 passed at `4ef231a1bbdc8d572e06dd5a44efff620dda0e97`.
M1 and the v1 goal remain open. Main is fixed at `baae648` during exact
replay `m1-t0-replay-baae648`. No M1 tag exists.

Original `m1-t0-baae648` scored Phoenix 17/20 and raw 8/20 fully successful.
Phoenix retained two `embedded_text` failures and one behavior failure.
Raw retained 12 compiler failures. Both methods had 792 eligible cases,
zero emulator disagreements and zero evaluation errors. Coverage was
790/1079 recovered block entries. Model use was 69 calls and $1.4249648
API-equivalent cost, with zero unknown-cost reservations.

The earlier `efcad05` original had the same success counts. Its replay
changed one stable failure record and recorded `reproduced=false`.
Astra held that milestone. The CMake feedback timing correction is on main.
Earlier original and replay reports remain intact.

The current main public pipeline passed both methods in all four build
configurations. Native CI passed and both native M0 reports matched the
Mac M0 report `m0-93e7c011124d4017b5908b8284535b1f`.
[CI run 42883642379](https://github.com/dvgyl/phoenix/actions/runs/42883642379).

This branch contains the isolated M2 evaluation matrix. It captures 260
method tasks for 130 T0/T1 variants before archive access. Independent
Sol review first held R1 replay lineage and R2 saved evidence. Their
correction passed a different independent Sol review. The parent gate
passed 582 tests with 25 opt-in skips and 92.25% evaluator line coverage.

Astra then found B1. Equal integer and floating-point configuration values
could pass Python dictionary equality. The parent reproduced this in direct
replay, ancestor replay and completed resume. The new correction serializes
the complete stable M2 projection and compares configuration with JSON types
preserved. Rejection tests failed before each correction. The parent full
gate passed 585 tests with 25 opt-in skips and 92.30% evaluator line coverage.
Fresh independent review of this exact correction remains required.

The separate shared-engine correction binds the ordered capture roster and
reconciles the full model ledger. It has not been integrated here. Combined
source review and a complete parent gate are required before sealed M2 use.
No M2 benchmark result or acceptance is claimed.

T1 is sealed with 15 programs and 90 variants. Sources contain 304 to 316 C
LOC. This limited size range must remain visible in the final report.
Minimum source branch coverage is 184/197. Minimum mutation detection is
11/12. Source and input archive commitments precede reconstruction.

The isolated observer calibration passed 96 positive cases three times and
rejected eight mutants. Both later API and register controls rejected invalid
traces. The reusable command has source and host review PASS. Its fresh
Linux run remains pending. Static lift evidence has Astra review PASS.
A separate Astra task is designing production recovery and localization.
A private Astra author is preparing T2. Its Linux gate remains closed while
M1 uses the VM. T3 qualification remains open. Private material stays sealed.

The internal-drive free-space baseline is 14,432,616 KiB.
The workspace is the external APFS mount `/Volumes/PhoenixWork`.
The dedicated Colima VM has four CPUs and 2 GiB of memory.

## Next actions

1. Complete exact M1 replay and verify every stable field and model-log byte.
2. Review the latest shared correction and typed M2 replay correction.
3. Integrate reviewed shared guards and require combined review before use.
4. Complete M1 acceptance, then integrate T1 and production M2 work.
5. Continue through M3, T3 qualification, M4, publication and section 9.
