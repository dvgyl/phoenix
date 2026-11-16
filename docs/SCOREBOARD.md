# Scoreboard

`scripts/loop` adds one row for each run. The format is in `docs/ROADMAP.md`
section 6.3. Do not edit rows by hand.

Reference result before the restart (old pipeline, not a row of this table):
run `m1-t0-6897e47` on sealed T0 at `-O0` gave 17 of 20 binaries fully
successful. The Ghidra-raw baseline gave 8 of 20.

| row | run_id | commit | corpus | loop | cache | milestone | exp | main metric | tier 0 | tier 1 | tier 2 | tier 3 | maintainable | held-out passed | integrity | edge cov | escape | literal % | goto/100 | cost median | free GiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
