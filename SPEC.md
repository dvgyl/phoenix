# Phoenix specification

This document states what Phoenix must achieve and how Phoenix-Bench measures the result.

- `docs/ARCHITECTURE.md` states how Phoenix works.
- `docs/ROADMAP.md` states the milestones, the gates and the budgets.
- `AGENTS.md` states how to work.

If two documents conflict, apply AGENTS.md section 2 Precedence.
Nothing in this document is a result. Each number is a target, a limit or a rule.

---

## 1. Goal and North Star

### 1.1 North Star

Give Phoenix a compiled program without its source. Phoenix gives back a C project that an engineer can read, build on a different processor, and change. Hidden tests show that the project behaves as the original program behaves.

Much software exists only as executables: abandoned tools, vendor programs with lost source, scientific programs that nobody can rebuild, and utilities that run only on x86-64. The current options are emulation, decompilation into code that does not build, or a rewrite by hand. Phoenix turns such an executable back into a maintainable source project, and Phoenix-Bench measures how often this succeeds.

### 1.2 The v1 goal

v1 applies the North Star to stripped Linux x86-64 executables of C command-line programs (section 5).
The v1 goal is met only under section 14.2. This requires a complete v1 experiment and every commitment in sections 4.1, 4.2 and 4.3.
Section 14 separates "v1 experiment complete" from "v1 goal met".

---

## 2. Definitions

### 2.1 Units and terms

| Term | Definition |
|---|---|
| Program | One C command-line program and its source. |
| Binary | One (program, compiler, optimization level) combination, and the stripped x86-64 executable built from it. Example: program `csvsum`, GCC, `-O2`. |
| Level | The optimization level of a binary: `-O0`, `-O1`, `-O2`, `-Os` or `-O3`. The input contract (section 5) accepts each level. The committed and stretch matrices of section 4 do not change. |
| Tier | A size and kind class of programs. Sealed tiers are T0 to T3 (section 10.3). Development tiers are D0 to D3 (section 10.1). |
| Cell | One (tier, level) pair. A cell holds the GCC and the Clang binaries of its programs. |
| Configuration | One of the four builds of a project: {GCC, Clang} x {x86-64, ARM64}. |
| Project | The C11 project that Phoenix writes for one binary (section 7). |
| Pipeline run | One run of `phoenix run` on one binary. |
| Evaluation run | One run of `phoenix-eval` on a set of binaries. |
| Case | One test input: argv, stdin bytes, an initial directory tree and an environment overlay. |
| Held-out set | The hidden cases of one program. Only `phoenix-eval` reads a held-out set. |
| Dev set | The cases that Phoenix generates from the binary during a pipeline run. |
| Match | A project matches the original on a case when these items are equal: stdout bytes; stderr bytes; the termination kind (exit or signal) and its value; and the final directory tree, compared by relative path, entry type, mode, file bytes and symbolic-link target, plus the mode of the root directory. There is no output normalization. A timeout, a resource-limit event or an evaluator error is never a match (section 5). |
| Runner | One execution environment for machine code: Rosetta, QEMU user mode or native hardware. |
| Valid case | A held-out case whose outcome on the original is the same on each x86-64 runner and passes the validation of section 10.6. |
| Cold run | A pipeline run with an empty LLM response cache and an empty stage cache. |
| Lines | The non-blank lines, after the removal of comments, of the `.c` and `.h` files that the build of the committed executable uses. A pinned counting tool gives the count. The count lists test, generated and bundled third-party files separately and does not include them. The tier of each program is fixed before reconstruction (section 10.4). |

### 2.2 Success

A binary is **fully successful** if all of these conditions are true:

1. The project builds with zero errors in all four configurations with the canonical build (section 7.2).
2. Each configuration matches the original on 100% of the valid held-out cases.
3. The project satisfies each rule of section 9 and passes each integrity check. A confirmed violation of a section 9 rule fails the binary, also when the checks accepted the project.
4. The pipeline run read only the binary and its run settings. The run record shows that the pipeline protection profile was active (section 10.5).
5. `phoenix run --replay` writes a byte-identical project from the recorded LLM responses.
6. The report lists no unsupported behavior. An unsupported behavior is a check of a fortified library call that the project cannot keep (`docs/ARCHITECTURE.md` section 9.1). A confirmed observable divergence from the original inside the input contract (section 5) also fails the binary. Record the case or other reproducible evidence of the divergence.
7. The delivered project satisfies sections 7 and 8. The submitted `CMakeLists.txt` equals the canonical template for its file list, and the package passes the checks of section 8.3.

If one condition is false, the binary is a failure. A binary that matches on 99% of the valid cases is a failure. Do not make this definition weaker.
A binary is also a failure if more than 5% of its candidate held-out cases are excluded (section 10.6).

A **program** is fully successful if each of its committed binaries is fully successful.
The committed binaries of a T0, T1 or T2 program are the GCC and Clang binaries at `-O0`, `-O2` and `-Os` (six binaries).
The committed binaries of a T3 program are the GCC and Clang binaries at the level that its build system sets (two binaries).

The **edit-task binary** of a T1 or T2 program is its GCC `-O2` binary.
An edit-task binary is **fully successful and maintainable** if it is fully successful and all of these conditions are true:

1. The literal-mode byte share is 10% or less, as the evaluator measures it (section 2.7).
2. The project has zero register-named locals.
3. The `goto` density is 1.0 or less, as the evaluator measures it (section 2.7).
4. The reconstruction arm passes at least 2 of the 3 edit tasks of the program (section 10.8).
5. The origin map is complete and consistent with the frozen inventory (section 2.7).

### 2.3 Metrics

Each metric uses the numerator and the denominator in this table. Errors, budget failures and pipeline crashes stay in each denominator.

