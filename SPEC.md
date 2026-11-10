# Phoenix: Project Specification

**Version:** 0.3 (2026-11-10)
**Read with:** `AGENTS.md`, which covers how to work: environment, autonomy, delegation, git and quality.
**Status of claims:** nothing in this document is a result. Everything here is a goal, a constraint or an acceptance test.

---

## 1. The goal

### 1.1 North star

> **Give Phoenix a compiled program, and with no source code it gives back a living codebase: source you can read, build on a different CPU, change, and trust, because it has been tested against the original on inputs no one wrote by hand.**

Billions of dollars of software exist only as binaries:

- abandoned tools;
- vendor code whose source was lost;
- scientific programs nobody can rebuild;
- utilities stuck on x86 while the world moves to ARM.

Today the options are emulation (slow and opaque), decompilation (unreadable, doesn't rebuild, never verified), or a rewrite by hand (months of work). Phoenix aims to make **"we lost the source" a solved problem**: binaries become software again.

### 1.2 The v1 goal (what this spec must deliver)

Build a pipeline and a sealed benchmark that together demonstrate the following headline. The fill-in values are measured, never assumed:

> *"Given only stripped x86-64 Linux executables of programs written after the model's training cutoff, Phoenix rebuilt **X%** of them into C projects that compile on both x86-64 and ARM64 and pass **100%** of held-out differential tests, which reach **C%** of the original program's code, at a median cost of **$Y** and **Z minutes** per program."*

**Ambition target for v1:**

- T0 and T1 at every optimization level: **≥ 70% fully successful**.
- T2 (1,500–6,000-line multi-module programs) at `-O2`: **≥ 40% fully successful**.
- At least one real-world, post-cutoff open-source CLI (T3) reconstructed fully successfully.

If v1 hits these targets, it would be the first contamination-controlled demonstration of whole-program, cross-architecture binary-to-source reconstruction with behavioral verification. Aim for that. Report exactly what you achieve.

### 1.3 The vision ladder (beyond v1; do not start before v1 is done)

| Stage | Capability |
|---|---|
| v1 | C, glibc dynamic, stripped, deterministic CLIs → portable C11 |
| v2 | Static binaries (libc identification), threads, C++ (vtables, exceptions, templates), Rust as output language |
| v3 | Shared libraries → ABI-compatible reconstructed libraries; servers verified by protocol-level differential testing; 100k+ instruction programs |
| v4 | Cross-OS input: Windows PE and Mach-O → portable source |
| v5 | Legacy-migration service: patch, port and modernize binaries whose source is gone |

---

## 2. Prior art and the gap

The building agent must not claim novelty beyond §2.2. Any further prior art goes in `docs/PRIOR_ART.md`.

### 2.1 Existing work (as of Nov 2026)

| Work | What it does | What it does not do |
|---|---|---|
| Ghidra, IDA, Binary Ninja, RetDec | Readable pseudo-C | Not designed to recompile; no behavioral check |
| rev.ng | Lifts via QEMU to LLVM and emits C that is meant to recompile | No behavioral harness; output is not a maintainable project |
| LLM4Decompile (2024), DecLLM (ISSTA 2025), SK2Decompile (ICLR 2026) | LLM decompilation with recompile and re-execute metrics | Function-level |
| Agent4Decompile (arXiv 2604.23940) | Multi-agent constraint-guided repair; 50.3% of 1,641 functions | Explicitly single-function |
| Chisel (arXiv 2608.27981, code released) | Ghidra pseudo-C plus libFuzzer differential oracle; 79.8% re-executable | Single function; stripped signatures are a stated limitation |
| "Recompilation Is Not Enough" (arXiv 2609.07201) | Whole-binary repair of decompiled C; 91/104 GNU coreutils pass the official tests | Coreutils only (in every model's training data); relies on existing test suites; same architecture; no released artifact; authors call the evaluation "narrow" |
| LLMSbt (arXiv 2610.05999) | x86-64 → AArch64 assembly static translation with SMT-checked snippets | Output is assembly, not maintainable source |
| N64/GBA "matching decomp" with Claude and Codex | Byte-identical C per function, using the original compiler | Requires the original compiler; not portable |

### 2.2 The gap Phoenix claims

No prior system shows all four of these together:

1. **Whole-program** reconstruction.
2. **Contamination-free** evaluation: sealed, post-cutoff programs.
3. **Demonstrated portability**: the same project builds and passes on AArch64.
4. **A test-suite-free behavioral oracle** whose evaluation inputs stay hidden from the reconstruction loop.

**Phoenix-Bench** (the sealed benchmark plus its harness) is a contribution of its own.

---

## 3. Scope

### 3.1 Input contract (v1)

A v1 input binary is:

- ELF64, x86-64, Linux, **stripped** (`strip --strip-all`);
- compiled from **C** by gcc or clang at `-O0`, `-O1`, `-O2` or `-Os`;
- **dynamically linked against glibc**;
- single-threaded, with no `fork`/`exec`, no network, and **deterministic** given argv, stdin, environment and input files;
- I/O limited to argv, stdin/stdout/stderr, a working directory tree, a fixed environment, and the exit code.

### 3.2 Out of scope for v1

Each item below is a later milestone, not a silent omission:

C++, Rust and Go inputs; static or musl binaries; threads; signals beyond default termination; `mmap` of files; output that depends on time, PID or randomness; GUIs; JIT or self-modifying code; obfuscation or packing; PE and Mach-O.

### 3.3 Output contract

For each input `foo`, Phoenix writes `out/foo/` containing:

- `CMakeLists.txt`: builds with gcc and clang; no host-specific flags;
- `src/*.c` and `include/*.h`: C11 plus POSIX, grouped into modules;
- `tests/`: replayable dev tests (inputs and expected outputs);
- `PHOENIX_REPORT.md` and `phoenix_report.json` (§3.4).

The source must:

- compile with `-std=c11 -Wall -Wextra` with **zero errors** on x86-64 and AArch64, with warnings counted and reported;
- contain no inline assembly, hard-coded load addresses or x86 intrinsics;
- use recovered `struct`/`enum`/typedef types wherever the evidence supports them;
- use evidence-based names, otherwise neutral ones (`fn_401a30`), never invented ones.

### 3.4 Report contract

**Per function:**

- address range;
- confidence:
  - `verified`: covered by passing tests, with ≥ 90% branch coverage of the original function;
  - `tested`: covered by passing tests, but below that coverage;
  - `unverified`: never executed by any test;
- the recovered signature and the evidence for it.

Every `unverified` function carries `/* PHOENIX-UNVERIFIED: <reason> */` in the source.

**Per binary:**

- build status per architecture and compiler;
- dev-test pass rate;
- original-code coverage reached by the tests;
- tokens, dollars and wall time;
- known divergences.

---

## 4. System architecture

### 4.1 Components and language

- **Orchestration:** Python 3.12.
- **Lifting:** Ghidra headless scripts.
- **Hot paths:** Rust, if profiling justifies it.
- **The runtime LLM** is one component inside the pipeline, reached through `phoenix/llm/` behind a provider-agnostic interface. It is distinct from the agent that builds Phoenix.
  - Backends: (a) the OpenAI Responses API when an API key is present in the environment; (b) the non-interactive `codex exec` CLI, which uses the logged-in account. Choose a default in an ADR.
  - Every call is recorded to `$PHOENIX_ROOT/runs/<id>/llm.jsonl` (prompt, response, model, service tier, tokens, cost) and cached by content hash.
  - Default runtime model: GPT-6.1 Sol. Escalating hard repairs to GPT-6 Astra is configurable and recorded separately.
  - **Service tier:** Standard (`AGENTS.md` §4).
  - **Budgets:** $5 per binary and $200 per evaluation run by default, both configurable. With the `codex exec` backend, enforce the equivalent token budgets.
  - **Usage limits:** on rate-limit or usage-limit errors, back off and resume the run from its last completed stage. Do not fail the binary.

### 4.2 Pipeline

```
ingest -> analyze -> lift -> recover -> generate -> build -> verify -> repair ⟲ -> package
```

1. **ingest**: validate the input against §3.1 and reject with a specific reason if it fails. Hash the binary and record compiler hints from `.comment` and prologue patterns.
2. **analyze** (dynamic):
   - Run the original on seed inputs.
   - Run coverage-guided input generation against the original to build the **dev set**. Use AFL++ in QEMU mode, or a mutational or grammar-aware fallback.
   - Record basic-block coverage and call/return traces, with argument values at libc boundaries, via QEMU user-mode TCG plugins.
3. **lift**: run Ghidra headless analysis and export to the versioned JSON schema `schemas/lift.schema.json`: functions, CFGs, call graph, types, strings, data references and imports.
4. **recover**: whole-program structure:
   - globals and their types;
   - struct layouts unified across all functions;
   - signatures cross-checked between callers and callees, and against observed values at runtime;
   - jump tables, and indirect-call targets from traces;
   - inlined libc idioms;
   - module boundaries from call-graph clustering.

   LLM proposals for names and types are stored with their evidence.
5. **generate**: emit C from the lifted IR plus the recovered types. LLM cleanup always works on the decompiler's output and never writes from scratch. Then emit the project skeleton.
6. **build**: gcc and clang, x86-64 and AArch64.
7. **verify**: run the differential runner (§4.4) on the **dev set only**, on both architectures, plus the integrity checks (§5).
8. **repair**: fault-localize each failure to functions, using trace comparison and the transplant mode described in §11.2 if it is adopted. Hand the runtime LLM a minimized failing input and the divergence. Budget: 20 rounds or the per-binary dollar cap, whichever comes first.
9. **package**: write the output contract and the reports.

Each stage writes artifacts to `$PHOENIX_ROOT/runs/<run_id>/<binary>/<stage>/`. Runs can be resumed from any stage. `phoenix run --replay <run>` re-executes a run using recorded LLM responses and makes no API calls.

### 4.3 Execution environment (oracle and sandbox)

The host is the owner's Mac. Every execution of an original or reconstructed binary happens inside **Linux containers** in the container VM, whose storage is under `$PHOENIX_ROOT` (see `AGENTS.md` §6).

- **x86-64 oracle (emulated on Apple Silicon):**
  - Use two independent emulators: Rosetta, through `linux/amd64` containers, and QEMU user mode (`qemu-x86_64`) inside an arm64 container.
  - Every oracle output must agree under both. A test case where they disagree is marked emulator-sensitive, excluded, and counted in the report.
- **AArch64 portability runs:** native, in arm64 containers.
- **Intel Mac:** if the host is an Intel Mac, run x86-64 natively in `amd64` containers, run AArch64 under `qemu-aarch64`, and skip the dual-emulator check.
- **CI cross-check:** CI repeats the oracle and the portability runs on real hardware (`ubuntu-latest` and `ubuntu-24.04-arm`) for the public toy corpus.
- **Sandbox per test:**
  - The container runs with no network, a read-only root filesystem, a fresh tmpfs working directory and a PID limit.
  - Inside the container, each test runs under `prlimit`/`bwrap` with CPU 5 s, memory 1 GiB, file size 64 MiB, a fixed environment (`LANG=C.UTF-8`, `TZ=UTC`, `HOME=/nonexistent`), and the same `argv[0]` for the original and the reconstruction.
  - Use a long-lived runner process inside the container that executes batches of tests, rather than one `docker exec` per test.
- Pin all tool versions in `tools.lock` and record `SOURCE_DATE_EPOCH` and all random seeds.

### 4.4 Differential runner (the oracle)

- **A test case** is: argv, stdin bytes, an initial directory tree, and an optional environment overlay.
- **A match** requires equal stdout bytes, stderr bytes, exit code or terminating signal, and final directory tree (paths, contents and modes).
- **Normalization** is off by default. Any rule must be declared per binary with a reason.
- **Two input sets** are kept separate:
  - **Dev set:** produced by Phoenix's analyze stage. The repair loop may see it.
  - **Held-out set:** produced by the corpus process (§6.1) with a different generator, seed and budget. It is stored under `$PHOENIX_ROOT/holdout/`, outside the repository, and read only by `phoenix-eval`. All headline numbers come from the held-out set.

### 4.5 Evaluation harness (`phoenix-eval`)

`phoenix-eval` is a separate package that **does not import** `phoenix`. It:

- runs Phoenix in a clean workspace;
- builds the output four ways: {gcc, clang} × {x86-64, AArch64};
- runs the held-out set on both architectures;
- applies the integrity checks.

It reports:

- build results;
- held-out pass rates per architecture;
- original-code coverage reached by the held-out set;
- integrity status;
- secondary quality signals: typed-function share, warnings, `unverified` share, LOC ratio;
- cost and time.

**For held-out failures it reports only the failure category, never the failing inputs**, until results are frozen at M4.

---

## 5. Integrity rules (hard invariants)

Breaking any of these rules scores the binary as a **failure**, whatever its test results. `phoenix-eval` enforces them automatically.

1. **No embedding the original.** The output must not contain the original's `.text` bytes, an x86 emulator or interpreter, or any way of loading or executing the original. Detection: any run of ≥ 64 bytes matching the original `.text`, in the source or in the built binary.
2. **Data only as typed data.** Constants and strings from `.rodata`/`.data` may appear only as typed C initializers. Any raw blob over 4 KiB must be justified in the report.
3. **No output memorization.** No lookup tables keyed on test inputs. Detection: string literals longer than 32 bytes that equal dev-test outputs and are absent from the original's `.rodata` are flagged. The held-out set is never visible to the pipeline.
4. **No source access.** The pipeline and the main agent never read sealed-corpus sources.

---

## 6. Phoenix-Bench

### 6.1 Sealing in an autonomous setup

The owner is away, so sealing is done by process and recorded honestly.

- **Corpus Author:** a dedicated GPT-6 Astra subagent (see `AGENTS.md` §8), or a GPT-6.1 Sol subagent if Astra is unavailable. It writes programs in `$PHOENIX_ROOT/sealed/src/`, outside the repository. The main thread and the pipeline never open that directory.
- **What the Author hands over:**
  - `$PHOENIX_ROOT/sealed/release/`: stripped binaries and a manifest with name, tier, compiler, flags, SHA-256 and a one-line *category* (for example, "text transformer"), but no behavioral description;
  - `$PHOENIX_ROOT/holdout/`: the held-out input sets;
  - aggregate adequacy numbers (§6.3).
- **Hash commitment:** when each corpus batch is created, the Author commits only the SHA-256 of the source tarball and of the held-out tarball to `docs/corpus_commitments.md`. Publishing the tarballs after M4 then proves nothing was changed after the fact.
- **Freshness:** programs are newly written, not ports or clones of well-known tools such as coreutils or busybox. They are original designs within ordinary program categories.
- **T3 real-world programs:** open-source CLIs that meet §3.1 and were **first published after the runtime model's training cutoff**. Look up and record the official cutoff and each program's publication date and licence.
- **Disclosure:** every report states that the corpus is *agent-sealed*: the Author is a separate subagent run on the honor system, not a human.

### 6.2 Tiers

| Tier | Size (C LOC) | Kinds of program | Count (v1) |
|---|---|---|---|
| T0 | ≤ 300 | stats, checksums, encoders | 10 |
| T1 | 300–1,500 | config/CSV transformers, calculators, codecs, image filters; uses structs, function pointers, `switch`, recursion, `getopt` | 15 |
| T2 | 1,500–6,000 | bytecode VMs, formatters, markup renderers, archivers; multi-file, with hash tables and linked structures | 10 |
| T3 | any | post-cutoff real open-source CLIs | 5–10 |

Builds:

- every program: {gcc, clang} × {`-O0`, `-O2`};
- T1 and T2 additionally at `-Os`;
- all builds are stripped and made in a pinned `linux/amd64` toolchain container.

Each (program, compiler, flag) combination is scored separately.

### 6.3 Test adequacy (checked by the Corpus Author on sources)

For T0–T2, the held-out inputs must:

- reach **≥ 85% source branch coverage**;
- kill **≥ 90% of non-equivalent mutants** (using `mull` or hand-written mutants).

Only these aggregate numbers cross into the repository.

---

## 7. Baselines (always reported next to Phoenix)

1. **Ghidra-raw:** Ghidra's output plus only a mechanically generated compatibility header.
2. **Single-shot LLM:** one cleanup pass per function, with no verify-and-repair loop.
3. **Ablation:** Phoenix without dynamic analysis.
4. **Ablation:** Phoenix without whole-program type recovery.

---

## 8. Milestones and acceptance criteria

**Fully successful** (for one binary) means all of the following:

- it builds with zero errors under gcc and clang on x86-64 and AArch64;
- it passes **100%** of held-out tests on both architectures;
- it passes every integrity check.

A milestone is done only when its criteria pass in a scripted run anyone can reproduce. Then tag it, update `docs/STATUS.md`, and have the milestone's diff and harness independently reviewed (`AGENTS.md` §8).

| Milestone | Deliverable | Acceptance |
|---|---|---|
| **M0: Harness first** | Workspace and container setup under `$PHOENIX_ROOT`; sandbox; differential runner; dual-emulator oracle; coverage; dev-set generator; `phoenix-eval` skeleton; public toy corpus (with source, for development only); CI on x86-64 and arm64 | Each original vs. itself: 100% match, 3 runs, no flakes. Deliberately mutated rebuilds of toy programs detected ≥ 90%. AArch64 cross-build-and-run works. CI green. |
| **M1: First end-to-end** | Full pipeline with a minimal repair loop; Corpus Author produces sealed T0 | T0 `-O0`: ≥ 80% fully successful; Ghidra-raw reported alongside |
| **M2: Optimization and portability** | Jump-table and indirect-call recovery, libc-idiom recovery, trace-based fault localization; sealed T1 | T0 all flags ≥ 80%; T1 `-O0` ≥ 60%; T1 `-O2` ≥ 40%; AArch64 within 5 points of x86-64, with every arm-only failure root-caused |
| **M3: Maintainable projects** | Whole-program type unification, modules, evidence-based naming, uncertainty annotations; sealed T2 | No regression on M2. ≥ 70% of T1 functions with non-default types. Readability rubric (`docs/READABILITY_RUBRIC.md`) applied by an Astra reviewer to 5 sampled projects. |
| **M4: Sealed evaluation and report** | One frozen run on sealed T0–T3, with baselines and ablations; `docs/REPORT.md` | All numbers published as produced; failure taxonomy; costs; limitations; commitments verified |
| **M5+** | Vision ladder (§1.3), starting with v2 | Defined in a new spec revision |

The §1.2 ambition targets are what M4 aims for. The table's acceptance criteria are the minimum needed to move on.

---

## 9. Definition of done (v1)

v1 is done when all of the following hold:

- M4 is complete;
- `docs/REPORT.md` presents held-out results for T0–T3 against every baseline, with costs and a failure taxonomy;
- the harness, the benchmark binaries, the held-out inputs and the committed source tarballs are published;
- every headline number reproduces with `phoenix-eval --replay`.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| The model memorized the targets | Sealed, newly written corpus; post-cutoff T3; hash commitments |
| Weak tests inflate pass rates | Coverage and mutation adequacy gates; coverage reported with every number |
| Gaming the metric | Integrity rules with automated detection; held-out failures reported by category only |
| Emulation differs from real x86 | Dual-emulator agreement; CI on real hardware |
| Optimized code defeats lifting | Tiered scope; `-O0` first; baselines and ablations show where gains come from |
| Portability bugs (endianness, `long`, `char` signedness, padding) | AArch64 build and test from M0; arm-only failures root-caused |
| Pipeline that can't be reproduced | Recorded and replayable LLM calls; pinned tools |
| Prior-art overlap | Claim only §2.2; cite and compare |
| Provider safety tooling misreads binary-analysis work | Only self-built or corpus binaries; purpose stated in README |
| Equivalence is undecidable | Never claim equivalence; claim "passes N held-out tests at C% coverage" |

---

## 11. Notes from Claude (independent review of this plan)

*These notes come from Claude (Anthropic), which researched and drafted this spec. Treat them as advice from a colleague, not as hard rules. Where they suggest a technique, adopting it is your decision; record it in an ADR.*

### 11.1 The harness is the product

The most likely way this project fails is not "the reconstruction is bad". It is "the numbers looked great and were wrong". A weak oracle, a leaky held-out set or an emulator quirk will inflate results quietly. Spend M0 making the harness hard to fool, and point Astra's adversarial review at it before trusting any number. If you had to choose between a beautiful pipeline with a mediocre harness and the reverse, choose the reverse.

### 11.2 Strongest technical suggestion: function transplant mode

You have the original binary, and you can run it. Use that fact.

- **The technique.** Build reconstructed functions as an x86-64 shared object in a "transplant" mode, where globals bind to the original binary's data addresses. Load it into the original with an `LD_PRELOAD` shim that patches each chosen function's entry with a trampoline. Then run the whole-program tests with one function replaced at a time.
- **What it gives you:**
  - **Exact fault localization:** the function whose transplant breaks the tests is the bug.
  - **A smooth progress metric:** the share of functions transplanted with all tests still passing.
  - **A way to split a whole-program problem into function-sized steps** without losing the whole-program check.
- **Caveats.** At `-O2`, compilers emit non-standard calling conventions (`.isra`, `.constprop` and `.part` clones; inter-procedural register allocation). Detect those functions and fall back to trace comparison. Prototype transplant mode at the end of M1 or in M2, and keep it only if it measurably improves repair success.

### 11.3 Where the leverage is

- **Type and signature recovery is where whole-program wins over function-level.** Chisel's authors name stripped-signature recovery as their limitation. Whole-program unification, together with runtime evidence (values actually observed at call boundaries), is the advantage function-level tools structurally lack.
- **Deterministic first, LLM second.** Let analyses propose, the LLM refine, and the tests decide. Cache everything.
- **A project that passes the tests but that nobody wants to maintain is just a decompiler with a test suite.** The readability rubric exists to stop the optimizer from producing working but unreadable output. Take it seriously from M3.

### 11.4 Discipline that makes the result believable

- Write the headline sentence (§1.2) first. Every experiment either fills in one of its blanks or doesn't belong in v1.
- Track **cost per binary** from the start. The cost curve as programs get bigger is itself a result people will care about.
- Never write "decompiles any program", "equivalent" or "first". Write what was measured.

### 11.5 For later (the owner's call, not v1)

The strongest contamination control would be a second sealed set **written by a different vendor's model or by humans**: for example, a batch commissioned from Claude, or a small set of human-written programs. An agent-sealed set built inside one model family is good, and a cross-vendor set is better. That is the step that would make the M4 result hard to dispute.

### 11.6 On instructions

`SPEC.md` and `AGENTS.md` were written to be consistent, with each rule stated once. If you find two rules that conflict, follow the precedence in `AGENTS.md` §2 and log the conflict. Don't guess silently.

---

## 12. Repository layout

```
phoenix/                    # git repo (public): github.com/dvgyl/phoenix
  AGENTS.md  SPEC.md  README.md
  tools.lock  pyproject.toml  env.example.sh
  phoenix/                  # pipeline
    ingest/ analyze/ lift/ recover/ generate/ build/ verify/ repair/ package/
    llm/ sandbox/ diff/ transplant/
  ghidra_scripts/  schemas/
  phoenix_eval/             # separate package; never imports phoenix/
  corpus_public/            # toy programs WITH source (development only)
  containers/               # Dockerfiles: amd64 toolchain, arm64 runner, oracle
  tests/
  .github/workflows/        # CI: ubuntu-latest + ubuntu-24.04-arm
  docs/  STATUS.md LOG.md REPORT.md PRIOR_ART.md QUESTIONS.md
         READABILITY_RUBRIC.md corpus_commitments.md adr/

Outside the repo, under $PHOENIX_ROOT (never committed):
  $PHOENIX_ROOT/env.sh  $PHOENIX_ROOT/tools/  $PHOENIX_ROOT/cache/  $PHOENIX_ROOT/runs/
  $PHOENIX_ROOT/sealed/  $PHOENIX_ROOT/holdout/  $PHOENIX_ROOT/worktrees/
```
