# Phoenix

Phoenix is a project to rebuild stripped Linux x86-64 executables into
portable C projects. It checks the behavior of rebuilt programs against
the original on x86-64 and AArch64.

M0 develops the test harness with public programs written for Phoenix.
See [the specification](SPEC.md) for the benchmark rules and
[the status](docs/STATUS.md) for the current milestone.

## Check a change

Install Python 3.12 and uv. On the Phoenix Mac, source the workspace
script before you use uv.

```sh
source '/Volumes/Extreme Pro/Phoenix/env.sh'
cd "$PHOENIX_ROOT/phoenix"
uv sync --locked
uv run --locked pre-commit install
./scripts/check
```

## Run the public behavior checks

On the Apple Silicon host, start the workspace Colima VM with Rosetta.
Build the two worker images. Run the same public inputs through Rosetta,
explicit QEMU x86-64 emulation, and native AArch64.

```sh
./scripts/build-worker amd64
./scripts/build-worker arm64
uv run --locked phoenix-eval m0 --mode apple-silicon --runs "$PHOENIX_ROOT/runs"
```

The command prints the path to its JSON report. The report contains the
run ID, seed, exact outcome hashes, and mutation counts.

## Rebuild a public executable

Install the Ghidra and Java versions in `tools.lock`. On Apple Silicon,
build the Ghidra native component from the pinned archive. Build both
worker images for the current checkout.

```sh
./scripts/build-ghidra-native
./scripts/build-worker amd64
./scripts/build-worker arm64
phoenix_run="public-$(uuidgen | tr '[:upper:]' '[:lower:]')"
uv run --locked phoenix run "$PHOENIX_ROOT/runs/PUBLIC/bitstats-original.elf" \
  --run-id "$phoenix_run"
```

Replace `PUBLIC` with the public M0 run ID. The command prints the
project path. It saves its checkpoints and model log in the run directory.
Use `--resume` after an interruption. Use `--replay` to rebuild with the
saved model responses. Both commands use the saved binary and require
the recorded checkout and worker images.

```sh
uv run --locked phoenix run --resume "$phoenix_run"
uv run --locked phoenix run --replay "$phoenix_run"
```

Use `--checked-switches` to retain supported switch definitions during
cleanup and repair. The option records unsupported functions as gaps.
It requires the Phoenix method. Its value stays fixed during resume and
replay. The option is off by default while public Linux checks remain open.

## Evaluate the sealed T0 batch

Use the agent-sealed release and the held-out archive in the workspace.
Build the source checker images for the current checkout. The evaluator
saves the submitted projects before it opens the held-out archive.
It tests GCC and Clang builds on x86-64 and AArch64, and records failure
categories, coverage, and the Ghidra-raw baseline.

```sh
./scripts/build-integrity amd64
./scripts/build-integrity arm64
uv run --locked phoenix-eval m1 --run-id m1-t0
uv run --locked phoenix-eval --replay m1-t0
```

If the model service reaches a limit, run the first evaluation command
again with the same run ID. The evaluator keeps the completed submissions.