| Metric | Numerator | Denominator |
|---|---|---|
| Binary success rate (cell) | Fully successful binaries of the cell | All binaries of the cell |
| Program success rate (tier) | Fully successful programs of the tier | All programs of the tier |
| Maintainable rate (T1, T2) | Programs whose edit-task binary is fully successful and maintainable | All programs of the tier |
| Held-out cases passed | (binary, configuration, valid case) triples that match | All (binary, configuration, valid case) triples |
| ARM gap, in points | 100 x (binaries whose two x86-64 configurations match on all valid cases, minus binaries whose two ARM64 configurations match on all valid cases) | All binaries of the tier |
| x86-64-only share | Binaries whose two x86-64 configurations build and match on all valid cases and whose ARM64 configurations do not | All binaries of the tier |
| `dev_edge_coverage` | CFG edges (section 2.4) that at least one dev case executes | CFG edges of the functions that are statically reachable from `main` |
| Indirect edge coverage | Indirect call edges that at least one dev case executes | Indirect call edges with a known target |
| Function reachability | Statically reachable functions that at least one dev case enters | Statically reachable functions |
| Escape rate (development only) | Binaries that match on 100% of the dev set in all four configurations and fail at least one valid held-out case | Binaries that match on 100% of the dev set in all four configurations. Report the numerator, this denominator and the count of selected binaries. A zero denominator gives no rate. |
| Truth transplant rate | Reached twin functions with an unchanged interface whose true-source replacement passes the transplant check | Reached twin functions with an unchanged interface |
| Transformed-interface truth rate | Reached transformed-interface functions whose true-source replacement passes the transplant check | Reached transformed-interface functions |
| Theseus fraction | Instruction bytes of the Theseus passing set | Instruction bytes of all functions that the dev set reaches. The denominator is fixed for each binary and dev-set hash. |
| Original-code dependence | Instruction bytes of reached functions outside the Theseus passing set | Instruction bytes of all reached functions |
| Original-data dependence | Bytes of the data objects that the Theseus passing set accesses through the binding header | (reported as a byte count) |
| Negative transplant detection rate | Injected faults that make the transplant check fail | Injected faults in code that the dev set covers |
| First-suspect accuracy | Injected faults where the first suspect contains the faulty function | Injected faults |
| Signature accuracy | Reached functions whose recovered parameter count, parameter widths and return width equal the true source | Reached functions with an unchanged interface |
| Struct field accuracy | True struct fields that a recovered type gives with the correct offset and size | True struct fields that reached functions access |
| Non-default type share | Project functions whose signature uses a project-defined `struct`, `union`, `enum` or `typedef`, or a library type such as `FILE *` | All project functions |
| Literal-mode byte share | Original instruction bytes that the evaluator counts as literal (section 2.7) | Original instruction bytes of the frozen inventory (section 2.7) |
| Register-named locals | Count of locals and parameters with a register name (section 2.5) | (reported as a count) |
| `goto` density | 100 x the count of `goto` statements, after the pinned formatter (section 2.7) | Lines of `src/` and `include/` that contribute to the executable, after the pinned formatter |
| Confidence byte share | Original instruction bytes of the functions with confidence `verified` or `tested`, each byte counted one time | Original instruction bytes of the frozen inventories of all fully successful projects. Unmapped bytes stay in the denominator. |
| glibc-internal symbols | Identifiers in the project source that name a glibc-internal function or object (import table in `docs/ARCHITECTURE.md`) | (reported as a count) |
| Edit-task parity | Edit tasks that the reconstruction arm passes | Edit tasks that the source arm passes, in the same programs |
| Edit-task paired fraction | Edit tasks that both arms pass | Edit tasks that the source arm passes, in the same programs |
| Edit-task pass rate (each arm) | Edit tasks that the arm passes | All edit tasks of all committed programs |
| Branch coverage (adequacy) | Source branches that the held-out cases execute | All branches that `gcov` reports for the program |
| Mutation score (adequacy) | Killed mutants plus confirmed timeouts (section 10.6) | Sampled mutants minus uncompilable mutants minus excluded survivors (section 10.6). A zero denominator fails the threshold. |
| Dev-set mutation score (technique N13) | Mutants of the reconstruction that the dev set kills | Sampled mutants of the reconstruction that compile |
| Integrity failures | Binaries with at least one integrity category | (reported as a count) |
| Cost per binary | US dollars of all LLM calls of one cold pipeline run, failed attempts included | (reported as median and interquartile range for each tier) |
| Time per binary | Machine minutes of one cold pipeline run | (reported as median and interquartile range for each tier) |
| Flip rate (noise) | Binaries whose fully successful result differs between two runs of one commit with the LLM cache off | Binaries of the tier in the noise run (`docs/ROADMAP.md` section 6.1) |

### 2.4 Control flow graph edges and reachability

The lifted control flow graph (CFG) of the original gives the edge universe. Define it before the dev set runs.

- An **intra-procedural edge** goes from one basic block to a successor block in the same function. Fall-through edges, branch edges and jump-table edges count.
- A **call edge** goes from a block with a direct call to the entry of an internal function.
- Return transfers, calls into imported library functions and signal transfers are not edges.
- An **indirect call edge** goes from an indirect call site to a target that a recovered pointer table or an address-taking instruction gives. Indirect call edges are a separate metric.
- An indirect transfer with no known target is **unresolved**. The report gives the count of unresolved transfers.

A function is **statically reachable** if a path of call edges and indirect call edges goes from `main` to the function.

### 2.5 Register-named locals

A local or a parameter is register-named if its name, compared without case, has one of these forms:

- an x86-64 register name (for example `rax`, `eax`, `ax`, `al`, `r8d`, `xmm3`), with or without a numeric suffix;
- a decompiler register form that contains such a name (for example `in_RAX`, `unaff_RBX`, `extraout_EDX`).

### 2.6 Function confidence

The report gives one confidence value for each function:

- `verified`: the function is in a project that matches on 100% of the dev set in all four configurations, and the dev set executes 90% or more of the function's CFG edges. A function with zero CFG edges is `verified` only when the evaluator observes that a dev case enters it and the call completes.
- `tested`: the function is in such a project, and the dev set executes the function, but less than 90% of its edges.
- `unverified`: no dev case executes the function, or its draft failed, or its project fails a dev case in any configuration. Each function that neither rule above covers is also `unverified`.

Unmapped original bytes get no confidence credit (section 2.7).

### 2.7 Evaluator-owned maintainability inputs

`phoenix-eval` measures the maintainability metrics. The submitted labels are inputs to its checks, not results.

- Before drafting, the evaluator freezes the inventory of original functions and instruction ranges of the binary.
- The evaluator checks `origin_map.json` against that inventory and the accepted draft and edit records. Each original instruction byte counts one time.
- An unmapped byte counts as literal. A byte with a literal implementation counts as literal. A byte with an `idiomatic` label that the checks do not support counts as literal.
- An extracted helper inherits the bytes of its parent function. It adds no bytes to the denominator.
- The evaluator measures the `goto` density after the pinned formatter, without comments and blank lines, on the source that contributes to the executable.
- The evaluator pins the formatter and the register-name patterns of section 2.5 before the freeze.
- An incomplete or inconsistent origin map disqualifies the project from "fully successful and maintainable".

---

## 3. The v1 headline claim

The headline uses this template. Each value in angle brackets is a measured value.

> "On Phoenix-Bench Sealed-B, Phoenix received only stripped x86-64 Linux executables. It reconstructed <Xn> of the 372 committed agent-written binaries (<X>%; tiers T0 to T2 at `-O0`, `-O2` and `-Os`; <Xa>% of all 496 T0 to T2 binaries; <XPn> of 62 programs in all committed variants) and <Yn> of the <Yd> committed binaries (<Y>%) of <N> human-written programs first published after the latest training cutoff of each model that it used (tier T3; <YPn> of <N> programs in both committed variants), as C11 projects. Each project builds with GCC and Clang on x86-64 and ARM64 and passes 100% of the valid hidden differential tests on both architectures (<E> excluded cases). The hidden tests execute <C>% of the source branches. <M>% of the T1 and T2 programs were also fully successful and maintainable. An engineer agent passed <P>% as many change tasks on the reconstructions as on the original sources. The median cold-run cost was <$Y> and <Z> machine minutes for each binary."

Rules for the headline:

