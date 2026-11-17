# Corpus handoff

Branch: `dev-corpus-1`. Only `corpus_dev/` files are staged. The lead must
run the repository checks and commit the staged files.

The batch has 22 programs, 10,788 non-blank source lines, and 7,828 distinct
published cases. The size groups meet the Dev Author brief. Each D0
program has one C source file. Each D1 program has one to three C source
files. Header lines count toward the source size.

| Program | Tier | Source lines | Cases | Taken branches | Coverage |
|---|---|---:|---:|---:|---:|
| `weighbit` | D0 | 53 | 327 | 20/20 | 100.00% |
| `niblace` | D0 | 71 | 298 | 34/34 | 100.00% |
| `pairfold` | D0 | 107 | 229 | 43/44 | 97.73% |
| `runepack` | D0 | 108 | 260 | 59/60 | 98.33% |
| `driftstat` | D0 | 161 | 267 | 60/62 | 96.77% |
| `spanrank` | D0 | 161 | 268 | 69/70 | 98.57% |
| `wordweft` | D0 | 221 | 312 | 116/118 | 98.31% |
| `tilehash` | D0 | 225 | 262 | 91/92 | 98.91% |
| `gapmeter` | D0 | 264 | 266 | 99/100 | 99.00% |
| `tokenlace` | D0 | 267 | 429 | 105/112 | 93.75% |
| `velocalc` | D1 | 319 | 321 | 140/149 | 93.96% |
| `knotconf` | D1 | 322 | 353 | 122/126 | 96.83% |
| `prismcsv` | D1 | 345 | 373 | 143/156 | 91.67% |
| `branchmark` | D1 | 604 | 347 | 245/262 | 93.51% |
| `skeinwire` | D1 | 610 | 560 | 302/329 | 91.79% |
| `lumaquilt` | D1 | 613 | 394 | 272/283 | 96.11% |
| `tariffgrid` | D1 | 901 | 423 | 382/411 | 92.94% |
| `patchpanel` | D1 | 908 | 436 | 451/472 | 95.55% |
| `fernconf` | D1 | 915 | 208 | 431/476 | 90.55% |
| `chromapath` | D1 | 1201 | 509 | 641/676 | 94.82% |
| `unitforge` | D1 | 1204 | 618 | 665/687 | 96.80% |
| `recordloom` | D1 | 1208 | 368 | 565/619 | 91.28% |

The D1 program feature counts are: structs 12; function pointer tables 7;
switches with at least 8 cases 10; recursion 5; `getopt` 12; floating-point
output 9; directory trees 5; static local objects 7; and `qsort` 8. Three
programs have mutable static local variables. The other four use constant
static local objects.

Checks completed:

- Run every generator twice with its fixed seed. The case files match.
- Parse each case with `phoenix_eval.corpus._case`. All 7,828 cases pass.
- Run `ruff check corpus_dev` and `ruff format --check corpus_dev`.
- Build and compare GCC and Clang at `-O0`, `-O2`, `-Os`, and `-O3` in
  `phoenix-worker:amd64`. All eight variants pass for each program.
- Build the canonical GCC and Clang configurations on x86-64 and ARM64.
  Run each configuration three times. Compare stdout, stderr, exit status,
  file contents, and file modes. Every published case matches.
- Build and run GCC with AddressSanitizer and UndefinedBehaviorSanitizer
  on ARM64. Run each case three times. All outcomes match the normal builds.
- Measure GCC `-O0 --coverage` with `gcov -b -c --json-format` on the
  published case files. Every program exceeds 90%. No branch is excluded.

The compiler comparisons used 8,320 generated input records. Removal of
492 duplicate records left 7,828 distinct cases. Each distinct case remains
in the published set. Coverage was measured again after duplicate removal.
No distinct case was excluded for instability or a sanitizer error.

`check_direct.py` and `check_portable.py` contain the container check
commands. The README gives the container invocation. Each program has
`direct-check.json` and `portable-check.json`. `VALIDATION.json` records the
image IDs, counts, and pending checks.

Phoenix acceptance remains pending. `scripts/build-dev-corpus` appeared on
`main` during the final check. It fixes the corpus path to its own checkout.
This worktree has no copy. `tools/adequacy.py` is absent from both checkouts.
The lead must run the following commands after integration:

```sh
scripts/build-dev-corpus --check <name>
tools/adequacy.py <name>
scripts/check
```

Mutation scores and pinned QEMU/Rosetta runner validation remain pending.
The Dev Author profile denies code that `scripts/check` reads. The lead
will run that command. No known source defect remains after the direct
checks. No Phoenix evaluation success rate is claimed.

The complete staged path list is in `STAGED_FILES.txt`.
