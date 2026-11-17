# Chromapath fix round 1

The task adds cases for surviving mutants from adequacy run
`9504b3ec73ed422088b6b5d4fd5f6f33`. The report has branch coverage
641/676 and mutation score 264/296. The report records 250 killed mutants,
14 timed out mutants, 32 surviving mutants, 4 uncompilable mutants,
and 0 unresolved mutants.

The generator appends nine cases. The new count is 518. The original
509 cases must remain the byte prefix. Their SHA-256 is
`7cf201deff5f5a605a554c839e018524e70ff48e33cfdb0a396b6043192e857b`.

Case indices below start at zero. Effects are source-based predictions.
No mutation gain is measured in this round.

| Case index | Condition | Surviving mutant ID | Location and expected effect |
|---|---|---|---|
| 509 | `C1 32 1` with samples 0 through 31. | `cacc47fa66dd91645c01fbe4d2f564a02488ab9a45abd8d101dcfb22b13e89a4` | `src/image.c:58`, `>` becomes `>=`. The mutant rejects width 32. The source accepts width 32 and writes the canvas. |
| 510 | `CP 2 1` with two palette entries and indices 0 and 1. | `90518a91a1f4cf6cf2b33a7f6f98f72ce0d257cf32bd83137cb00b697d2a4597` | `src/image.c:66`, `<` becomes `!=`. The mutant rejects two palette entries. The source writes pixels `10 20 30` and `40 50 60`. |
| 511 | Blend pixel `12 34 56` with alpha 0. | `e6680d14c022b271244e92b21e27f83627dec6e1229d3dca2b425914a024273e` | `src/main.c:51`, `<` becomes `<=`. The mutant rejects alpha 0. The source accepts alpha 0 and preserves the pixel. |
| 512 | A horizontal gradient of width 3 has blue endpoints 60 and 20. | `ca5992a0ef45fcfd654012862e4260e66898ab1d159e9cdaece60e0d7f8c7735` | `src/main.c:106`, `-` becomes `+`. The source writes blue values 60, 40, and 20. The mutant writes 60, 100, and 140. |
| 513 | Apply `bias 2` to pixel `10 20 30`. | `ffc548098c0b6e2f065c71d6e7329400f3750edd9f2bf6856116d12b72dac76e` | `src/filters.c:190`, `+=` becomes `/=`. The source writes blue 32. The mutant writes blue 15. |
| 514 | Dither a 4 by 2 canvas with gray samples 111. | `e7707f2a3b736a0fb8213e7e94f7617dcce41f1f00165a1abc907ebe6b90976f` | `src/filters.c:221`, Bayer entry 6 becomes 7. At zero-based pixel coordinate 3,1, the threshold changes from 104 to 120. The source writes white. The mutant writes black. |
| 515 | Dither a 3 by 4 canvas with gray samples 100. | `d063d66cc8b3766591fad5e4ab8ba8945476b3d2dac59b4c727d24776ddd6025` | `src/filters.c:221`, Bayer entry 13 becomes 0. At zero-based pixel coordinate 2,3, the threshold changes from 216 to 8. The source writes black. The mutant writes white. |
| 516 | Apply `hue 0` to magenta `255 0 255`. | `983e856e530cd91a5e31da53c14a1fa2d4bec1d59dad70fa30267fdb3d1ea210` | `src/image.c:190`, `<` becomes `>=`. The mutant leaves hue -60 uncorrected. The negative sector selects no switch case and produces black. The source preserves magenta. |
| 516 | The same magenta case requires correction of a negative hue. | `2dd487c1997edd9f4caa38d34fb597c91692f01ebefc28e04089cf02a8a77ef8` | `src/image.c:191`, `+=` becomes `-=`. The mutant changes hue -60 to -420. The negative sector produces black. The source preserves magenta. |
| 517 | Write pixel `251 0 0` with `-g`. | `57e4f68b9dd5a8c6b67e8122a838da17555d912fa2cb2d8eb2afae91910bf3ac` | `src/image.c:170`, 128 becomes 129. The weighted sum is 19327. The source writes gray 75. The mutant writes gray 76. |

The scoped checks passed. Two runs of
`PYTHONDONTWRITEBYTECODE=1 python3 corpus_dev/chromapath/holdout/gen.py`
produced identical bytes. The new file has SHA-256
`ab3ef4cfc7b27bfe4cb39ff5a418b6de261ec5dc66ff7dd38704bed4623f75b7`.
An in-memory comparison with `git show HEAD:corpus_dev/chromapath/holdout/cases.jsonl`
confirmed the complete 211778-byte prefix. All 518 inputs passed
`phoenix_eval.wire.decode_invocation`, which uses strict Base64 decoding.
The check found zero duplicate lines and zero duplicate decoded invocations.
The metadata count matches the record count.

These scoped commands passed on both generator files:

```sh
ruff check --no-cache corpus_dev/d1_image_record_cases.py corpus_dev/chromapath/holdout/gen.py
ruff format --check --no-cache corpus_dev/d1_image_record_cases.py corpus_dev/chromapath/holdout/gen.py
```

Ruff reported `All checks passed!` and `2 files already formatted`.
The generator wrapper required no change. The shared generator diff changes
only the chromapath arm. The metadata diff changes only `heldout_cases`.

Risks remain until the Lead runs full acceptance. The source predicts ten
mutant detections. Sanitizer checks, branch coverage, and mutation results
remain unmeasured for the 518-case set. The adequacy report describes the
509-case set. This round does not update that report or the exclusions.