1. Headline numbers come only from the preregistered Sealed-B run on the tag `v1-freeze` (section 10.7).
2. If Sealed-B does not exist, the report gives the Sealed-A validation results only. The report then states that the headline is not measured.
3. If a training cutoff of a model is not documented, the public release date of that immutable model version replaces the cutoff (section 10.7, item 2). The headline wording and the label "post-cutoff" stay.
4. `<P>` is the edit-task parity over all committed programs (section 10.8).
5. `<X>` uses the 372 committed T0 to T2 binaries as its denominator, because each commitment uses committed cells. The same sentence gives `<Xa>`, the rate over all 496 T0 to T2 binaries, including `-O3`.
6. `<C>` is the mean over programs of the lowest branch coverage of each program across its scored variants. Each program counts one time.

---

## 4. Targets

All targets apply to the frozen run on Sealed-B. A target is met when the point estimate reaches the value. Decide each target from the integer counts of section 12.1, before rounding. Section 12 gives the interval for each estimate.

### 4.1 Success commitments

Each cell value is the binary success rate, GCC and Clang together.

| Tier | `-O0` | `-O2` | `-Os` |
|---|---|---|---|
| T0 (300 lines or less) | 95% | 90% | 90% |
| T1 (301 to 1,500 lines) | 85% | 75% | 75% |
| T2 (1,501 to 6,000 lines) | 65% | 50% | 50% |

T3: 30% or more of the T3 binaries are fully successful, and 5 or more T3 programs are fully successful.

### 4.2 Maintainability commitments

- Maintainable rate: 60% or more on T1, and 35% or more on T2.
- Edit-task parity over the fully successful programs: 0.70 or more on T1 and T2 together. The edit-task paired fraction over the same programs is also 0.70 or more.
- An empty cohort or a zero denominator gives `not measured`, and the commitment is unmet (section 10.8).

### 4.3 Other commitments

- ARM gap: 3 points or less in each tier. The x86-64-only share is also 3% or less in each tier. Compute both values from unrounded counts.
- Confidence byte share: 85% or more. If no project is fully successful, this commitment is unmet.
- glibc-internal symbols: zero in each project.
- Median cost per binary: $3 or less for T1, and $15 or less for T2.

### 4.4 Stretch targets

These targets define a landmark result.

| Tier | `-O0` | `-O2` | `-Os` | `-O3` |
|---|---|---|---|---|
| T0 | 100% | 97% | 97% | 90% |
| T1 | 95% | 90% | 90% | 80% |
| T2 | 85% | 75% | 75% | 60% |

- T3: 50% or more of the T3 binaries. One fully successful T3 program above 10,000 lines.
- Maintainable rate: 80% or more on T1, and 60% or more on T2. Edit-task parity and the edit-task paired fraction over the fully successful programs: 0.90 or more each.
- Program success rate: 70% or more on T1.
- Scale: one fully successful T3 program above 25,000 lines. If Sealed-B has no eligible program of this size, the report states that this target was not measured.
- No unverified code: in 50% or more of the fully successful T1 projects, each function has the confidence `verified`.
- Upstream-patch parity on T3: for each fully successful T3 program, take one real change that its authors made after the sealed commit. An engineer agent applies the same change request to the reconstruction. The changed reconstruction passes the authors' updated tests.
- Reverse direction: the same pipeline reconstructs stripped ARM64 executables of the T1 programs into projects that also pass on x86-64, with T1 `-O2` at 60% or more. This input is outside the v1 input contract. It is a demonstration only.
- External comparison: the 104 GNU coreutils programs of "Recompilation Is Not Enough", with the Phoenix rules added (ARM64, hidden generated tests). Target: more than 91 of 104. Describe this comparison as a public benchmark with a contamination risk, because current models can have these programs in their training data. Report the published test gate (selected official tests and smoke checks) and the added Phoenix gate separately. Claim a direct performance gain only after both methods are scored on the same roster and test protocol. Do this comparison only after the frozen run.

`-O3` binaries are in Sealed-B. Their results have no commitment.

---

## 5. Input contract

A v1 input binary is:

- ELF64, x86-64, Linux, stripped (`strip --strip-all`);
- compiled from C by GCC or Clang at `-O0`, `-O1`, `-O2`, `-O3` or `-Os`, without link-time optimization;
- dynamically linked against glibc;
- single-threaded, with no `fork`, no `exec` and no network;
- deterministic for a given argv, stdin, environment and input file tree;
- limited in input and output to argv, stdin, stdout, stderr, a working directory tree, a fixed environment and the exit status.

The pipeline receives the binary and its run settings (cost cap and execution budget, section 12.3). It receives no source, no other binary of the same program, and no held-out data.

The Corpus Author (or the Dev Author for `corpus_dev`) records the source language, the compiler, the effective flags and the link settings of each binary. These records decide eligibility. The pipeline never receives them. If `ingest` rejects a committed binary, the binary is a failure.

Runtime contract. The frozen evaluator pins the Linux runtime image and its supported libraries, `argv[0]`, the locale, the time zone, the working directory, the umask, the rules that apply the environment overlay of a case, and the resource limits. Each execution starts from a new copy of the case image. A timeout, a resource-limit event or a launch failure is a runner error. It never counts as a match (section 2.1).

---

## 6. Out of scope for v1

Each item is a later step on the ladder in `docs/ROADMAP.md`. It is not a silent omission.

- C++, Rust and Go inputs;
- static binaries, musl binaries and link-time optimization;
- threads, and signals other than default termination;
- `mmap` of files;
- output that depends on time, process ID or randomness;
- graphical programs, servers and shared libraries;
- just-in-time or self-modifying code, obfuscation and packing;
- PE and Mach-O inputs, and ARM64 inputs (except the reverse-direction demonstration in section 4.4).

---

## 7. Output contract

### 7.1 Project layout

For each input binary `foo`, Phoenix writes `out/foo/` with these files:

| Path | Content |
|---|---|
| `CMakeLists.txt` | The canonical template of section 7.2 for the project's file list. |
| `src/*.c`, `include/*.h` | C11 source with POSIX calls, grouped into modules. |
| `tests/` | Replayable dev cases: inputs and expected outcomes. |
| `PHOENIX_REPORT.md`, `phoenix_report.json` | The report of section 8. |
| `origin_map.json` | For each project function: the original address ranges, the mode (`idiomatic` or `literal`), and the parent function of an extracted helper. |

### 7.2 Canonical build

`phoenix_eval/submission.py` writes the canonical CMake template for a file list. The template compiles each `src/*.c` file with `include/` on the include path and these flags:

`-std=c11 -O2 -Wall -Wextra -ffp-contract=off -fno-strict-aliasing -fwrapv -fsigned-char`

The template also keeps the hardening flags of `docs/DECISIONS.md` entry 10: `-fstack-protector-all`, full RELRO and immediate binding. R0 uses the M1 build profile. The canonical template starts in R1.

The template links with `-lm`. The evaluator compares the submitted `CMakeLists.txt` byte for byte with the canonical template for the submitted file list. A difference fails the binary (section 2.2, condition 7). The evaluator also builds the delivered package offline in all four configurations, with only its own sources and the pinned system toolchain and libraries. The report states that the build uses `-fsigned-char`.

### 7.3 Source rules

The source must:

