# Phoenix

Phoenix turns stripped Linux x86-64 executables into readable, maintainable
C11 projects without access to the original source.

Each project that Phoenix writes must:

- build with GCC and Clang on x86-64 and ARM64;
- reproduce the behavior of the original program on tests that the
  reconstruction process never sees;
- be a project that an engineer can read and change.

The benchmark uses newly written programs and real human-written programs
that were first published after the training cutoff of the models. The
hidden tests stay outside the reconstruction process. [SPEC.md](SPEC.md)
section 10.7 gives the contamination controls and the evidence that a
post-cutoff claim needs.

## Current state

| Milestone | Result |
|---|---|
| M0 | Test harness: sandboxed differential runner, two x86-64 emulators, native ARM64, coverage, CI on x86-64 and ARM64. |
| M1 | First end-to-end pipeline. Sealed T0 at `-O0`: 17 of 20 binaries fully successful (Ghidra-raw baseline: 8 of 20). Run `m1-t0-6897e47`. |
| R0 | Active. Reset to the M1 core and a fast measurement loop. See [the roadmap](docs/ROADMAP.md). |

The live state is in [docs/STATUS.md](docs/STATUS.md). The measured results
are in [docs/SCOREBOARD.md](docs/SCOREBOARD.md).

## How Phoenix works

This section describes the target design. The milestones in the roadmap
build it step by step.

Phoenix lifts the binary with Ghidra and builds a knowledge base of
functions, data, types and test cases. It generates test inputs from the
original program. It writes C one function at a time. It checks each
function inside the running original, then checks the whole project on
four builds. A repair loop fixes the failures. A final step improves names,
types and modules, and checks each edit again.

The details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documents

| Document | Content |
|---|---|
| [SPEC.md](SPEC.md) | Goal, definitions, targets, contracts, integrity rules, benchmark |
| [AGENTS.md](AGENTS.md) | How the engineering agents work |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline, interfaces, techniques |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones R0 to R7, gates, budgets, risks |
| [docs/plans/](docs/plans/) | ExecPlans for the milestones |
| [docs/STATUS.md](docs/STATUS.md) | Current state |
| [docs/SCOREBOARD.md](docs/SCOREBOARD.md) | One row for each measurement |
| [docs/LOG.md](docs/LOG.md) | Decisions, one line each |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Tool and environment decisions |
| [docs/PRIOR_ART.md](docs/PRIOR_ART.md) | Related work and upstream tools |
| [docs/corpus_commitments.md](docs/corpus_commitments.md) | Hashes of the sealed test archives |

## Check a change

Install Python 3.12 and `uv`. On the Phoenix Mac, source the workspace
script first. It mounts the workspace image and sets `PHOENIX_ROOT`.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
cd "$PHOENIX_ROOT/phoenix"
uv sync --locked
uv run --locked pre-commit install
./scripts/check
```

## Run the public behavior checks

On the Apple Silicon host, start the workspace Colima VM with Rosetta. Build
the two worker images. Then run the public inputs through Rosetta, QEMU
x86-64 emulation and native ARM64.

```sh
./scripts/build-images worker amd64
./scripts/build-images worker arm64
uv run --locked phoenix-eval m0 --mode apple-silicon --runs "$PHOENIX_ROOT/runs"
```

The command prints the path to its JSON report.

## Rebuild one executable

Install the Ghidra and Java versions in `tools.lock`. On Apple Silicon, build
the Ghidra native decompiler from the pinned archive. Build both worker
images for the current checkout.

```sh
./scripts/build-ghidra-native
phoenix_run="public-$(uuidgen | tr '[:upper:]' '[:lower:]')"
uv run --locked phoenix run "$PHOENIX_ROOT/runs/<run>/bitstats-original.elf" \
  --run-id "$phoenix_run"
```

The command prints the project path. Use `--resume` after an interruption.
Use `--replay` to rebuild from the recorded model responses. Milestone R0
replaces these commands with `scripts/loop`.

## License and third-party tools

See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
