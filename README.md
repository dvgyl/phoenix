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