- compile with zero errors in all four configurations, with warnings counted and reported;
- contain no inline assembly, no load address of the original, no x86 intrinsics and no `long double`;
- use recovered `struct`, `union`, `enum` and `typedef` types where the evidence supports them;
- use names that have evidence (a string, an import, a constant or a role). Otherwise the source uses neutral names such as `fn_401a30` and `g_4a30`. The source never uses a name without evidence;
- mark each `unverified` function with the comment `/* PHOENIX-UNVERIFIED: <reason> */`.

---

## 8. Report contract

### 8.1 For each function

- the address ranges in the original;
- the status and the confidence (section 2.6);
- the recovered signature and its evidence;
- the mode (`idiomatic` or `literal`).

### 8.2 For each binary

- the build result and the warning count of each configuration;
- the dev-set pass rate;
- `dev_edge_coverage`, indirect edge coverage, function reachability and the count of unresolved transfers;
- the Theseus fraction, the original-code dependence and the original-data dependence, when the transplant mode ran;
- the count of functions for each status;
- the literal-mode byte share, the register-named locals, the `goto` density and the non-default type share;
- each untyped data object above 256 bytes, and each raw object above 4 KiB with its justification;
- the statement that the build uses `-fsigned-char`;
- known divergences, with the reason for each. A confirmed divergence inside the input contract fails the binary (section 2.2, condition 6);
- each unsupported behavior (section 2.2, condition 6);
- each model used, by role and model identifier, with the reasoning effort of each call class;
- tokens, cost in US dollars and machine minutes.

### 8.3 Schemas and package check

- The frozen harness owns versioned schemas for `phoenix_report.json`, `origin_map.json` and the dev-case replay format in `tests/`.
- The schemas define the required fields, units, allowed values, address conventions and the value for an unavailable result.
- The function report and the origin map use the same stable function IDs.
- The evaluator validates the complete package against the schemas. A package that fails validation fails the binary.
- The evaluator records the held-out verdicts separately from the report of the pipeline.

---

## 9. Integrity rules

`phoenix-eval` applies these rules to each project. A project that breaks one rule is a failure, whatever its test results. A confirmed violation fails the binary, also when the checks accepted the project (section 2.2, condition 3).

Independently compiled C can give the same machine code as the original. Such identical bytes from the same compiler are not a violation. The reuse of original instructions as program data or as executable logic is a violation of rule 1.

The checks are heuristic. Each check finds known forms of a forbidden technique. A passing check does not prove that a project contains no other form. The report states this limit.

| Rule | Requirement | Detection |
|---|---|---|
| 1. No embedding of the original | The project contains no original `.text` bytes, no emulator or interpreter of the original, and no way to load or execute the original. | (a) No 64-byte window of the original `.text` in any source literal or initializer. (b) No such window in the non-executable data sections of a built executable (`.rodata`, `.data`, `.data.rel.ro`), without the ranges that the C runtime start-up objects contribute. The built code sections are not checked, because one compiler can give the same machine code as the original from honest source. (c) No function holds a dispatch `switch` or a computed `goto` on values equal to 16 or more original code addresses. (d) No pointer to memory that the project makes executable. |
| 2. Data only as typed data | Constants and strings from the original data appear only as typed C initializers. | A raw object above 4 KiB needs a justification entry in the report. The non-pointer bytes of a constant table must be all zero or present in the original data. |
| 3. No output memorization | No lookup table keyed on test inputs. | A string literal longer than 32 bytes that equals a dev-test output and is absent from the original data is a failure. New short strings, such as diagnostics, are permitted. |
| 4. No source access | The pipeline never reads a sealed source, a held-out set or a `corpus_dev` source. | The protection profile of section 10.5 denies the reads. The run record shows the denial probe. |
| 5. Approved calls only | The project calls only its own functions, function pointers, and the functions on the approved call list. | `phoenix_eval/integrity.py` holds the approved call list. The list never contains `mmap`, `mprotect`, `dlopen`, `dlsym`, `fork`, `system`, `popen`, `ptrace`, `syscall` or a function of the `exec` family. |

The integrity checks do not restrict function names, function counts or control flow counts. A project can rename functions, extract helpers, use function pointer tables and add short diagnostic strings.

Three fixture suites test the checker:

- The **cheat suite** holds known cheats: embedded `.text`, memorized outputs, an interpreter of the original and a loader of the original. The checker must reject 100% of it.
- The **honest suite** holds honest projects: renamed functions, extracted helpers, function pointer tables, new short diagnostic strings, and machine code from the same compiler that equals the original. The checker must accept 100% of it.
- The **challenge suite** holds cheats in new forms. The Reviewer role writes it, not the engineer who changes the checker. Add each new cheat form to the suite when someone finds it. The Reviewer commits the SHA-256 of the suite before the frozen checker is tested on it. The checker must reject each fixture of the suite that uses a confirmed forbidden technique.

The checker must reject each confirmed violation in the cheat suite and the challenge suite, and accept each project in the honest suite. The report gives the fixture count, the verdicts and the hash of each suite, and the limits of the checks. A missed challenge fixture prevents an integrity-qualified claim from that freeze. A later fix of the checker does not change the earlier result.

---

## 10. Phoenix-Bench

Phoenix-Bench is the benchmark: the corpora, the held-out sets, the harness (`phoenix-eval`) and the rules in this section.

### 10.1 Three corpora

| Corpus | Source visible to engineers | Use | Location |
|---|---|---|---|
| `corpus_dev` (tiers D0, D1, D2, D3) | yes | All development. Engineers read the sources and the failing held-out cases to find causes. | repository, `corpus_dev/` |
| Sealed-A (existing sealed T0, T1, T2, T3) | no | Validation at milestone gates. Detection of overfit to `corpus_dev`. | `$PHOENIX_ROOT/sealed`, `$PHOENIX_ROOT/holdout` |
| Sealed-B (new) | no | One frozen run. The only source of headline numbers. | `$PHOENIX_ROOT/sealed_b`, `$PHOENIX_ROOT/holdout_b` |

A recovery cycle (`docs/ROADMAP.md`, R8) adds one new sealed set with the rules of Sealed-B: Sealed-C, then Sealed-D, and so on. Each set has its own paths, for example `$PHOENIX_ROOT/sealed_c` and `$PHOENIX_ROOT/holdout_c`.

The development tiers use the sizes and kinds of the sealed tiers: D0 as T0, D1 as T1, D2 as T2. D3 holds real programs first published after the training cutoff, with visible source. No D3 program is in a sealed set.

Rules for `corpus_dev`:

- The pipeline process never reads the `corpus_dev` tree of any checkout, the git object stores and history of any checkout, an unstripped twin binary, or a binary under `$PHOENIX_ROOT/dev_bin` other than its own input copy. The pipeline protection profile denies these reads (section 10.5).
- The pipeline code contains no logic for a specific program. `scripts/check` searches `phoenix/` for the names and the unique strings of the `corpus_dev` programs.
- Each `corpus_dev` program has a held-out set made with the procedure of section 10.6. Thus the escape rate is measurable during development.
- Each `corpus_dev` binary has an unstripped twin: the same build with `-g` and without `strip`. The twin gives the map from source functions to addresses for the truth transplant. A twin is valid only if its `.text` bytes equal the `.text` bytes of the stripped binary.

