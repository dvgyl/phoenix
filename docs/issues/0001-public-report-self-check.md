# Require self-check evidence in public report comparison

Status: OPEN. Owner: principal agent. Found on 2026-11-13.

`compare_public_reports` compares evaluator identity, seed, program counts
and outcome hashes. It does not inspect a program's `self_match` field.
A report with `behavior_checks_passed=true` and `self_match=false` can pass
comparison when its fingerprint fields still match the other reports.

The fresh public evidence review reproduced this limit with actual public
reports. Root repeated that control. Complete root and review assertions
also check every self-match, portability, mutation and probe field. Thus
the bounded evidence at `293477f` remains accepted with its stated limits.

Add a focused refusal control for contradictory self-check evidence. Keep
valid native and emulated reports compatible. Then strengthen the public
comparison boundary and obtain independent review. Do not treat an overall
flag or matching outcome digest as a substitute for the required checks.

The original evidence is in
[the complete public review](../checkpoints/2026-11-13-resume/public-linux-review.md.txt).
This issue supplies no capture authority or milestone acceptance.


## Source correction, 13 November

The source branch now requires every program self_match value to be exactly
true. Missing, false and non-Boolean values refuse before fingerprint comparison.
The original positive fixture now includes the real required self-check field.
Its changed-case-count refusal remains intact. Root reproduced 24 failing
controls before the fix. All 28 final controls pass, including float identity.
Root also checks copies of the three actual public M0 reports. Two valid
comparisons pass. All 54 missing or contradictory program flags refuse with
the overall success flag and fingerprint fields unchanged. The original reports
and historical review control remain exact.

This issue stays OPEN pending full source checks, independent Sol correctness
review, Astra harness review and main integration. This small correction does
not certify every report field. The complete public evidence assertions remain
required. No new target execution or evaluation score follows from these checks.
