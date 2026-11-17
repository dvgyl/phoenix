# Branchmark fix round 1

The candidate adds 11 cases. The total is 358. All 347 existing cases remain
as a byte-identical prefix. Only the branchmark arm in `d1_cases.py` changes.
The independent generator remains unchanged. Source remains unchanged.
The Lead updated the metadata case count to 358.

The table predicts 20 additional mutant detections from source inspection.
Case numbers are one-based JSONL line numbers. Mutant ID prefixes refer to
`adequacy.json`. This is a prediction, not an official mutation score.

| Case | Input condition | Surviving edits | Expected difference |
|---|---|---|---|
| 348 | Suffix length 31 | `e6d13220692c`, line 132, `>` to `>=` | Valid rule becomes an error. |
| 349 | Maximum 1000000 | `f71bb5ad8c87`, line 109, `>` to `>=` | Valid limit becomes an error. |
| 350 | Factor 1000 | `3e0aea5b39af`, line 119, `>` to `>=` | Valid factor becomes an error. |
| 351 | Exclude length 127 | `abc2c6c72ac7`, line 191, `>` to `>=` | Valid pattern becomes an error. |
| 352 | Remove the second of five weighted suffixes | `3b178a664c24`, line 156, `1` to `(1 + 1)`; `c748bb102697`, line 156, `<` to `==`; `c1a8ae7decf7`, `98b1afbe6236`, `b8c624460a74`, line 157, `-` to `/`, `%`, `+` | Remaining file scores change. |
| 353 | Update the second suffix rule | `0b82d1e188a3`, line 134, `++` to `--` | Duplicate weights give score 21 instead of 7. |
| 354 | Suffix matches the complete file name | `6640d6d4f523`, `c366c4e05737`, line 282, `<=` to `!=`, `<` | File score becomes 1 instead of 3. |
| 355 | Nested file with default depth | `c8014ba19d68`, line 563, `8` to `0` | Nested file is ignored. |
| 356 | Scores 0 and 1, mean 0.5, variance 0.25 | `ea217efd46df`, line 552, `0` to `(0 + 1)`; `0b3d62900e37`, line 555, `0` to `(0 + 1)` | Deviation output changes. |
| 357 | Relative file path length 511 | `c2b2ba34da4c`, line 321, `>` to `>=` | Valid path becomes an error. |
| 358 | Relative file path length 512 | `a7bc8d5d7e54`, `8ee0bb193147`, line 342, `result` to `0`, `1`; `efae889801a6`, line 321, `2` to `0`; `e3202d95e175`, line 321, `+` to `%` | Error propagation or path rejection changes. |

The unchanged source rejects case 358 before it copies the long file path.
The two path-guard mutants can overflow their buffer. Their outcomes need
official validation. The other 18 predictions do not depend on that overflow.

Checks passed. Two generator runs match byte for byte. The strict decoder
`phoenix_eval.corpus._case` accepts all 358 cases. No cases are duplicates.
`ruff check corpus_dev`, `ruff format --check corpus_dev`, and the diff
whitespace check pass.

The Author profile denied reads during the full repository check. The Lead ran
`./scripts/check` outside that profile after the worker stopped. All 927 tests
passed, with 86.69 percent evaluator coverage. The check took 58.09 seconds.
Evidence is `tmp/r0-dev-fix-branchmark-1-lead-check.log`.

Existing validation bindings and the adequacy report describe the old cases.
The Lead must run pinned validation and the official pilot for this candidate.
This session ran no target binary and no official validation or adequacy job.

Cases SHA-256 is
`f3a757fe19d64e32635331abbab22dc3d039913f194a4b19c473d8e0afe613e3`.
