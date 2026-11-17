# Candidate development corpus

This batch contains 10 D0 programs and 12 D1 programs. Each program is a
new C11 design. All programs use bounded input storage. They do not use a
network, child processes, time values, or random values.

The sources contain program behavior and input validation. They contain no
unused functions or line-count padding. The line count includes non-blank
`.c` and `.h` lines. The sources contain no comments.

| Program | Behavior |
|---|---|
| `niblace` | Encode bytes as letter pairs. Decode letter pairs with whitespace handling. |
| `weighbit` | Calculate a rotating byte checksum with a byte sum and a length. |
| `runepack` | Encode byte runs as hexadecimal byte and count records. Decode these records. |
| `pairfold` | Calculate two modular sums over complete input or separate blocks. |
| `driftstat` | Calculate numeric moments, movement, and direction counts. |
| `spanrank` | Calculate stable ranks, interpolated quantiles, and outlier counts. |
| `wordweft` | Encode text with byte escapes, line wrapping, and case conversion. |
| `tilehash` | Calculate checksums over tiles and report byte distribution. |
| `gapmeter` | Measure numeric gaps, segments, runs, and level crossings. |
| `tokenlace` | Encode bytes in a selected radix with digit order and checksum options. |
| `knotconf` | Apply configuration assignments, includes, queries, and value changes. Export entries to a directory. |
| `prismcsv` | Read quoted CSV cells. Change text, numbers, separators, and column order. |
| `velocalc` | Evaluate expressions with precedence, variables, and named math functions. |
| `lumaquilt` | Filter gray images. Measure regions and export image rows. |
| `branchmark` | Read a directory tree. Apply suffix weights and configuration rules. Report file checksums and grouped measurements. |
| `skeinwire` | Encode typed records with variable-length integers, bit strings, runs, and checked envelopes. |
| `patchpanel` | Change numeric CSV tables. Calculate ranks, covariance, grouped means, and matrix products. |
| `tariffgrid` | Calculate invoices with volume bands, line discounts, tax classes, shipping, returns, and payment plans. |
| `fernconf` | Change typed configuration trees. Copy, move, merge, search, include, and export subtrees. |
| `unitforge` | Calculate quantities with dimensions. Convert units and calculate polynomial, interpolation, and regression results. |
| `chromapath` | Change color images with geometric operations, color models, kernels, drawing, and palette reduction. |
| `recordloom` | Change typed records. Encode prefix-compressed records with checksums, hexadecimal text, and byte armor. |

Each program has `meta.json`, sources, a generator, and `holdout/cases.jsonl`.
Each generator has a fixed seed. The shared generator modules contain the
case definitions for each source. Run a generator from this worktree:

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
python3 corpus_dev/<name>/holdout/gen.py
```

The case files contain no duplicate input records. The author used a larger
generated sequence for the initial compiler comparisons. Added cases require
new evaluator validation and adequacy reports.

The case schema comes from `phoenix_eval.corpus`. Byte fields use Base64.
The cases include valid data, malformed data, invalid options, missing
files, and input limits. The directory cases contain explicit parent
entries.

`direct-check.json` records direct GCC branch coverage and repeated outcome
comparisons. Coverage counts each branch with a positive execution count.
It excludes no branch. The comparisons include stdout, stderr, exit status,
file contents, and file modes. The checker builds GCC and Clang variants at
`-O0`, `-O2`, `-Os`, and `-O3`. Each report gives the repetition count.
The canonical checks run each build three times.

`portable-check.json` records the separate canonical build checks. These
use GCC and Clang on x86-64 and ARM64. The ARM64 check also uses GCC with
AddressSanitizer and UndefinedBehaviorSanitizer. The Clang ARM64 sanitizer
libraries are absent from the compiler image. The checker compares complete
outcomes through SHA-256 hashes. It does not exclude cases.

Run the direct checks inside the compiler container. This command sends
only `corpus_dev/` to the container. It does not require a VM bind mount.

```sh
COPYFILE_DISABLE=1 tar --format=ustar -C corpus_dev --exclude .work \
  --exclude __pycache__ -cf - . |
  docker run --rm -i --platform linux/amd64 --network none \
    --entrypoint /bin/sh phoenix-worker:amd64 -c \
    'mkdir /work; tar -xf - -C /work; cd /work; python3 check_direct.py <name>'
```

Use `check_portable.py <name>` in each architecture's compiler container
for the canonical checks. Use `phoenix-worker:arm64` and
`--platform linux/arm64` for ARM64.

This batch is not accepted. At the owner pause on 2026-11-17, the evaluator
has validated all eight builds of seven programs. Two programs have current
adequacy passes: `branchmark` and `driftstat`.

The `chromapath` fix has 518 validated cases. Its new pilot was interrupted
at the owner's request. Its stored `adequacy.json` describes the earlier
509-case set and does not count as a current pass.

The lead must finish evaluator validation and adequacy for all 22 programs.
The author checks are preliminary evidence. The evaluator records determine
acceptance. `accepted.json` and the quick set have not been created. No
reconstruction success rate is claimed.

The saved state is in `docs/evidence/r0/pause-checkpoint.json`. The R0 plan
gives the resume commands.
