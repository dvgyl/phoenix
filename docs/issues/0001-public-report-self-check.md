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