### 10.2 Sealed-A

Sealed-A is the existing sealed corpus. Its hash commitments in `docs/corpus_commitments.md` stay valid.

| Tier | Programs | Status |
|---|---|---|
| T0 | 10 | Evaluated at the earlier M1 milestone. It is a validation set, not a clean measurement. |
| T1 | 15 | Not evaluated yet. The programs span a narrow size range (304 to 316 lines in the count of the Corpus Author). |
| T2 | 10 | Not evaluated yet. |
| T3 | 5 | Not evaluated yet. Some first-publication dates are not proved. |

Rules:

- Do not change or rebuild a Sealed-A program.
- If a Sealed-A tier lacks the adequacy numbers of section 10.6, the Corpus Author adds held-out cases. The Corpus Author writes a new versioned archive (for example `t1-inputs.v2.tar.gz`) and adds a new commitment line. The earlier commitment lines stay.
- Report the T3 programs with unproved first-publication dates separately from the other T3 programs.
- Make at most three Sealed-A evaluation runs before the freeze. `docs/ROADMAP.md` names the milestones of these runs. Each run gets a number in `docs/SCOREBOARD.md`. The report shows each run.
- The report lists the size limits of Sealed-A as a limitation.

### 10.3 Sealed-B content

| Tier | Programs | Lines | Kinds |
|---|---|---|---|
| T0 | 12 | 300 or less | statistics, checksums, encoders |
| T1 | 30 | 301 to 1,500 | configuration and CSV transformers, calculators, codecs, image filters; with structs, function pointers, `switch`, recursion and `getopt` |
| T2 | 20 | 1,501 to 6,000 | bytecode virtual machines, formatters, markup renderers, archivers; multiple files, hash tables, linked structures |
| T3 | 20 or more | 300 to more than 10,000 | real open-source command-line programs written by people and first published after the latest training cutoff of each model used (section 10.7) |

Size spread:

- In T0, T1 and T2, at least 20% of the programs are in each quarter of the tier's line range. The quarters are: T0: 1 to 75, 76 to 150, 151 to 225, 226 to 300 lines. T1: 301 to 600, 601 to 900, 901 to 1,200, 1,201 to 1,500 lines. T2: 1,501 to 2,625, 2,626 to 3,750, 3,751 to 4,875, 4,876 to 6,000 lines.
- In T3, at least 5 programs have more than 3,000 lines, and at least 2 programs have more than 10,000 lines. Add one program above 25,000 lines if an eligible program exists.

Builds:

- Each T0, T1 and T2 program: {GCC, Clang} x {`-O0`, `-O2`, `-Os`, `-O3`}. Thus T0 to T2 have 496 binaries.
- Each T3 program: {GCC, Clang} at the level that its build system sets.
- All builds are stripped, PIE as the pinned toolchain sets it, and made in the pinned `linux/amd64` container.

Edit tasks: each T1 and T2 program has 3 edit tasks (section 10.8).

### 10.4 Sealing

- The Corpus Author writes and seals Sealed-B (role in AGENTS.md section 6 Models, roles and reasoning effort). It writes only to `$PHOENIX_ROOT/sealed_b` and `$PHOENIX_ROOT/holdout_b`.
- The Corpus Author never reads `corpus_dev`, the pipeline prompts or the dev-set code of the pipeline. Thus Sealed-B does not follow the style of the development programs.
- At creation, the Corpus Author commits the SHA-256 of the source archive, the held-out archive and the edit-task archive to `docs/corpus_commitments.md`.
- The release manifest gives for each binary: name, tier, compiler, flags, SHA-256 and a one-line category. It gives no description of behavior.
- T0 to T2 programs are new designs. They are not ports or copies of known tools.
- For each T3 program, the Corpus Author records: the first publication date, the repository URL, the commit, the license, and the documented training cutoff of each model used in reconstruction. A program with an earlier public ancestor is not eligible.
- For each T3 candidate, the Corpus Author also keeps dated evidence of human authorship, the earliest public availability, the search for earlier public ancestors and the exact source revision. It records each exclusion and its reason. The evaluator verifies the effective model versions and their cutoff or release records.
- A T3 program is eligible when its first publication is after the documented training cutoff of each model that can influence its reconstruction. For a model without a documented cutoff, the first publication must be after the public release of that immutable model version. Both cases use the label "post-cutoff" (section 10.7, item 2).
- Before selection, commit the candidate search, the selection order, the counting tool of section 2.1 and the tier membership rules. Fix the tier of each program before reconstruction. Keep each selected program in its denominator.
- For each binary, record the source language, the compiler, the effective flags and the link settings (section 5).
- Each report states that an agent sealed the corpus, not a person.

### 10.5 Protection of hidden data

`phoenix_eval/protection.py` holds the only list of protected paths and the profile of each role. `scripts/launch-role <role> -- <command>` runs a command under the profile of the role. The host sandbox applies the profile: `sandbox-exec` on macOS, `bwrap` on Linux.

| Path | `pipeline` | `engineer` (workers) | `dev-author` | `corpus-author` | `evaluator` |
|---|---|---|---|---|---|
| `$PHOENIX_ROOT/sealed`, `holdout`, `sealed_b`, `holdout_b`, and the paths of each later sealed set | denied | denied | denied | read and write | read |
| `$PHOENIX_ROOT/sealed_runs`, and the earlier sealed T0 records `$PHOENIX_ROOT/runs/m1-t0-*` | denied | denied | denied | denied | read and write |
| `$PHOENIX_ROOT/sealed_work` (private work directories of sealed runs) | denied, except the work directory of its own binary (read and write) | denied | denied | denied | read and write |
| `corpus_dev/*/src`, `corpus_dev/*/holdout`, `corpus_dev/*/tasks`, unstripped twins | denied | read | read and write | denied | read |
| `phoenix/analyze`, `phoenix/devset`, `phoenix/generate/prompts` (dev-set code and prompts) | read | read and write | denied | denied | read |
| other files in `phoenix/` | read | read and write | read | read | read |

Rules:

- The repository rows apply to the main checkout and to each registered worktree under `$PHOENIX_ROOT/worktrees/`. Each copy of a protected path gets the same rule.
- The `pipeline` profile also denies: the whole `corpus_dev` tree of each checkout; the git object stores and history of each checkout; each binary under `$PHOENIX_ROOT/dev_bin`; held-out data; and earlier evaluation records under `$PHOENIX_ROOT/runs` and `adequacy_runs`. The only exceptions are the input copy of the binary and the run directory of the current pipeline run.
- The `corpus-author` profile denies all of `corpus_dev`.
- The lead model's session runs without a profile, because it starts the evaluator. AGENTS.md section 4 Hard rules forbids the lead model to open the sealed paths, `sealed_runs` and `sealed_work`.
- Only `phoenix-eval` reads or writes `sealed_runs`. For each binary and arm of a sealed run, the evaluator stages the binary under an opaque identifier in an empty private work directory under `$PHOENIX_ROOT/sealed_work/`. The pipeline and its tools can access only that binary, the pinned tools and settings, and the artifacts of their own run. They cannot access sibling work directories, corpus metadata, scoring records or external source repositories.
- An evaluator-controlled broker gives the pipeline remote model access, with retrieval disabled. The evaluator denies each other network access.
- The evaluator captures the project and closes the pipeline access before the hidden tests start. It hashes the project, imports the project and the ledger into `$PHOENIX_ROOT/sealed_runs/<run_id>/`, and deletes the work copy. It records the effective policy and the probe results. A failed protection check fails the binary.
- `phoenix-eval` exports only the aggregate scoreboard of the run (aggregate numbers and failure categories). The lead model never copies a file from a sealed directory and never lists one.
- A sealed evaluation run starts only from a tagged commit, with the preregistration of section 10.7, item 6.
- A test proves the denied reads of each profile before any corpus work. The test covers the main checkout and a worker checkout. Synthetic denial fixtures prove each pipeline denial of this section before the next reconstruction. A test with synthetic material proves the staging flow before Sealed-A run 1. `phoenix-eval probe` runs the checks on the real protected directories and returns only one boolean for each check.

