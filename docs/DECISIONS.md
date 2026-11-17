# Decisions

This file records decisions about tools, the environment and interfaces.
Each entry has 10 lines maximum. Add an entry only when a tool, an
environment setting or an interface in `docs/ARCHITECTURE.md` changes.
Record smaller decisions as one line in `docs/LOG.md`.

The entries 1 to 10 come from the first phase of the project (milestones M0
and M1). They stay in force until a later entry replaces them.

## 1. Host and workspace

The host is an Apple Silicon Mac (`arm64`, 8 CPUs, 16 GiB memory). The
external drive uses exFAT. Thus the workspace is a 60 GiB case-sensitive
APFS sparse bundle, `"/Volumes/Extreme Pro/Phoenix/phoenix-work.sparsebundle"`,
mounted at `/Volumes/PhoenixWork`. `"/Volumes/Extreme Pro/Phoenix/env.sh"`
mounts the image and points all caches and tools into `$PHOENIX_ROOT`.
Rosetta 2 is installed for x86-64 Linux containers.

## 2. Linux VM and containers

Use Colima 0.10.3, Lima 2.2.1 and the Docker CLI (`tools.lock`). The VM uses
the `vz` type with Rosetta, at most 4 CPUs and 6 GiB of memory, and its own
Docker endpoint. The VM disk is under `$PHOENIX_ROOT/vm/colima`. Python 3.12
and `uv` manage the Python environment. `uv.lock` pins the packages.

## 3. Test isolation

A long-lived Docker worker runs one executable and its cases. The worker has
a read-only root, no network, a PID limit and a bounded tmpfs. Each case runs
in its own chroot with dropped privileges, resource limits and a seccomp
filter that blocks process creation (`containers/launch-target.c`).
Base image: Ubuntu 24.04 by digest, packages from the pinned snapshot.

## 4. Coverage

A QEMU TCG plugin (`containers/code-coverage.c`) records each executed
x86-64 address of the original. GNU Binutils give the static block
inventory. A traced run must give the same outcome as an untraced run. The
metric "recovered block entries" will change to CFG edges (see the
architecture).

## 5. Lifting

Ghidra 12.2 headless with `ghidra_scripts/ExportLift.java` exports
`lift.json` (`schemas/lift.schema.json`). Ghidra needs Temurin 25.0.5+8.
Both archives are under `$PHOENIX_ROOT/tools`, checked by SHA-256 from
`tools.lock`. The macOS ARM64 decompiler is built from source with
`scripts/build-ghidra-native`.

## 6. Runtime model access

The pipeline calls the runtime model through the OpenAI Responses API when
`OPENAI_API_KEY` is set, otherwise through `codex exec` with the signed-in
account. Prompts have no tool access. Each call goes to `llm.jsonl` with the
model, service tier, tokens and estimated cost. The service tier is the
default (Standard) tier.

## 7. Compiler evidence for integrity

`containers/c-integrity.cc` uses Clang 18.1.3 LibTooling in a Linux
container without the original or evaluation inputs. It checks the stored
bytes of C declarations. Its typed-storage and call-list rules will change
in milestone R1 (see the architecture).

## 8. Ghidra-raw baseline

The baseline uses the same lift and function set as Phoenix. It keeps
Ghidra's function bodies and adds a generated compatibility header with
standard headers, type aliases, string data and an entry wrapper.

## 9. Package transport

The pinned Ubuntu snapshot is the only source of signed package indexes.
The official Ubuntu pool is a package-only fallback through APT's mirror
transport. Each Dockerfile is part of its image source digest.

## 10. Build profile for evaluation

The evaluator builds each project with `-O2`, stack protection on each
function, full RELRO and immediate binding. The same profile applies to
Phoenix and the baselines, on both architectures.

## 11. True-source sanitizer validation

Use `Engine.TRUE_SOURCE_ARM64` only for true-source validation.
It permits sanitizer virtual reservations and retains the other target limits.
Disable LeakSanitizer and external symbolization. Keep ASan and UBSan active.
Pin `qemu64-v1` and the glibc feature mask in `tools.lock`.
The fixture probe matched 145 libc/libm symbol versions on both x86-64 runners.
Evidence is in `$PHOENIX_ROOT/tmp/validation-runtime/proof.json`.

## 12. Source mutation tool

Mull is absent from the pinned compiler image. Its probe returned exit 127.
Use `clang-ast-source-v1` with the operator set in SPEC.md section 10.6.
Keep unresolved mutants in the denominator. Count compiler infrastructure
failures as unresolved. Store source, case, tool and report hashes.
The Linux fixture proof is in `$PHOENIX_ROOT/adequacy_runs/bced812a3047410eae4f7393fcd1fdd5`.

## 13. Image build entry point

Use `scripts/build-images worker|integrity amd64|arm64` for local image builds.
The command retains immutable image IDs before and after each build.
It serializes builds and takes compile and execution slots.
The underlying builder recipes remain unchanged.
A real rebuild preserved all 29 preceding image IDs.