### 10.6 Held-out sets and adequacy

Rules for each held-out set:

- The held-out generator is a different implementation from the Phoenix dev-set code. It uses a different seed and knowledge of the source. Its author does not read the dev-set code or the prompts of the pipeline.
- Each T0 and D0 binary has 100 or more distinct valid cases. Each other binary has 200 or more distinct valid cases. The held-out set contains error cases: bad options, missing files and malformed input.
- Freeze the case IDs, the outcomes and the exclusion reasons before reconstruction.
- The case minimum and the adequacy thresholds apply to each distinct set of valid cases that scores a binary.
- A program enters a new sealed roster only when it meets the applicable thresholds. A correction after the freeze never improves a primary score.

The author of the corpus (Dev Author or Corpus Author) validates each held-out case:

1. Build the true source with the canonical flags of section 7.2, with GCC and Clang, on x86-64 and on ARM64. Add one ARM64 build with `-fsanitize=address,undefined`.
2. Run the case on each build and on the original binary under each x86-64 runner, three times.
3. Exclude the case if any two outcomes differ, or if a sanitizer reports an error.
4. Record the count of excluded cases for each binary. If more than 5% of the complete candidate set of a binary is excluded, the binary counts as failed.

The oracle pins one QEMU `-cpu` model, and one `GLIBC_TUNABLES` hardware-capability mask for all x86-64 runners. `tools.lock` holds both values. Thus glibc selects the same `libm` and string-function variants on each runner.

Adequacy procedure (`tools/adequacy.py`):

1. Branch coverage: build the source at `-O0` with GCC `--coverage`. Run the valid held-out cases. Count branches with `gcov -b -c` from the pinned GCC. No branch is excluded.
2. Mutation: use `mull` with the pinned version if it runs in the toolchain container. Otherwise use the project source mutator. Both use this fixed operator set: arithmetic operator replacement, relational operator replacement, logical connector replacement, integer constant replacement (`c` to `c+1` and to `0`), condition negation, call statement deletion and return value replacement.
3. Enumerate the distinct mutants (mutation sites and operator changes) under the pinned tool and operator set. If there are 300 or fewer, use all of them. Otherwise sample 300 uniformly without replacement, with a seed that is committed before the sampling.
4. Run each mutant on the valid held-out cases. The time limit of a case is 10 times the median of three run times of the original on that case. A difference in outcome kills the mutant. A timeout counts as a kill only when a repeat on the same case under the same limit confirms it, and the original passes under that limit.
5. Report the counts of killed, survived, timed-out, uncompilable and unresolved mutants. An unresolved mutant counts as survived.
6. Exclude at most 20 surviving mutants for each program, across all its scored variants. Each exclusion needs a written semantic proof that the mutation cannot change an allowed outcome in the input scope, an independent review of that proof, and the result of 1,000 more generated cases. Extra passing cases alone do not justify an exclusion. Count the other survivors as survived.
7. Report the raw score (before exclusions) and the triaged score (after exclusions). A zero denominator fails each applicable threshold.
8. Write `adequacy.json` for each program. Only aggregate numbers go into the repository for a sealed program.

Thresholds:

| Tier | Branch coverage | Mutation score |
|---|---|---|
| T0, T1, T2, D0, D1, D2 | 90% or more | 90% or more |
| T3, D3 | 70% or more | reported, no threshold |

The report gives the branch coverage with each success number.

### 10.7 Control of contamination and adaptive overfit

1. T0 to T2 programs are new designs that an agent wrote. T3 programs are written by people and first published after the training cutoff. The report gives the two groups separately. T3 is the strongest claim.
2. Each pipeline run records each model that it uses. T3 eligibility uses the latest documented training cutoff among all of these models. If a model has no documented cutoff, use the public release date of that immutable model version in place of its cutoff. A release date is later than each training cutoff of that version, so the T3 claim still says "post-cutoff" (section 10.4).
3. A sealed evaluation run gives only aggregate numbers and these failure categories: `build_x86`, `build_arm`, `behavior_x86`, `behavior_arm_only`, `integrity`, `timeout`, `budget`, `pipeline_error`. It never gives a failing input, an output difference, or a binary name together with a failure detail.
4. After a Sealed-A run, nobody writes a `corpus_dev` program that copies a sealed category on purpose. A `corpus_dev` program for a failure type (for example, ARM64-only behavior failures) is permitted.
5. Overfit alarm: if a `corpus_dev` binary success rate is more than 15 points above the Sealed-A rate of the same tier and level, stop feature work. The Dev Author writes 6 new programs in a different style. Measure again with one experiment. Then continue.
6. Sealed-B runs one time, on the tag `v1-freeze`. This run is preregistered.
   - Preregistration: before the run, commit the run ID, the freeze commit and the SHA-256 of a manifest. The manifest binds the binaries, the cases, the exclusions, the adequacy records, the edit tasks, the comparison arms, the images, the model versions, the budgets, the seeds, the scoring rules and the retry rules. `scripts/loop sealed-pre` writes the run ID, the tag, the commit and the manifest hash into the preregistration row of `docs/SCOREBOARD.md`.
   - Each assigned binary has one scored outcome for each arm. After a pipeline crash, the evaluator can resume the binary one time from its recorded state, with the remaining budget. A crash that this resume does not recover is a primary failure, not a diagnostic result. The evaluator keeps each completed model response and each charge. A new attempt from the start never replaces the scored outcome.
   - A missing result is a failure. A missing required cell makes the experiment incomplete.
   - Each other rerun needs a new tag. The report shows each run. The preregistered run stays the headline.
7. The model of each role stays fixed after the tag `v1-freeze`.

### 10.8 Edit-task parity

Edit-task parity measures whether a reconstruction is as easy to change as the original source.

- Each T1 and T2 program has 3 edit tasks. A task is a short change request (for example, "add an option `-q` that suppresses the header line") and hidden task tests. The author of the corpus (Dev Author or Corpus Author) makes the task tests from a patched copy of the original source.
- The **source arm** gives the request and the original source to an engineer agent. The **reconstruction arm** gives the request and the project of the edit-task binary to an engineer agent.
- Before sealing a task, the author of the corpus shows two facts: the unchanged original source fails at least one task test, and the reference patch passes all task tests and regression cases in all four configurations.
- The engineer agent is the lead model at `medium` effort. Freeze the prompt, the model version, the tools and the token budget. Both arms use the same frozen values.
- Each (task, arm) pair runs in a new, isolated session with its own copy of the project. No session sees another session or a test result.
- A task passes if the changed project builds in all four configurations, passes the task tests, and passes the regression cases. The regression cases are the valid held-out cases whose outcome the reference patch preserves.
- If the edit-task binary is not fully successful, the reconstruction arm fails each task of that program.
- A program where the source arm passes no task is excluded from the parity and the paired fraction, and counted in the report.
- An empty cohort or a zero denominator gives `not measured`. The applicable commitment is then unmet.
- For each task and arm, the evaluator records the initial project hash, the request, the model settings, the budget, the submitted patch or failure, and the test identities. Replay applies the recorded patch to the recorded project and runs the four builds, the task tests and the regression cases again.

Report these numbers:

- the edit-task parity over all committed programs (the headline value `<P>`);
- the edit-task pass rate of each arm over all 150 assigned tasks;
- the edit-task parity and the edit-task paired fraction over the fully successful programs (the commitment in section 4.2);
- for all committed programs and again for the fully successful programs: the four paired counts (both arms pass, only the source arm passes, only the reconstruction arm passes, neither passes), and the counts of eligible and excluded programs;
- a readability score from the Reviewer role on 5 sampled projects: names, types, module structure and comments, 5 points each. This score is secondary.

Describe the result as the performance of the specified engineer agent.

---

## 11. Baselines and ablations

Report each baseline next to Phoenix on Sealed-B:

1. **Ghidra-raw**: the Ghidra decompiler C plus a generated compatibility header.
2. **M1 pipeline**: the pipeline at commit `6897e47`. It uses one whole-program prompt and whole-program repair. Run it from a worktree at that commit with the current runtime model.
3. **Behavior-only rebuild**: an agent gets execute-only access to the original program, as in [MirrorCode](https://arxiv.org/html/2606.30182v2). It gets no disassembly. It receives only process outcomes, through a broker.
4. **Plain agent**: a general coding agent gets the binary and the pinned Ghidra. It does not use the Phoenix pipeline.

Rules for the comparison:

- Phoenix and both new baselines get identical model access (the runtime model and the strongest available model), prices, per-binary cost caps, original-execution budgets, retry allowance and cold start. Record the actual use.
- Freeze the prompt, the tools and the submission adapter of each arm. Pin the Ghidra compatibility header and the M1 project adapter. Run each frozen adapter on a public fixture before the freeze.
- The input, output, scoring and integrity rules still apply. The evaluator scores each arm with the same canonical build, valid cases, integrity rules and failure accounting.
- Report the four-build behavioral success beside the full success of each arm.
- Primary claim: Phoenix beats a baseline when, over the pooled T1 and T2 committed binaries, the program-clustered paired difference in full success has a one-sided 95% lower bound above zero. There are two preregistered tests, one for each new baseline, with Holm correction.
- A claim that Phoenix beats both baselines "in every cell" needs a one-sided 95% lower bound above zero for each of the 12 cell-by-baseline paired differences (6 T1 and T2 cells, 2 baselines), with programs as clusters. This claim uses no further multiplicity correction (intersection-union principle).
- Report a positive cell estimate without that support as an observed difference. Publish the table of paired differences for each cell and each baseline.

Report each ablation next to Phoenix:

5. Phoenix without transplant (the compile-only mode of `docs/ARCHITECTURE.md`).
6. Phoenix without the generated dev-set steps 1 and 4 (CLI surface recovery and LLM generators).
7. Phoenix without trace evidence (techniques N5 and N9 off).

Run the ablations on T1 and T2 at `-O2` only. Each ablation keeps each setting of Phoenix except the named change. The evaluator scores each baseline and each ablation with the same rules as Phoenix.

---

## 12. Statistics and reporting rules

### 12.1 Estimates and intervals

- Report the binary success rate and the program success rate separately.
- A commitment uses the point estimate. Decide each target from integer counts, before rounding. For each target, report the numerator, the denominator and the minimum integer pass count. Mark a target that did not run `not measured`.
- Minimum integer pass counts of the commitments in section 4 (at the planned Sealed-B sizes):

| Commitment | `-O0` | `-O2` | `-Os` |
|---|---|---|---|
| T0 binaries | 23 of 24 | 22 of 24 | 22 of 24 |
| T1 binaries | 51 of 60 | 45 of 60 | 45 of 60 |
| T2 binaries | 26 of 40 | 20 of 40 | 20 of 40 |

- Maintainable rate: 18 of 30 T1 programs and 7 of 20 T2 programs.
- T3 at the minimum size of 20 programs: both 12 of 40 binaries and 5 of 20 fully successful programs.
- Give each binary success rate of a cell or a tier with a program-clustered bootstrap 95% interval. Resample programs with replacement, 10,000 times, with a recorded seed. Take the 2.5 and 97.5 percentiles. For pooled intervals, resample whole programs within tiers.
- Report the number of distinct programs beside each interval.
- If a bootstrap interval has zero width, label that fact. Also give the Wilson 95% interval for the share of programs that pass with both compilers at that level.
- Give each rate over independent programs (program success rate, maintainable rate) with a Wilson 95% interval. Use Wilson intervals only for such proportions.
- Give the edit-task parity, the edit-task paired fraction, the ARM gap and the x86-64-only share with a program-clustered bootstrap 95% interval.
- For the ARM gap, also report the four counts of each tier and level: both architectures pass, only x86-64 passes, only ARM64 passes, neither passes.
- The intervals describe this benchmark design and its selection procedure. They do not describe programs outside it.
- Give cost and time per binary as the median and the interquartile range for each tier, from cold runs. Failed attempts are included.

### 12.2 Report rules

- `docs/REPORT.md` gives each tier and level, with intervals, baselines, ablations, edit-task results, costs, failure categories, all Sealed-A runs and the limitations.
- The report gives the agent-written tiers (T0 to T2) and the human-written post-cutoff tier (T3) separately.
- The report states: agent sealing, the use of `-fsigned-char`, each model used with its documented training cutoff (or the release date that replaces it, section 10.7), the limits of the integrity checks, the size limits of Sealed-A, and the use of emulated x86-64 runners.- The report never uses the words "equivalent", "any program" or "first" about Phoenix. It gives the measured numbers.

### 12.3 Run settings

The evaluator gives each pipeline run a cost cap. The cap is a safety limit. A pipeline run that reaches its cap stops, and the binary counts as failed with the category `budget`.

| Tier | Cost cap for each binary |
|---|---|
| T0, D0 | $3 |
| T1, D1 | $10 |
| T2, D2 | $30 |
| T3, D3 | $60 |

`docs/ARCHITECTURE.md` gives the execution budget (count of runs of the original) for each tier. `docs/ROADMAP.md` gives the rule that computes the budget of the frozen run.

---

## 13. Prior art and the claimed gap

### 13.1 Existing work

| Work | What it does | What it does not do |
|---|---|---|
| Ghidra, IDA, Binary Ninja, RetDec | Readable pseudo-C | Not designed to recompile; no behavioral check |
| rev.ng | Lifts through QEMU to LLVM and emits C that is meant to recompile | No behavioral harness; the output is not a maintainable project |
| LLM4Decompile, SK2Decompile (ICLR) | LLM decompilation with recompile and re-execute metrics | Function level only |
| DecLLM (ISSTA 2025) | LLM recompilation of decompiled code. Reports whole-binary results, including unstripped Coreutils binaries. Verify the counts from the primary source before the final report. | Unstripped inputs in the whole-binary result; same architecture |
| [PCodeTrans](https://arxiv.org/html/2603.14855v1) (arXiv 2603.14855; [ASE 2026](https://conf.researchr.org/details/ase-2026/ase-2026-research-track/136/PCodeTrans-Translate-Decompiled-Pseudocode-to-Trace-Level-Equivalent-Source-Code)) | Puts one recompiled function into the unmodified original process with `LD_PRELOAD` and a trampoline. Repairs faults from breakpoint trace differences. | The Linux study uses Coreutils and Binutils, x86-64, `-O2` and official test suites. Stripped Coreutils 9.5 reports 96.84% function success and 25.92% file-level success. Stripped Binutils 2.45 reports 98.38% and 25.00%. The binaries are built with GCC. File-level success aggregates isolated function checks. It does not build a standalone project. |
| [DecompileBench](https://aclanthology.org/2025.findings-acl.1194/) (ACL Findings 2025) | Puts a decompiled function into the original program and compares runtime coverage profiles | Function-level decompiler evaluation |
| [MirrorCode](https://arxiv.org/html/2606.30182v2) (arXiv 2606.30182) | Agents rebuild 25 whole programs with execute-only access. Held-out tests score the result. The best model scored 56%. | Its score uses its own task scope and budget. It does not require Phoenix's four build configurations. |
| [SRE-Bench](https://arxiv.org/html/2608.11469v2) (arXiv 2608.11469) | Contamination-free reverse-engineering benchmark built from 19 private programs | Includes anti-analysis protections outside the Phoenix v1 input contract |
| [REBench](https://arxiv.org/html/2604.27319v1) (arXiv 2604.27319) | Measures type and name recovery in stripped binaries | Type inference remains difficult. It does not measure standalone project behavior. |
| [SCRIBE](https://arxiv.org/html/2605.02121v1) (arXiv 2605.02121) | Patches binaries through recompiled decompiled code. Includes an 18-person user study. | Keeps the original binary as the basis of the patched program |
| Agent4Decompile (arXiv 2604.23940) | Multi-agent constraint-guided repair; 50.3% of 1,641 functions | Single function |
| Chisel (arXiv 2608.27981, code released) | Ghidra pseudo-C plus a libFuzzer differential oracle; 79.8% re-executable across stripped and unstripped variants, 72.9% on stripped variants | Single function; stripped signatures are a stated limitation |
| "Recompilation Is Not Enough" (arXiv 2609.07201) | Whole-binary repair of decompiled C; 91 of 104 GNU coreutils programs pass its selected official tests plus smoke checks | Coreutils only, with a contamination risk; needs existing test suites; same architecture; no released artifact |
| [ProgramBench](https://arxiv.org/abs/2605.03546) (arXiv 2605.03546) | Whole-program rebuilding scored with generated hidden tests. Verify the scope and results from the primary source before the final report. | Verify from the primary source before the final report |
| [No Bit Left Behind](https://arxiv.org/html/2609.16423v1) (arXiv 2609.16423) | x86-64 to ARM64 cross-recompilation through LLVM intermediate representation. Verify the results from the primary source before the final report. | The output is not a maintainable C project (verify from the primary source before the final report) |
| [FoxDec](https://ssrg.ece.vt.edu/papers/sefm20.pdf) | Ports recovered C to ARM, with user input. Verify the results from the primary source before the final report. | Needs user input (verify from the primary source before the final report) |
| LLMSbt (arXiv 2610.05999) | x86-64 to AArch64 assembly translation with SMT-checked snippets | The output is assembly, not maintainable source |
| N64 and GBA "matching decompilation" projects with LLM agents | Byte-identical C for each function with the original compiler | Needs the original compiler; not portable |

`docs/PRIOR_ART.md` holds more prior art and the dependencies.

### 13.2 The claimed gap

The studies reviewed do not report all four of these properties in one evaluation (literature search date: `<search date>`). `docs/PRIOR_ART.md`, section "Property evidence", holds the paper-by-property evidence table. This statement covers only the studies reviewed.

1. Whole-program reconstruction.
2. Contamination-controlled evaluation on sealed programs, with a post-cutoff human-written tier.
3. Shown portability: the same project builds and passes on ARM64.
4. A behavioral oracle that needs no existing test suite and keeps the evaluation inputs hidden from the reconstruction process.

The in-situ function check is not new.

Add these two claims only if the measurements support them:

5. Behavioral verification of functions inside the running original (technique N1). For each compiler and level, report the counts and the original instruction bytes of the functions that are identified, reached, eligible for substitution, substituted and passed. State why functions were not eligible. Use "each function" only when each original function of the stated population was reached, substituted and passed.
6. A measured maintainability result (the maintainable rate, the edit-task parity and the edit-task paired fraction, with the source metrics).

Compare each cited study by input, output, unit of scoring, architecture and test access. Claim a direct performance gain over a study only after both methods are scored on the same roster and test protocol.

Phoenix-Bench is a contribution of its own.

---

## 14. Definition of done

### 14.1 v1 experiment complete

The v1 experiment is complete when all of these conditions are true:

1. The preregistered frozen run on Sealed-B is complete on the tag `v1-freeze`, with the baselines and the ablations.
2. `docs/REPORT.md` follows section 12.
3. The harness, the benchmark binaries, the held-out sets, the edit tasks and the committed source archives are published. The Corpus Author publishes each sealed archive through the release channel only after the final authorized scored use of that material. `phoenix-eval` verifies that the published hashes agree with `docs/corpus_commitments.md`. The lead model receives the aggregate results, the publication links and the hash-verification status.
4. After the final authorized scored use, the evaluator releases the recorded model inputs and responses of the sealed run, the project hashes, the verdict of each attempt and the cost records. Until then, it exports only the permitted aggregates.
5. Each headline number reproduces with `phoenix-eval --replay`. The replay rebuilds each scored project from the recorded responses, runs the scoring checks again, applies the recorded edit-task patches (section 10.8) and computes each headline value and each reported count again.

### 14.2 v1 goal met

The v1 goal is met when the v1 experiment is complete and the frozen run reaches each commitment in section 4.1, section 4.2 and section 4.3.

If the frozen run misses a commitment:

- Publish the report as a partial result. Do not call v1 done.
- Continue the work on the roadmap. The commitments do not change.
- The Sealed-B headline stays the preregistered run. A later claim of "v1 goal met" needs a new sealed set, made with the procedure of section 10.3 and section 10.4, and a new preregistered run on a new freeze tag. The recovery cycle of `docs/ROADMAP.md` (R8) gives the procedure. Earlier results are never replaced.
