# Phoenix architecture

This document states how Phoenix works. It describes the target state of the code.

- `SPEC.md` states what Phoenix must achieve. This document uses its definitions.
- `docs/ROADMAP.md` gives the milestone of each part. A label such as "(from R3)" marks a part that arrives in that milestone.
- `docs/plans/R0-reset.md` gives the steps from the current code to the start of this design.

If two documents conflict, apply AGENTS.md section 2 Precedence.

This document uses three role names for models: **lead model**, **strongest available model** and **runtime model** (the model inside the pipeline). AGENTS.md section 6 Models, roles and reasoning effort maps the roles to models. `phoenix/config.py` holds the model identifiers for the pipeline.

Terms used in this document:

| Term | Meaning |
|---|---|
| Original | The stripped x86-64 input binary of one pipeline run. |
| KB | The knowledge base: one SQLite file with all facts about one original. |
| Claim | One statement about one attribute of one KB entity, with its evidence (from R3). |
| Transplant | The replacement of one or more functions inside the running original with reconstructed functions. |
| Twin | The unstripped build of a `corpus_dev` binary (`SPEC.md` section 10.1). Only tools and evaluators read twins. |
| Stage version | The SHA-256 of a stage's source files, the files that it runs, the pinned tool versions that it uses and its configuration values. |

---

## 1. Design principles

1. **The original is an oracle at each granularity.** Phoenix can run the original. It uses the original to check a whole program, one function, one data object and one type layout.
2. **Deterministic analysis proposes. The LLM rewrites. Tests decide.** A fact that a tool can read from the binary is never an LLM task.
3. **Faithful first, readable second.** Phoenix first makes each function correct. Then it makes the code readable. Each readability edit goes through the same checks again. Readability is part of success (`SPEC.md` section 2.2).
4. **One KB.** Each stage reads and writes the KB. Stages do not pass private files to each other. The only other shared artifact is the project directory that `assemble` writes.
5. **One binary, one isolated run.** A pipeline run never uses evidence from another binary, including another binary of the same program. A cache entry keyed by the SHA-256 of the same binary is permitted (section 14.3).
6. **Small code.** `docs/ROADMAP.md` section 6.5 gives the code size limits. A new package or a new artifact format needs a technique card (section 15).
7. **Each technique has a fallback.** When a technique is killed, the pipeline continues with the fallback in its card.

---

## 2. Pipeline and stage interfaces

### 2.1 Stages

```
ingest -> lift -> devset -> recover -> draft -> assemble -> verify -> repair -> polish -> package
```

`trace` and `transplant` are services. Stages call them. They are not stages.

R0 runs the M1 form of the pipeline (commit `6897e47`). The column "From" gives the milestone of the target form of each stage.

| Stage | Reads | Writes (in the KB unless stated) | LLM | From |
|---|---|---|---|---|
| `ingest` | original | binary entity, sections, relocations, imports, input contract result | no | R1 |
| `lift` | original | functions, CFG, call sites, strings, untyped globals, Ghidra C, assembly | no | R0 (M1 form), R1 |
| `devset` | KB, original | test cases, oracle outcomes, coverage | step 4 only | R1 (steps 1 to 3), R3 (step 4) |
| `recover` | KB, observations | signatures, data model, import mapping, CLI surface; struct types from R4 | from R4 | R1 |
| `draft` | KB | one C draft and one status for each function | yes | R1 |
| `assemble` | KB | project directory, `origin_map.json`, Theseus result | no | R1 |
| `verify` | project, dev set | build results, dev results, integrity result, lint result | no | R1 |
| `repair` | KB, failures | new drafts; refuted claims from R3 | yes | R1 |
| `polish` | KB, passing project | names, helpers, modules, comments | yes | R5 |
| `package` | KB, project | output contract files (`SPEC.md` section 7 and section 8) | no | R1 |

Each stage has this interface:

```python
def run(ctx: StageContext) -> StageResult
# StageContext: kb: KB, run_dir: Path, runners: Runners, llm: LLM, budget: Budget,
#               config: Config, jobs: Jobs, mode: Literal["compile_only", "transplant"]
# StageResult: status: Literal["ok", "failed", "skipped"], metrics: dict[str, float], message: str
```

### 2.2 Command line

```
phoenix run <binary> --run-id <id> --cost-cap-usd <usd> --exec-budget <runs> [--mode compile_only|transplant]
            [--runs-root <dir>] [--cache-root <dir>]
phoenix run --resume <run_id>
phoenix run --replay <run_id>
phoenix kb export <kb.sqlite>
```

The evaluator gives the cost cap (`SPEC.md` section 12.3) and the execution budget (section 5.3) for the tier. The default mode is the value `draft_mode` in `phoenix/config.py`. In a sealed run, the evaluator gives a runs root and an empty cache root under `sealed_runs/<run_id>/`.

Each pipeline run writes `runs/<run_id>/<binary_sha256>/run.json`. It holds: the binary SHA-256, the run settings, the mode, each model used with its effort settings, the protection probe result (section 6.3), the stage list, the cost and the machine minutes.

### 2.3 Checkpoints, resume and replay

- Before each stage, `pipeline.py` stores a recoverable KB checkpoint: a copy of `kb.sqlite`, made with the SQLite backup interface, at `checkpoints/<stage>.kb.sqlite` in the run directory.
- After each stage, `pipeline.py` commits the KB transaction. Then it writes `stage.json` atomically (write to a temporary file, then rename).
- `stage.json` holds: `stage`, `status`, `stage_version`, `kb_before`, `input_hash`, `output_hash` and `seeds`.
  - `kb_before` is the KB digest before the stage.
  - `input_hash` is the SHA-256 of the binary SHA-256, the stage version, `kb_before` and the configuration hash.
  - `output_hash` is the KB digest after the stage.
- `phoenix run --resume` validates the checkpoint hash chain in stage order:
  1. A stage is valid if its status is `ok`, its `kb_before` equals the `output_hash` of the preceding stage (for the first stage, the digest of the empty KB), and its recomputed `input_hash` equals the recorded value.
  2. The scan stops at the first stage that is not valid. The latest completed stage is the last valid stage before that point.
  3. Compare only the `output_hash` of the latest completed stage with the current KB digest. If they are equal, resume at the next stage.
  4. If they differ (for example, after an interrupted stage), restore the checkpoint that was stored before the next stage. Check that its digest equals that `output_hash`. Then resume at the next stage.
  5. Each later stage runs again.
- `phoenix run --replay` uses only the recorded LLM responses. A cache miss is an error (`replay_miss`). A replay writes a byte-identical project.
- `scripts/gc` can archive a run directory as `runs/<run_id>.tar.gz` and record its SHA-256. Before a replay, `phoenix-eval --replay <run_id>` restores an archived run to its recorded directory and verifies the archive hash. The archive keeps the recorded responses and the provenance files of the run.

Determinism rules:

- Record each seed (mutation, generator, sampling) in `stage.json` and in the KB.
- Apply results of parallel work in the order of the function address.
- Never use a timestamp to make a decision.
- Store each LLM-generated generator function as text in the KB. Run it with its recorded seed.
- The replay test starts from an empty run directory and includes an interrupted stage. It is part of the R1 gate.

### 2.4 Modes and function statuses

The pipeline has two modes. The mode is fixed for one pipeline run and recorded in `run.json`.

| Mode | How a draft is checked | From |
|---|---|---|
| `compile_only` | The draft compiles. The whole project then runs the dev set. | R1 |
| `transplant` | The draft runs inside the original against selected dev cases (section 7). The whole project then runs the dev set. | R2 |

Function statuses:

```
lifted -> drafted -> compiles -> transplant_pass ---------> integrated_pass
                              -> compile_only -----------> integrated_pass
                              -> unpatchable ------------> integrated_pass
                              -> unsupported_interface --> integrated_pass
                              -> static_only
         draft_failed  (reason: compile | transplant | too_large | budget | refused)
```

| Status | Meaning |
|---|---|
| `compile_only` | The draft compiles. The pipeline ran in `compile_only` mode. |
| `transplant_pass` | The draft passed the transplant check (section 7). |
| `unpatchable` | The entry cannot be patched (section 7.5). Only whole-program checks apply. |
| `unsupported_interface` | The machine interface is not known with certainty (section 5.4.1). Only whole-program checks apply. |
| `static_only` | No dev case executes the function. |
| `integrated_pass` | The function is in a project that matches on 100% of the dev set in all four configurations, and a dev case executes the function. |
| `draft_failed` | Each attempt failed. The best draft stays in the project. |

### 2.5 Shared infrastructure and fallbacks

Keep a shared part while any active technique needs it. Delete it only when the last technique that needs it is killed.

| Shared part | Used by | Delete when |
|---|---|---|
| Instrumentation mode and the tracer image (section 6.2) | N1, N2, N5, N7, N8, N9 | all of these are killed |
| Shim and thunk (section 7) | N1, N2, N8 | N1 is killed and N8 is not active |
| `funcio` plugin (section 5.3) | N5, N7 | N5 and N7 are killed |
| Heap preload and memory-access recording | N9 | N9 is killed |
| `tools/truth.py` (DWARF ground truth) | N1, N4, N5, N9 | never before v1 |

Each technique card in section 15 gives the complete fallback path.

---

## 3. Directory layout

```
phoenix/                    # pipeline; may import phoenix_eval; never imports tools
  cli.py  pipeline.py  config.py  jobs.py
  kb/          store.py  model.py  export.py  schema.sql  claims.py (from R3)
  ingest/      elf.py  contract.py
  lift/        ghidra.py  relocs.py  imports.py  fragments.py
  trace/       plugin_driver.py  coverage.py  funcio.py (R3)  libc_events.py (R3)  heap.py (R4)
  devset/      cli_surface.py  seeds.py  mutate.py  loop.py  minimize.py  llm_generators.py (R3)  mutants.py (R3)
  recover/     signatures.py  globals.py  idioms.py  structs.py (R4)
  generate/    context.py  function.py  regions.py  data.py  project.py  raw.py  runtime/  prompts/
  transplant/  bind.py  build.py  run.py  theseus.py  shim/phx_shim.c  shim/phx_thunk.S  (R2)
  verify/      build.py  diff.py  integrity.py  lint.py  sanitize.py (R3)
  repair/      localize.py  loop.py
  polish/      rename.py  helpers.py  modules.py  (R5)
  package/     report.py
  llm/         provider.py  responses.py  codex.py  ledger.py
phoenix_eval/               # evaluator; never imports phoenix
  case.py outcome.py wire.py tree.py trace.py worker.py docker.py elf.py coverage.py
  build.py toolchain.py integrity.py pair.py platforms.py protection.py provenance.py
  corpus.py m0.py reports.py submission.py run.py quality.py edit_tasks.py (R5)
tools/                      # source-aware tools; never imported by phoenix
  truth.py  adequacy.py
ghidra_scripts/             ExportLift.java
containers/                 Dockerfile  Dockerfile.integrity  Dockerfile.tracer (R2)
                            launch-target.c  launch-instrument.c (R2)  prepare-runtime.sh
                            code-coverage.c  funcio-plugin.c (R3)  heap-preload.c (R4)  c-integrity.cc
schemas/                    lift.schema.json  kb.schema.json
corpus_public/              # harness self-test programs for `phoenix-eval m0`
corpus_dev/                 <program>/src/  <program>/holdout/  <program>/tasks/  <program>/meta.json
                            <program>/adequacy.json  quick.txt
scripts/                    check  loop  gate  gc  launch-role  resize-workspace  build-dev-corpus
                            build-worker  build-integrity  build-tracer (R2)  build-ghidra-native
tests/
docs/                       ARCHITECTURE.md  ROADMAP.md  STATUS.md  SCOREBOARD.md  LOG.md  DECISIONS.md
                            PRIOR_ART.md  corpus_commitments.md  REPORT.md (R7)  plans/
```

Locations outside the repository, under `$PHOENIX_ROOT`:

| Path | Content |
|---|---|
| `runs/<run_id>/` | Pipeline runs and `corpus_dev` evaluation runs. |
| `dev_bin/<program>/<compiler>-<level>/` | Built `corpus_dev` binaries and twins, and `dev_bin/manifest.json`. |
| `sealed/`, `holdout/` | Sealed-A. |
| `sealed_b/`, `holdout_b/` | Sealed-B. |
| `sealed_runs/<run_id>/` | Sealed evaluation runs. |
| `cache/phoenix/` | Stage caches and the LLM response cache (section 14.3). |
| `slots/` | Lock files of the global concurrency budget (section 14.1). |

Do not add a top-level package without a technique card.

---

## 4. Knowledge base

### 4.1 Storage

- One SQLite file for each original: `runs/<run_id>/<binary_sha256>/kb.sqlite`.
- `phoenix/kb/store.py` is the only module that executes SQL.
- Only the pipeline process writes the KB. Parallel workers return results to the pipeline process.
- `phoenix kb export <kb.sqlite>` writes canonical JSON that agrees with `schemas/kb.schema.json`. Use the export for debugging and for prompt context.
- Each entity has a stable identifier that contains its address in the original.

### 4.2 Tables (from R1)

Each table has a `provenance` column. It maps each attribute to `{"source": ..., "ref": ...}`. Sources: `elf`, `reloc`, `ghidra`, `static`, `trace`, `test`, `llm`, `default`.

| Table | Identifier | Columns |
|---|---|---|
| `binary` | `B` | `sha256`, `pie`, `entry`, `main_addr`, `compiler_hint`, `opt_hint`, `sections`, `relocs`, `dev_set_hash`, `oracle` (`dual` or `single_runner`) |
| `functions` | `F:<hex>` | `addr`, `ranges`, `blocks`, `edges`, `callees`, `callers`, `raw_c`, `asm`, `insn_count`, `flags`, `status`, `status_reason`, `mode`, `signature`, `source_text`, `source_hash`, `attempts`, `origin_parent`, `module`, `coverage` |
| `globals` | `G:<hex>` | `addr`, `size`, `align`, `section`, `mutable`, `bytes`, `pointer_slots`, `aliases`, `copy_symbol`, `crt`, `c_type`, `readers`, `writers`, `owner_function` |
| `imports` | `I:<name>` | `raw_name`, `c_name`, `header`, `prototype`, `wrapper` |
| `test_cases` | `K:<n>` | `argv`, `stdin_ref`, `tree_ref`, `env`, `origin` (`seed`, `surface`, `mutate`, `llm`), `seed`, `outcome_ref`, `coverage_ref`, `runners_agree` |
| `meta` | key | schema version, stage versions, seeds |

`functions.flags` is a set of: `leaf`, `noreturn`, `variadic`, `uses_setjmp`, `fragment`, `multi_entry`, `address_taken`, `import_stub`.

A signature value has this shape (section 5.4.1 gives the rules):

```json
{"ret": {"type": "int32_t", "regs": ["rax"]},
 "params": [{"name": "buf", "type": "const char *", "loc": "rdi", "width": 8,
             "stack_off": null, "agg_class": null}],
 "variadic": false, "certain": true,
 "arity_evidence": ["static_callee", "static_callers"]}
```

`loc` is a register name or `stack`. `stack_off` is the offset above the return address for a stack parameter. `agg_class` is the System V class of an aggregate: `INTEGER`, `SSE`, `MEMORY`, or a list of classes for each eightbyte.

From R3, the KB adds the tables `claims`, `call_sites`, `obs_funcio`, `obs_argclass`, `obs_libc` and `obs_cov`. From R4, it adds `types`, `alloc_sites` and `obs_heap`.

### 4.3 Claims (from R3)

From R3, a claim is the only way to set a mutable attribute: `name`, `signature`, `type`, `fields`, `module`.

```
Claim {
  id: integer (assigned in deterministic order),
  subject, attr, value (JSON),
  source: binary_exact | test_verified | trace_observed | static_analysis | llm_proposed | default,
  evidence: [ {kind, ref, note} ],
  depends_on: {function_id: source_hash},   # test_verified claims only
  dev_set_hash,                              # test_verified claims only
  confidence: float (0.0 to 1.0),
  state: active | superseded | refuted | stale,
  refuted_by: [evidence reference],
  stage
}
```

Source ranks: `binary_exact` 100, `test_verified` 90, `trace_observed` 70, `static_analysis` 50, `llm_proposed` 30, `default` 10.

Resolution (`kb/claims.py`, `resolve(subject, attr)`):

1. Use only `active` claims.
2. Select the claim with the highest rank.
3. If two claims have the same rank, select the higher confidence.
4. If the confidence is also equal, select the higher claim ID. A timestamp never decides.

Rules:

- **Supersession.** When a stage writes a new claim with the same subject, attribute and source as its own earlier claim, the earlier claim becomes `superseded`.
- **Promotion.** Only a passing transplant check promotes. For each claim that the check depends on, the pipeline adds a `test_verified` claim with the same value. The check depends on: the signature claims of each replaced function and of its callees, the type claims of each type that the replaced drafts use, and the type claims of each global that they reference. The new claim records the source hash of each draft in the check and the dev-set hash. A whole-program pass promotes no claim.
- **Invalidation.** When a source hash in `depends_on` changes, or the dev-set hash changes, the `test_verified` claim becomes `stale`.
- **Refutation.** Row 3 of the repair decision table (section 5.7) refutes a claim. The refutation records its evidence: the failing set, the source hashes of its drafts and the failing case. If a source hash in that evidence changes, the refutation is reversed and the claim becomes `active` again.

Evidence kinds: `reloc`, `section_bytes`, `import_proto`, `ghidra`, `asm_pattern`, `funcio_values`, `libc_event`, `heap_shape`, `transplant_pass`, `dev_pass`, `llm_rationale`.

### 4.4 Observations (from R3)

Observations are bulk rows. Claims refer to them as evidence.

| Table | Columns |
|---|---|
| `obs_funcio` | `function`, `case`, `call_index`, `int_args[6]`, `fp_args[8]`, `stack_words[8]`, `ret_int[2]`, `ret_fp[2]`, `pointee_samples` |
| `obs_argclass` | `function`, `slot`, `class`, `count`. Classes: `heap_ptr`, `stack_ptr`, `global_ptr`, `string_ptr`, `code_ptr`, `small_int`, `bool`, `wide_int`, `float` |
| `obs_libc` | `case`, `seq`, `import`, `caller_function`, `args_summary`, `ret` |
| `obs_heap` (R4) | `alloc_site`, `off`, `size`, `rw`, `function`, `count` |
| `obs_cov` | `case`, `edge_bitmap_ref` |

Keep at most 32 `obs_funcio` rows for each function. Prefer rows with different values. Observations are examples. They never remove a parameter by themselves (section 5.4.1).

### 4.5 KB interface

```python
class KB:
    @classmethod
    def open(cls, path: Path) -> "KB"
    def transaction(self) -> AbstractContextManager[None]
    def entity(self, id: str) -> Entity
    def functions(self, status: str | None = None) -> list[Function]
    def add_entity(self, e: Entity) -> None
    def set_attr(self, id: str, attr: str, value: object, provenance: Provenance) -> None
    def set_status(self, function_id: str, status: str, reason: str | None = None) -> None
    def set_source(self, function_id: str, c_source: str, mode: str) -> None
    def export(self) -> dict[str, object]
    def digest(self) -> str          # hash of all attributes, sources, statuses and active claims
    # from R3:
    def claim(self, subject: str, attr: str, value: object, source: str,
              evidence: list[Evidence], confidence: float, stage: str) -> int
    def resolve(self, subject: str, attr: str) -> Claim | None
    def refute(self, claim_id: int, evidence: Evidence) -> None
    def add_obs(self, table: str, rows: list[dict[str, object]]) -> None
    def obs(self, table: str, **filters: object) -> list[dict[str, object]]
```

From R3, `set_attr` rejects the mutable attributes. Do not add a method without a caller in the same commit.

---

## 5. Stage specifications

### 5.1 ingest

- Check the input contract (`SPEC.md` section 5). Reject an input with the reason `contract:<rule>`.
  - ELF64, x86-64, an interpreter and a `DT_NEEDED` entry for `libc.so.6`, no `.symtab`.
  - No import of `pthread_create`, `fork`, `vfork`, the `exec` family, `socket` or `system`.
- Parse `.rela.dyn` and `.rela.plt`.
  - Each `R_X86_64_RELATIVE` entry gives one pointer slot in the data.
  - Each `R_X86_64_COPY` entry gives one copy slot with its `.dynsym` name (section 8.2).
  - Each `R_X86_64_GLOB_DAT` and `R_X86_64_JUMP_SLOT` entry gives one import.
- Find `main_addr` from the first argument of `__libc_start_main` at the entry point.
- Read `compiler_hint` and `opt_hint` from `.comment` and from prologue patterns. They are hints for prompts only.

### 5.2 lift

Ghidra 12.2 headless is the only structural lifter. It gives function boundaries, the CFG, the call graph and decompiler C. The assembly text is the ground truth. Ghidra C is a hint. Each prompt that contains Ghidra C also contains the assembly of the same function.

- `lift/ghidra.py: run_ghidra(binary: Path, out: Path) -> Path` writes `lift.json`. The schema is the schema of commit `6897e47`, extended with `blocks`, `edges`, `ranges` and `asm`.
- Give Ghidra the glibc prototypes before decompilation. Thus Ghidra propagates the library types.
- `lift/fragments.py` merges fragments. A range is a fragment if only non-call jumps from one other function enter it. Merge the fragment into that function. This rule handles the `.cold` parts from GCC.
- Delete the Ghidra project directory after the export. The lift keeps only `lift.json`.
- Phoenix uses no second decompiler in v1 (technique X2).

### 5.3 devset and the trace service

The dev set decides the result on the hidden tests. Phoenix cannot check a function that no dev case executes.

**Trace service** (`phoenix/trace`):

```python
def collect(kb: KB, cases: list[TestCase], what: set[str], runners: Runners) -> None
# what is a subset of {"cov", "funcio", "libc", "heap"}
```

| Kind | Mechanism | Execution mode | From |
|---|---|---|---|
| `cov` | `containers/code-coverage.c` on the oracle QEMU (8.2.2). The plugin records each pair of consecutive block-leader hits. The reader keeps the pairs that are CFG edges (`SPEC.md` section 2.4). | evaluator sandbox | R1 |
| `funcio`, `libc` | `containers/funcio-plugin.c` on the tracer QEMU (10.0) | instrumentation | R3 |
| `heap` | memory-access recording in the plugin, plus `containers/heap-preload.c` for `malloc`, `calloc`, `realloc` and `free` with the call-site address | instrumentation | R4 |

Rules for the tracer:

- Build one QEMU 10.0 `qemu-x86_64` from source in `containers/Dockerfile.tracer`. Pin the version and the source hash in `tools.lock`. Do not change the oracle QEMU.
- The build checks that `qemu-plugin.h` declares `qemu_plugin_read_register` and `qemu_plugin_read_memory_vaddr`. If one is absent, technique N5 is killed. There is no `gdbstub` fallback.
- At each function entry, `funcio` reads `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, `xmm0` to `xmm7` and the 8 stack words above the return address. At each `ret`, it reads `rax`, `rdx`, `xmm0` and `xmm1`. For a pointer argument, it reads 32 bytes at the pointer.
- The plugin keeps a shadow call stack to attribute each return to a function. Each frame holds the `rsp` value at the function entry. The plugin pops the shadow stack by `rsp`: at each event, it discards each frame whose saved `rsp` is below the current `rsp`. This handles tail calls and `longjmp`.
- The heap preload scans each live heap object at `free` and at exit. An aligned 8-byte word that points into a live object is a pointer field.

**Dev set construction** (`devset.build(kb, budget) -> None`). Do these steps in sequence:

1. **CLI surface recovery** (`cli_surface.py`). Read the `getopt` option string and the `getopt_long` table from the call arguments: first statically, then from `obs_libc`. Collect the constant strings that the original gives to `strcmp`, `strncmp`, `strcasecmp` and `memcmp`. Collect usage text from `.rodata`. The result is a `CliSurface` record: options, option arguments, keywords, file operands and the use of stdin.
2. **Seeds** (`seeds.py`). Build cases from the `CliSurface`: each option alone, each pair of options, each keyword, empty input, a missing file and a large input.
3. **Coverage loop** (`loop.py`). Mutate cases with `mutate.py`: byte, token, line, argv and file-tree mutations, plus dictionary tokens from step 1. Keep a case if it adds a new CFG edge. Run the loop in batches of 64 cases. Stop after 3 batches with no new edge, or at the end of the execution budget.
4. **Targeted generation** (`llm_generators.py`, from R3). Select the uncovered functions and branches. Give the LLM the Ghidra C of the branch, the path from `main`, the `CliSurface` and 3 near-miss cases. The LLM returns a Python generator function `gen(rng) -> Case`. Run the generator in an isolated container with no network for 200 cases. Keep the cases that add edges. Do at most 3 rounds for each uncovered region.
5. **Oracle.** Run each kept case on the x86-64 runners of the host (section 13). Keep a case only if the runners agree and three repeated runs agree. On a single-runner host, set `binary.oracle` to `single_runner`.
6. **Minimize** (`minimize.py`). Keep a set of cases that preserves the edge coverage, with at most 400 cases. Always keep one case for each exit status and each terminating signal.
7. **Mutant adequacy** (`mutants.py`, from R3, technique N13). After the project matches the full dev set, add the cases that separate surviving mutants of the reconstruction from the reconstruction (section 15.2, N13).

Stop rule: `dev_edge_coverage` reaches 95%, or the execution budget ends. The execution budget is a count of runs of the original:

| Tier | Execution budget |
|---|---|
| T0, D0 | 5,000 |
| T1, D1 | 20,000 |
| T2, D2 | 60,000 |
| T3, D3 | 150,000 |

The stage reports `dev_edge_coverage`, indirect edge coverage, function reachability, the unresolved transfers and the list of unreached functions. The dev-set hash is the SHA-256 of the canonical encoding of the kept cases and their outcomes.

AFL++ is not part of v1. It is the pivot of technique N4.

### 5.4 recover

#### 5.4.1 Signatures (`recover/signatures.py`)

For each function, write one signature (section 4.2):

1. **Arity from static analysis.** Callee view: the argument registers and stack slots that the function reads before it writes them. Caller view: the registers and stack slots that each caller sets before the call. Use the union of the two views if they agree on each location. Trace values are examples and confirmations. A trace value never removes a parameter by itself.
2. **Location, width and class.** Record for each parameter the location, the width in bytes, the stack offset and the aggregate class (section 4.2).
3. **Parameter types.** Use `obs_argclass` (from R3). A slot that always holds a `string_ptr` is `const char *`. A slot that always holds a `code_ptr` is a function pointer. A slot that holds only 0 and 1 is a `bool`-like `int`.
4. **Library propagation.** A value that goes to an import parameter gets the type of that parameter (`FILE *`, `size_t`, `const char *`).
5. **Return.** `void` if no caller reads `rax` or `xmm0` after the call. The trace confirms it.
6. **Certainty.** If the callee view and the caller view disagree, or a caller is unknown (an indirect call with no recovered target), set `certain` to `false`. Do not guess. The function gets the status `unsupported_interface` in `transplant` mode.

In R1 and R2, signatures have the provenance `static`. From R3, they are claims with the source `static_analysis` or `trace_observed`.

#### 5.4.2 Globals and data

Section 8 gives the data model and the emission rules.

#### 5.4.3 Imports and idioms

Section 9 gives the import table, the wrappers and the arithmetic helpers.

#### 5.4.4 Structs (`recover/structs.py`, from R4)

1. Group field accesses by `AllocSite` (`obs_heap`) and by base pointer parameter (static access patterns).
2. Record two kinds of relation between groups:
   - **Type equality**: one value flows between the groups through a call argument, a return value or a store and load of the same global.
   - **Pointer containment**: a field of one group holds a pointer to the other group.
3. Unify groups with a union-find structure on type-equality relations only. A pointer-containment relation links two types. It never unifies them.
4. Recognize these shapes before unification:
   - **Array**: accesses with a fixed stride from one base. The element is the type. One allocation with a size of k times the stride is an array of k elements.
   - **Flexible array member**: a fixed header and accesses past the header whose extent changes with the allocation size.
   - **Interior pointer**: a pointer to an offset above zero inside an object. Record it as (group, offset). It never makes a new group.
   - **Generic allocator**: a function that returns the result of `malloc`, `calloc` or `realloc` with a size from its parameters. Its callers are the allocation sites. The allocator is never one type.
5. If two groups have conflicting evidence (one offset with two sizes, or two incompatible field types), keep separate types.
6. For each type, give the LLM the field table (offset, size, reading and writing functions, pointer targets) and the functions that use it. The LLM returns a `struct` definition with names.
7. Check the definition deterministically. Each observed offset and size agrees with a field. The size agrees with the allocation sizes, after arrays and flexible array members. Reject a definition that fails the check.
8. Emit `_Static_assert(offsetof(...) == ...)` lines into the transplant build. Set `layout_locked` after a transplant pass of each function that uses the type.

Before R4, drafts use the Ghidra types and local casts.

### 5.5 draft

`draft` writes one C function for each function. In `transplant` mode, the check of one function does not depend on the draft of another function. Thus drafts run in parallel through the global concurrency budget (section 14.1).

```python
def draft_function(kb: KB, fid: str, attempt: int, feedback: Feedback | None) -> Draft
# Draft: c_source: str, claims: list[ProposedClaim], mode: Literal["idiomatic", "literal"]
```

**Context** (`generate/context.py`):

- the assembly of the function (ground truth) and the Ghidra C (hint);
- the signature of the function and of each callee;
- the declarations of each global and each type that the function uses;
- the strings that the function refers to;
- at most 8 `obs_funcio` rows for the function (from R3);
- the rows of the import table that apply;
- the portability rules (section 10).

The prompt size limit is a fraction of the runtime model's context window. `phoenix/config.py` holds the fraction (default 0.25) and the window size of each model.

**Region drafting** (`generate/regions.py`). Use it for each function whose assembly text is larger than 16 KB:

1. Split the function into regions at basic-block boundaries. Each region holds at most 12 KB of assembly text.
2. All regions share one local-variable structure, `struct fn_<hex>_locals`. It holds each value that is live across a region boundary.
3. Each region is one function: `static int fn_<hex>_r<k>(struct fn_<hex>_locals *L)`. It returns the index of the next region, or `-1` to return from the function.
4. The function body calls the regions in a loop on the region index. The index is a small integer. It is never an original address.
5. If a region prompt is still above the prompt size limit, or a computed jump crosses a region boundary, the status is `draft_failed` with the reason `too_large`. This is never a crash.

`polish` can later rewrite region code into structured code.

**Output contract.** The LLM returns JSON: `{"c_source": "...", "claims": [{"subject", "attr", "value", "rationale"}]}`. The function keeps its signature. A change of signature is a proposed claim. The pipeline accepts it only after all callers compile and pass their checks again.

**Attempts.** The attempt counter of a function is shared by `draft` and `repair`.

| Attempt | Mode | Model | Effort |
|---|---|---|---|
| 1 | idiomatic | runtime model | `low` below 40 instructions, otherwise `medium` |
| 2 | idiomatic | runtime model | `medium` |
| 3 | literal | runtime model | `high` |
| 4 | literal | strongest available model | `high` |

A function with more than 600 instructions uses literal mode from attempt 1.

**Loop for one function:**

```
for attempt in next_attempts(fid):                 # at most 4 in total for each function
    draft = draft_function(kb, fid, attempt, feedback)
    if not build(draft):                           feedback = compiler errors; continue
    if mode == "compile_only":                     status = compile_only; stop
    if unpatchable(fid):                           status = unpatchable; stop
    if not signature(fid).certain:                 status = unsupported_interface; stop
    cases = select_cases(fid, limit=64)
    if not cases:                                  status = static_only; stop
    result = transplant.check(kb, {fid}, cases)
    if result.passed:                              status = transplant_pass; stop
    feedback = minimized counterexample + first difference + obs_funcio rows of that case
status = draft_failed
```

- **Idiomatic mode** asks for natural C with the same behavior.
- **Literal mode** asks for a statement-by-statement translation of the assembly into C. Local variables replace registers. `goto` is permitted. `polish` improves the result later.
- Literal mode is not an emulator. A draft must not contain a register array, a variable for the processor flags, or a dispatch loop on addresses. `verify/lint.py` rejects these shapes.
- A `static_only` function gets one literal draft.

### 5.6 assemble

- `generate/data.py` emits all data objects (section 8).
- `generate/project.py` writes `src/*.c`, `include/phx_decls.h`, the runtime files of section 9 when needed, `tests/` and `CMakeLists.txt`. Before `polish`, there is one source file for each call-graph cluster.
- `CMakeLists.txt` is the canonical template from `phoenix_eval.submission.canonical_cmake(files)`. The pipeline and the evaluator use the same function.
- `origin_map.json` maps each project function to the original addresses, the mode and, for a helper, the parent function.
- In `transplant` mode, run `transplant.theseus` (section 7.8). Then go to `verify`.

### 5.7 verify and repair

`verify.project(project_dir, cases, configs) -> VerifyResult`:

- builds the project in all four configurations;
- runs the dev set on each configuration;
- runs the integrity check with `phoenix_eval.integrity`;
- runs `verify/lint.py`. Violations of the portability rules (section 10) and the emulator shapes of section 5.5 are blocking failures. Register-named locals, `goto` density, literal-mode byte share and glibc-internal symbols are metrics only. Before `polish`, they never block a stage;
- from R3, builds one ARM64 configuration with `-fsanitize=address,undefined` and runs the dev set (`verify/sanitize.py`). Sanitizer reports are repair input, not a gate.

`repair.localize(kb, failure) -> list[Suspect]` uses this decision table:

| Row | Symptom | Suspects, in sequence |
|---|---|---|
| 1 | Build error | The function or declaration in the compiler message. |
| 2 | A function fails the transplant check (`transplant` mode) | That function. The draft loop continues. |
| 3 | Theseus fails, and each function passes alone | The minimal failing set. From R3, refute the type or signature claim that the functions do not share. |
| 4 | Theseus passes or `compile_only` mode, and the x86-64 project fails | (a) Functions on the failing path with status `static_only`, `draft_failed`, `compile_only`, `unpatchable` or `unsupported_interface`. (b) Data objects that the failing path reads (section 8.4). (c) `main` and start-up code. |
| 5 | x86-64 passes, ARM64 fails | Sanitizer findings. Then the first function where the call sequence differs between the two builds (`-finstrument-functions` logs). Then the portability rules. |
| 6 | Integrity failure | The object or function that the checker names. |

The failing path is the set of functions that the failing case executes. From R3, technique N7 orders this set: compare `obs_libc` of the original with the libc call sequence of the project on the same case. The first different event gives the function.

Counterexample format: the minimized case (argv, stdin of 256 bytes at most, file tree), the expected and the actual first different bytes, and the `obs_funcio` rows of the suspect for that case (from R3).

`repair.fix(kb, suspect, counterexample) -> Draft` calls the draft loop with the counterexample as feedback. One repair round handles one suspect. Limits:

- at most 12 repair rounds for each binary, or the cost cap;
- a round that does not increase the count of passing dev cases or the Theseus fraction is a failed round;
- stop after 3 failed rounds in sequence.

### 5.8 polish (from R5)

`polish` starts when the project builds in all four configurations, matches the full dev set, and has no integrity or portability violation. The maintainability metrics (register-named locals, `goto` density, literal-mode byte share) never block entry to `polish`. Each edit is one transaction: apply, build, run the transplant check for the changed functions (in `transplant` mode), run the dev set, then keep or revert. A failed edit is reverted and not tried again.

Do these steps in sequence:

1. `helpers.py`: rewrite literal-mode and region functions into idiomatic C. Extract a helper where the compiler inlined one (a repeated code shape). Add the helper to `origin_map.json`. Remove register-named locals.
2. `rename.py`: names of functions, parameters, locals, globals, fields and types. One LLM call for each module. A name needs a rationale that cites evidence in the code: a string, an import, a constant or a role (for example, the comparator given to `qsort`). Below confidence 0.6, keep the neutral name.
3. `modules.py`: group functions into source files by call-graph cluster and shared types. Write one header for each module.
4. Comments: one short comment for each non-trivial function. Each `static_only` and `draft_failed` function gets `/* PHOENIX-UNVERIFIED: <reason> */`.

`static_only` and `draft_failed` functions get only steps 2 and 4, because no dev case checks them.

Budget: `draft` and `repair` stop when they reach 80% of the cost cap. Thus `polish` always has 20% of the cap. Budget reductions never remove `polish`.

### 5.9 package

`package/report.py` writes the output contract and the report of `SPEC.md` section 7 and section 8, with the confidence of each function from `SPEC.md` section 2.6.

---

## 6. Execution modes and protection

### 6.1 Evaluator sandbox (unchanged)

The evaluator sandbox runs the oracle, the held-out cases, the dev cases on projects and the coverage plugin. It stays as it is. Its parts are `phoenix_eval/worker.py`, `phoenix_eval/docker.py` and `containers/launch-target.c`: no network, a read-only root, all capabilities dropped, a process limit, `chroot`, `setuid`, resource limits, a `seccomp` deny list, no `LD_` or `QEMU_` environment entries, and no process creation. A change to these parts needs the review of AGENTS.md section 8 Review.

### 6.2 Instrumentation mode (from R2)

Instrumentation mode runs the original with Phoenix code inside the process: transplant (R2), the `funcio` and `libc` tracer (R3), the heap tracer (R4) and N8. It never scores a held-out case.

| Property | Instrumentation mode |
|---|---|
| Image | `phoenix-tracer:<arch>`: QEMU 10.0 `qemu-x86_64`, the plugins and the preload libraries |
| Launcher | `containers/launch-instrument.c` |
| Network | none |
| Root file system | read-only |
| Trusted library mount | `/phx/lib`, read-only: `phx_transplant.so`, the plugin files and `heap-preload.so`, built by the pipeline in the toolchain image |
| Preload | guest only: `qemu-x86_64 -E LD_PRELOAD=/phx/lib/phx_transplant.so`. The QEMU process itself loads no preload library. |
| glibc tunables | the oracle hardware-capability mask (`SPEC.md` section 10.6) plus `glibc.cpu.x86_shstk=off`, given with `-E GLIBC_TUNABLES=...` |
| Memory | a cgroup memory limit (`docker run --memory`). No `RLIMIT_AS`, because QEMU and the sanitizers reserve a large address space. |
| Processes | `--pids-limit 8`: the launcher and the QEMU threads. The launcher starts the QEMU process. The guest has no `fork` (input contract). N8 starts one process for each call, in sequence. |
| Trace output | `/phx/out` on a tmpfs. Each case has an output cap (`trace_cap_bytes` in `config.py`, default 256 MiB). A case that reaches the cap is `trace_truncated` and gives no observations. |
| CPU limit | the per-case CPU limit of the evaluator sandbox |

On a Linux x86-64 host, transplant can run natively with `LD_PRELOAD` on the target in the same container profile. The tracer always runs under QEMU, because it needs the plugins.

A change to the launcher or the profile needs the review of AGENTS.md section 8 Review.

### 6.3 Protection profiles

`phoenix_eval/protection.py` implements the protection table of `SPEC.md` section 10.5.

```python
PROFILES: dict[str, Profile]      # "pipeline", "engineer", "dev-author", "corpus-author", "evaluator"
def guarded_command(workspace: Path, repo: Path, command: tuple[str, ...], profile: str,
                    allow: tuple[Path, ...] = ()) -> tuple[str, ...]
# allow: paths that the profile permits in a denied class, for example the sealed run directory of one binary
def inherited_guard(workspace: Path) -> bool
```

- On macOS, `guarded_command` returns a `sandbox-exec` command with a generated SBPL policy. Path patterns such as `corpus_dev/*/src` become SBPL `regex` rules.
- On Linux, it returns a `bwrap` command. Each protected path becomes an empty `--tmpfs` mount. Glob patterns expand at launch time.
- `scripts/launch-role <role> -- <command>` calls `guarded_command`.
- The pipeline run creates a probe file in its run directory and puts the probe path in `PHOENIX_PIPELINE_GUARD`. The profile denies the probe. `inherited_guard` confirms the denial. `run.json` records `{"profile": "pipeline", "probe_denied": true}`. The evaluator requires this record (`SPEC.md` section 2.2, condition 4).
- The rules apply to the main checkout and to each registered worktree under `$PHOENIX_ROOT/worktrees/` (from `git worktree list --porcelain`). Each repository path pattern, for example `corpus_dev/*/src` or `phoenix/devset`, becomes one rule for each checkout. `guarded_command` generates the profile at each launch, so a new worktree is covered.
- `tests/test_protection.py` checks the generated policy of each profile with a temporary layout. The layout has a main checkout and a worker checkout.
- `phoenix-eval probe` checks the real protected directories of this host. For each profile and each protected path, it attempts one read under the profile. It returns only one boolean for each check. The lead model never lists, opens or copies a sealed directory.

---

## 7. Transplant service (from R2)

Transplant is an R2 experiment with a kill criterion (technique N1). The R1 pipeline delivers value without it, in `compile_only` mode.

### 7.1 Interface

```python
def build(kb: KB, drafts: list[Draft]) -> Path | BuildErrors      # phx_transplant.so, x86-64
def check(kb: KB, fids: set[str], cases: list[TestCase]) -> TransplantResult
# TransplantResult: passed: bool, failures: list[CaseFailure], untestable: dict[str, str]
def theseus(kb: KB, cases: list[TestCase]) -> TheseusResult
# TheseusResult: passing_set, minimal_failing_sets, replaced_bytes, reached_bytes,
#                original_code_bytes, original_data_bytes, fraction, dev_set_hash
```

### 7.2 Binding

`transplant/bind.py` generates `phx_bind.h` from the KB for the transplant build only:

- Each global becomes a macro into the memory of the original: `#define g_4a30 (*(struct T12 *)(phx_base + 0x4a30))`.
- Each function outside the replaced set becomes a macro that calls the original code: `#define fn_1b00 ((int (*)(const char *))(phx_base + 0x1b00))`.
- A call between two replaced functions is a direct C call.
- Imports are normal libc calls. The dynamic linker binds them to the libc of the same process. Thus the original and the replacement share the `stdio` state.
- A static local variable of the original is a global with `owner_function`. The draft uses the bound name.

The same draft text compiles in the transplant build (with `phx_bind.h`) and in the final project (with `phx_decls.h`). A draft never contains an address.

### 7.3 Patching

The constructor of `phx_transplant.so` does these steps before `main` runs:

1. Find `phx_base` with `dl_iterate_phdr`.
2. Map one trampoline page within +/-2 GiB of the image. Try address hints below the image start and above the image end. Check the distance of the result.
3. For each replaced function, write a trampoline entry into the page: `jmp [rip+0]` and the 8-byte address of the function's own thunk entry (14 bytes).
4. Make the entry page writable. Write a 5-byte `jmp rel32` from the function entry to its trampoline entry. Restore the page protection.
5. If no page within +/-2 GiB is available, write the 14-byte absolute jump at the function entry.

The patch and the trampoline change no register. Build the shim with `-fcf-protection=none`.

### 7.4 Thunk

GCC at `-O2` can let a caller of a local function keep values in caller-saved registers that the original callee does not change (interprocedural register allocation). A replacement can change these registers. The thunk protects such callers.

Each replaced function has its own thunk entry. The thunk entry does these steps:

1. Discard dead shadow frames. If the return address on the machine stack is not the address of the return stub, discard each frame whose saved stack pointer value is `rsp + 8` or below. If it is the address of the return stub (a tail call from a replaced function), discard only each frame whose saved value is below `rsp + 8`. A discarded frame belongs to a call that `longjmp` left.
2. Push a frame onto the shadow stack of the shim: the real return address, the stack pointer value after the return (`rsp + 8` at entry), and all caller-saved registers: `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`, `r9`, `r10`, `r11` and `xmm0` to `xmm15`.
3. Replace the return address on the machine stack with the address of the return stub. The stack arguments stay in position. The thunk uses no machine stack, so the 16-byte stack alignment at the replacement entry is the same as at the original entry.
4. Jump to the replacement.

The two cases of step 1 are necessary. A tail call from a replaced function enters with the same `rsp` as its live caller frame, and that frame must stay.

The return stub does these steps:

1. Discard each shadow frame whose saved stack pointer value is below the current `rsp`. Such frames belong to calls that `longjmp` left.
2. Restore each saved register except the registers that the resolved return type writes:

| Return type | Registers that the replacement writes |
|---|---|
| `void` | none |
| integer or pointer, 8 bytes or less | `rax` |
| aggregate of two `INTEGER` eightbytes | `rax`, `rdx` |
| `float` or `double` | `xmm0` |
| aggregate of two `SSE` eightbytes | `xmm0`, `xmm1` |
| aggregate of one `INTEGER` and one `SSE` eightbyte | `rax`, `xmm0` (in the order of the eightbytes) |
| `MEMORY` class aggregate | `rax` (the hidden pointer) |

3. Pop the frame and jump to the real return address.

From R3, the return stub also writes the return registers of the resolved return type to `/phx/out`, for each (case, `call_index`) that has an `obs_funcio` row. `check` compares them with the row. Compare only a return slot whose `obs_argclass` class is `small_int`, `bool`, `wide_int` or `float`. A difference fails the check. The feedback is the call, its arguments, the expected value and the actual value.

The shadow stack is one global array, because v1 programs have one thread. It holds 65,536 frames. On overflow, the shim writes `phx: shadow stack overflow` to file descriptor 2 and calls `_exit(125)`. The case is then untestable for that set.

### 7.5 Patchability

| Status | Condition |
|---|---|
| `unpatchable` | The function is shorter than 5 bytes. Or the bytes that the patch writes (5, or 14 in the fallback) contain a jump target of the function itself or of another function. Or another function shares the entry. |
| `unsupported_interface` | The signature has `certain: false` (section 5.4.1). |

These functions get whole-program checks only, and N8 when N8 is active.

### 7.6 Case selection

`select_cases(fid, limit)` returns the cases that execute the most CFG edges of the function first. It always includes one case for each caller that the dev set executes.

### 7.7 Validation of the mechanism

**Thunk fixture suite** (`tests/transplant/`). Each fixture is a small C program, built with the pinned GCC and Clang at `-O0`, `-O2` and `-Os`. The replacement is the true source of the function. The suite covers:

- callers that keep values in caller-saved registers across a call (interprocedural register allocation at `-O2`);
- stack arguments (more than 6 integer or 8 floating-point arguments);
- small aggregate returns in two registers, and `MEMORY` class returns;
- recursion 10,000 levels deep;
- tail calls into a replaced function and from it;
- `.isra` and `.constprop` clones, where the replacement implements the actual machine interface of the clone;
- `setjmp` and `longjmp` across a replaced function;
- calls through a function pointer, and a variadic function;
- 100,000 `longjmp` recoveries across a replaced function.

Gate: 100% of the fixtures pass.

**Truth transplant.** For each `corpus_dev` binary with a valid twin:

1. `tools/truth.py` reads the DWARF data of the twin: the address of each source function, its parameters and their locations, and its types.
2. For each reached function with an unchanged interface, compile the true source function as the replacement. `phx_bind.h` comes from the twin.
3. Run `check` with `select_cases`.

A function has a transformed interface if one of these conditions is true. The truth transplant rate excludes it. The transformed-interface truth rate reports it.

- The twin symbol has a `.isra`, `.constprop`, `.part` or `.cold` suffix.
- The DWARF entry has `DW_AT_calling_convention` equal to `DW_CC_nocall`.
- A formal parameter has no location at the function entry in the DWARF location list (a parameter that the compiler removed).

**Negative transplants.** Inject faults into passing true-source replacements, in code that the dev set covers: a wrong constant, an off-by-one comparison, a wrong field offset and a missing store. Each fault must make the check fail. The result is the negative transplant detection rate.

### 7.8 Theseus procedure (`transplant/theseus.py`)

1. Let `S` be the set of all `transplant_pass` functions.
2. Replace all functions of `S` at the same time. Run the full dev set.
3. If each case passes, `passing_set` is `S`. Stop.
4. If a case fails and this computation made fewer than 3 `ddmin` runs, run delta debugging (`ddmin`) on `S` to find a minimal failing set `F`. Record `F`. Set `S` to `S` minus `F`. Go to step 2.
5. If this computation made 3 `ddmin` runs, remove from `S` each function that a failing case executes. Go to step 2. If `S` is empty, `passing_set` is empty.

Numbers:

- `reached_bytes`: instruction bytes of all functions that the dev set executes. It is fixed for each binary and dev-set hash. Compare Theseus fractions only for one dev-set hash.
- `replaced_bytes`: instruction bytes of `passing_set`.
- `fraction` (the Theseus fraction) = `replaced_bytes` / `reached_bytes`.
- `original_code_bytes` = `reached_bytes` minus `replaced_bytes`.
- `original_data_bytes`: bytes of the data objects that the drafts in `passing_set` access through `phx_bind.h`. A Theseus run uses the original data, so it does not check the data emission.

The Theseus fraction is the progress metric of one binary in `transplant` mode.

---

## 8. Data model and data emission

### 8.1 Storage objects and aliases

- A global is an owning storage interval: address, size, alignment, section and mutability.
- A pointer target has a kind: `global` (a data object and an offset in it), `function` (a project function) or `import` (a library function or object). `pointer_slots` holds `{off, kind, target, target_off}` for each pointer slot. `target_off` is 0 for `function` and `import` targets.
- `aliases` holds each address inside the object or one past its end that code or data refers to, as an offset.

Build the objects with these rules:

1. Start an interval at each address that a relocation, an instruction operand or a Ghidra data type refers to.
2. Use Ghidra data types (arrays, structures, strings) and access widths to set extents.
3. Merge an interval into its predecessor when code indexes the predecessor past its end, or when the only references to the interval start are comparisons with pointers into the predecessor (a one-past-the-end pointer).
4. When the evidence is not clear, merge. A merged object keeps aliasing correct. A wrong split can break it.
5. A reference inside an object or one past its end becomes an alias. It never starts a new object.

Jump tables stay inside their functions. Ghidra recovers them as `switch` statements. The data emitter does not emit a jump table.

### 8.2 Special slots and excluded ranges

- Map each `R_X86_64_COPY` slot to its `.dynsym` name. Library objects such as `stdout`, `stderr`, `stdin`, `optarg`, `optind`, `opterr`, `optopt` and `environ` become the real C names from the library headers. The project declares them through the headers and never defines them.
- Exclude the C runtime ranges from emission: `__dso_handle`, `completed.0`, `__TMC_END__`, `__data_start`, `data_start`, `_IO_stdin_used`, `.init_array` and `.fini_array`.

### 8.3 Emission (`generate/data.py`)

`generate/data.py` emits each data object deterministically from `bytes`, the resolved type and `pointer_slots`. The LLM never writes an initializer.

- A typed object gets an initializer of its type.
- A pointer slot of kind `global` becomes `&obj` for offset 0, `&obj[i]` when the target is an array and the offset is a multiple of the element size, and `(char *)&obj + off` otherwise.
- A pointer slot of kind `function` or `import` becomes the declared C symbol of the target, for example `fn_1b00` or `strcmp`. A function-pointer slot has the resolved function-pointer type.
- The emitter never emits an original code address.
- An untyped object in `.rodata` becomes `static const`. An untyped object in `.data` or `.bss` stays writable: never `const`.
- Each untyped object keeps its alignment with `_Alignas(n)`.
- An untyped object without pointer slots becomes `unsigned char name[N]`.
- An untyped object with pointer slots becomes a structure of byte arrays and pointer members, one pointer member for each slot: `void *` for a `global` target, and the resolved function-pointer type for a `function` or `import` target. `_Static_assert(offsetof(...) == ...)` lines check the layout. If a pointer slot offset is not a multiple of 8, the pipeline stops with `pipeline_error` and the reason `unaligned_pointer_slot`.
- The bytes of a fallback object never contain an absolute address of the original. Each pointer slot is symbolic.
- The report lists each untyped object above 256 bytes.

### 8.4 Byte check (from R1)

After `assemble`, build the project for x86-64 with symbols. For each emitted object, read its bytes from the built executable after relocation. Compare them with the original bytes:

- Each byte outside a pointer slot is equal.
- Each pointer slot points to the emitted object and offset that correspond to the original target.

A mismatch gives the repair suspect "data object" (row 4b of the decision table) and counts as a data-caused failure.

---

## 9. Import normalization and arithmetic helpers

### 9.1 Import table (`lift/imports.py`)

One table maps each glibc-internal import to portable C. Each fortified call keeps its check. A report entry never replaces a check. The table stays within its size limit (`docs/ROADMAP.md` section 6.5).

| Raw import | Portable form |
|---|---|
| `__printf_chk(flag, fmt, ...)`, `__fprintf_chk(f, flag, fmt, ...)`, `__vprintf_chk`, `__vfprintf_chk` | `phx_printf_chk(flag, fmt, ...)`, `phx_fprintf_chk(f, flag, fmt, ...)`, `phx_vprintf_chk`, `phx_vfprintf_chk`. Each wrapper keeps the writable-format check: if `flag > 0` and `fmt` contains `%n`, it accepts `fmt` only in a read-only mapping (read from `/proc/self/maps`, as glibc does). Otherwise it writes the glibc message of this check to file descriptor 2 and calls `abort()`. Take the exact message bytes from the pinned glibc version. |
| `__sprintf_chk(s, flag, slen, fmt, ...)`, `__snprintf_chk(s, n, flag, slen, fmt, ...)` | `phx_sprintf_chk(s, slen, fmt, ...)`, `phx_snprintf_chk(s, n, slen, fmt, ...)` |
| `__memcpy_chk(d, s, n, dn)` | `phx_memcpy_chk(d, s, n, dn)`: `if (n > dn) phx_fortify_fail(); return memcpy(d, s, n);` |
| `__memmove_chk`, `__memset_chk`, `__strcpy_chk`, `__stpcpy_chk`, `__strcat_chk`, `__strncpy_chk`, `__strncat_chk`, `__read_chk`, `__fgets_chk` | `phx_<name>_chk` with the same check |
| `__isoc99_sscanf`, `__isoc99_scanf`, `__isoc99_fscanf` | `sscanf`, `scanf`, `fscanf` |
| `__errno_location()` | `errno` |
| `__ctype_b_loc()` table tests | `isalpha`, `isdigit` and the other `<ctype.h>` functions |
| `__ctype_tolower_loc`, `__ctype_toupper_loc` | `tolower`, `toupper` |
| `__assert_fail(expr, file, line, func)` | `phx_assert_fail(expr, file, line, func)`. It prints the glibc message with the strings of the original call and the program name, then calls `abort()`. |
| `__stack_chk_fail` and the `fs:0x28` canary | remove |
| `_IO_getc`, `__uflow`, `__overflow` | `getc`, `putc` |

`phx_fortify_fail()` writes `*** buffer overflow detected ***: terminated` and a newline to file descriptor 2 with `write`, then calls `abort()`. This gives the glibc message and `SIGABRT`.

If a wrapper cannot keep the check of a fortified call, the pipeline records an unsupported behavior for the binary, with the call. The binary is then not fully successful (`SPEC.md` section 2.2, condition 6).

The wrappers are in `src/phx_runtime.c` and `include/phx_runtime.h`. `assemble` writes only the wrappers that the project uses.

The table also holds prompt notes for inlined idioms: `rep movs` and SSE copy loops (`memcpy`), `repnz scasb` (`strlen`), and division by a multiplication constant. The LLM applies the notes. The checks decide. Do not write a separate idiom analysis engine.

The glibc-internal symbol count (`SPEC.md` section 2.3) uses each raw name in this table and each identifier that matches `__*_chk`.

### 9.2 Arithmetic helpers (`include/phx_arith.h`)

C leaves some operations undefined or implementation-defined. x86-64 instructions define them. Each helper gives the x86-64 result on each architecture.

| Operation | Helpers | x86-64 behavior |
|---|---|---|
| Shift by a variable count | `phx_shl32`, `phx_shr32`, `phx_sar32`, and the 64-bit forms | The count is masked: `n & 31` or `n & 63`. |
| Signed division and remainder | `phx_sdiv32`, `phx_srem32`, and the 64-bit forms | If the divisor is 0, or the dividend is the minimum value and the divisor is -1: `raise(SIGFPE)`. |
| Unsigned division and remainder | `phx_udiv32`, `phx_urem32`, and the 64-bit forms | If the divisor is 0: `raise(SIGFPE)`. |
| Truncating conversion from `float` or `double` to a signed integer | `phx_cvtt_f64_i32`, `phx_cvtt_f64_i64`, `phx_cvtt_f32_i32`, `phx_cvtt_f32_i64` | NaN or out of range gives the minimum value of the target type. |

Use a helper when the operand range is not provably safe. A constant shift count below the width, or a constant divisor that is not 0 and not -1, is safe. `verify/lint.py` enforces this rule.

`tests/test_arith_helpers.py` builds `tests/arith/boundary.c` with GCC and Clang for x86-64 and ARM64. On x86-64, it compares each helper with the instruction itself (inline assembly in the test only). On ARM64, it compares the results with the x86-64 results. The inputs include 0, 1, -1, the minimum and maximum values, shift counts 0 to 130, NaN, the infinities and the values near 2^31 and 2^63.

---

## 10. Portability rules

Each draft prompt contains these rules. `verify/lint.py` checks the rules marked "lint".

| # | Rule | Check |
|---|---|---|
| 1 | Where the width or sign of a byte matters (arithmetic, comparison, index, shift), use `signed char` or `unsigned char` as the assembly shows (`movsx` or `movzx`). Plain `char` is only for text. The canonical build also sets `-fsigned-char` as a safety net. | lint |
| 2 | Use `<stdint.h>` types for each value where the width matters. | prompt |
| 3 | Do not use `long double`. | lint |
| 4 | Use the arithmetic helpers of section 9.2 for each operation with an undefined or implementation-defined result. | lint |
| 5 | Convert a pointer to an integer only through `intptr_t` or `uintptr_t`. | lint |
| 6 | If the assembly reads a value before a write, first treat it as a missing parameter (section 5.4.1). If no caller sets it, initialize it to 0, add `/* PHOENIX-UNINIT */` and record a known divergence. Never use a value from the dev set. | lint |
| 7 | Do not print a pointer value. | lint |
| 8 | Do not depend on padding bytes or on the evaluation order of function arguments. | prompt |
| 9 | Keep the floating-point operations in the order of the assembly. If a result needs x87 precision, record a known divergence. Do not add output normalization. | prompt |

Each ARM64-only failure on `corpus_dev` gets a root cause. If the cause is a new rule, add it to this table and, where possible, to the lint.

---

## 11. LLM layer

- Keep `llm/provider.py`, `llm/responses.py` and `llm/codex.py`.
- Rewrite `llm/ledger.py` within its size limit (`docs/ROADMAP.md` section 6.5). It holds the cost log (`llm.jsonl`) and the response cache with the request hash as the key.
- Interface: `LLM.call(task: str, prompt: str, schema: dict, role: str, effort: str) -> dict`.
  - `task` is one of `draft`, `region`, `repair`, `generator`, `struct`, `rename`, `polish`.
  - `role` is `runtime` or `strongest`.
- `phoenix/config.py` holds the model identifier of each role (`ROLE_MODELS`, with the keys `runtime` and `strongest`), the price table and the context window of each model, the prompt fraction and the service tier. No other pipeline file holds a model name. AGENTS.md section 6.1 gives the values of `ROLE_MODELS`.
- Each call uses the standard service tier.
- Effort for each task:

| Task | Effort |
|---|---|
| `draft`, `region`, `repair` | the attempt table of section 5.5 |
| `generator`, `struct`, `polish` | `medium` |
| `rename` | `low` |

- The cost cap of each binary comes from the run settings. `draft` and `repair` stop under the rule of section 5.8.
- `phoenix run --replay` uses only the cache. A cache miss is an error.
- On a rate-limit or usage-limit error, retry with exponential backoff, at most 5 attempts. `phoenix/config.py` holds the attempt count and the base delay (`llm_retry_attempts`, `llm_retry_base_delay`). They are technical retry parameters, not schedule limits. If each attempt fails, keep the checkpoint, record `pipeline_error` for the binary, and continue with independent work. `phoenix run --resume` continues the binary later. When such errors stop 3 runs in sequence, apply the reduction sequence of `docs/ROADMAP.md` section 8.2.
- If the provider refuses a prompt, add the purpose statement (recovery of the owner's own test programs) and retry one time. Then mark the function `draft_failed` with the reason `refused` and continue.
- Each call record holds the task, the role, the model identifier, the effort, the request hash, the tokens, the cost and the cache result. `run.json` lists each model used (`SPEC.md` section 10.7).
- `generate/prompts/` holds one prompt template and one JSON schema for each task.

---

## 12. Evaluator changes

The evaluator is sound. Change only the items in this table. Each change needs the review of AGENTS.md section 8 Review. An unreviewed change never merges.

| Change | Files | Milestone |
|---|---|---|
| Window rule (`SPEC.md` section 9, rule 1a and 1b): check source literals and initializers, and the non-executable data sections of the built executables without the C runtime ranges. Do not check the built code sections. Add an honest fixture where machine code from the same compiler equals the original. | `phoenix_eval/integrity.py`, `tests/test_integrity.py` | R0 |
| Protected path list and role profiles (section 6.3). | `phoenix_eval/protection.py` | R0 |
| `phoenix_eval/run.py` replaces `m1.py` and `m2.py`. It evaluates `corpus_dev` and writes `scoreboard.json`. After the selection is fixed, it records each selected binary and writes a scoreboard even if the execution stops. It restores archived runs for `--replay`. `phoenix-eval probe` runs the real-directory protection checks. | `phoenix_eval/run.py`, `phoenix_eval/__main__.py` | R0 |
| The sealed corpus mode of `phoenix_eval/run.py`: it writes sealed runs only to `sealed_runs/` and exports only the aggregate scoreboard of a sealed run. `scripts/loop sealed-pre` and `scripts/loop sealed-import`. Before Sealed-A run 1. | `phoenix_eval/run.py`, `scripts/loop` | R2 |
| Remove the function-name roster rule, the control-flow count limit, the ban on indirect calls, the single translation unit rule and the rule that rejects each literal that is absent from the original data. | `phoenix_eval/integrity.py`, `containers/c-integrity.cc` | R1 (first) |
| Accept `src/*.c` and `include/*.h` with the canonical CMake template (`canonical_cmake(files)`). | `phoenix_eval/submission.py`, `phoenix_eval/build.py` | R1 (first) |
| Typed storage evidence for structures, unions, pointer initializers (target and offset) and function pointer tables. The constant-table rule compares only non-pointer bytes. | `containers/c-integrity.cc`, `phoenix_eval/integrity.py` | R1 (first) |
| Approved call list: add `raise`, `getopt_long`, the C11 `<math.h>` functions, and each other C11 or POSIX.1-2008 function that a `corpus_dev` program uses. Keep `abort`. Never add the functions that `SPEC.md` section 9, rule 5 names. | `phoenix_eval/integrity.py` | R1 (first) |
| Emulator-shape check (rule 1c) and the executable-memory rule (rule 1d). | `containers/c-integrity.cc`, `phoenix_eval/integrity.py` | R1 (first) |
| Oracle pinning: one QEMU `-cpu` model and one `GLIBC_TUNABLES` mask from `tools.lock`. | `phoenix_eval/worker.py`, `containers/prepare-runtime.sh`, `tools.lock` | R1 |
| Platform capabilities (section 13). Linux protection with `bwrap`. | `phoenix_eval/platforms.py`, `phoenix_eval/protection.py` | R1 |
| Edge coverage (`SPEC.md` section 2.4): plugin, wire format, collector and reader change together. | `containers/code-coverage.c`, `phoenix_eval/coverage.py`, `phoenix_eval/wire.py` | R1 |
| Maintainability metrics from the submitted source: register-named locals and `goto` density (R0); non-default type share, literal-mode byte share from `origin_map.json` and glibc-internal symbols (R1). | `phoenix_eval/quality.py` | R0, R1 |
| Edit-task harness (`SPEC.md` section 10.8). | `phoenix_eval/edit_tasks.py` | R5 |

Fixtures for the first R1 items: end-to-end projects with multiple source files, helpers, structures, pointer initializers and indirect calls pass. The cheat suite fails. The honest suite passes.

---

## 13. Platform capabilities

`phoenix_eval/platforms.py` holds the only logic that selects runners. `phoenix/config.py` calls it.

```python
def capabilities() -> Capabilities
# Capabilities: host: Literal["apple_silicon", "linux_x86_64", "linux_arm64"],
#               x86_runners: tuple[str, ...], arm64_runner: str,
#               oracle: Literal["dual", "single_runner"]
```

| Host | x86-64 runners | ARM64 runner | Oracle |
|---|---|---|---|
| Apple Silicon (macOS with Colima) | Rosetta (`linux/amd64` containers), QEMU user mode | native | `dual` |
| Linux x86-64 | native, QEMU user mode | QEMU user mode | `dual` |
| Linux ARM64 | QEMU user mode | native | `single_runner` |

- Oracle agreement uses two independent x86-64 runners where the host has them. On a single-runner host, the dev set and `run.json` record `single_runner`.
- Portability checks (the ARM64 configurations) are separate from oracle agreement.
- Remove the macOS-only gates in `phoenix/llm/codex.py` and in `phoenix_eval/protection.py`.
- CI (GitHub Actions, `ubuntu-latest` and `ubuntu-24.04-arm`): build the fixed reconstructions in `tests/replay/<program>/` with GCC and Clang natively, run the `corpus_dev` held-out cases, and compare the outcomes with the original binaries. The x86-64 job builds and runs the originals. The ARM64 job compares with the x86-64 outcome artifact. CI never reads sealed data.

---

## 14. Concurrency, resources and caching

### 14.1 Global concurrency budget

One budget limits all parallel work of all binaries on the host.

| Slot class | Variable | Default |
|---|---|---|
| CPU slots | `PHOENIX_JOBS` | physical cores / 2, at least 1 |
| Compile slots | derived | `max(1, PHOENIX_JOBS // 2)` |
| Execution slots | derived | `max(1, PHOENIX_JOBS - compile slots)` |
| LLM slots | `PHOENIX_LLM_SLOTS` | 8 |

- `phoenix/jobs.py` implements the slots as lock files in `$PHOENIX_ROOT/slots/<class>/<n>.lock` (`fcntl` locks). Thus all processes share one budget.
- Each compiler call and each Ghidra lift takes one compile slot. Each container execution batch takes one execution slot. Each LLM call takes one LLM slot.
- `scripts/loop` and `phoenix-eval` start any number of binaries. The slots limit the work.

### 14.2 Resource measurement

- `scripts/loop` records the peak memory and the peak storage of each loop in the scoreboard.
- The storage design limit is the actual size of the workspace image. `docs/ROADMAP.md` gives the storage rules.

### 14.3 Caching

| Cache | Key | Location |
|---|---|---|
| Lift | binary SHA-256, lift stage version | `$PHOENIX_ROOT/cache/phoenix/lift/<sha256>/<version>/lift.json` |
| Dev set | binary SHA-256, devset stage version, seed | `$PHOENIX_ROOT/cache/phoenix/devset/<sha256>/<version>/` |
| LLM responses | request hash: model, effort, prompt, schema | `$PHOENIX_ROOT/cache/phoenix/llm/` |

- The quick loop must not run Ghidra or rebuild the dev set when neither the binary nor the stage version changed.
- A cache entry never holds evidence from another binary.
- A cold run uses an empty cache root (`--cache-root` to an empty directory). Sealed runs are cold runs.

---

## 15. Techniques

### 15.1 Card format

Each card gives:

- **H**: the hypothesis;
- **E**: the experiment;
- **M**: the metric;
- **K**: the kill criterion;
- **F**: the complete fallback path after a kill.

All experiments run on `corpus_dev`. "Baseline" is the scoreboard row before the change, on the same binaries (`docs/ROADMAP.md` gives the comparison rule). An experiment count in a kill criterion counts experiments on that technique only. An acceptance attempt of an enabling item is not a full-loop row. The two-flat-rows rule of AGENTS.md section 9 Anti-stall rules does not count it.

### 15.2 Accepted techniques

**N1. Function transplant with a register-preserving thunk.**
- H: An in-process check of one function against the original gives an exact oracle for each function at each optimization level.
- Prior art: [PCodeTrans](https://arxiv.org/html/2603.14855v1) and [DecompileBench](https://aclanthology.org/2025.findings-acl.1194/) already check functions inside the original program. Phoenix adds the register-preserving thunk, register and shadow-stack handling, negative transplants, and the use of the check to build a standalone project (section 7).
- E: The thunk fixture suite. Then the truth transplant on `corpus_dev` at `-O0`, `-O2` and `-Os`. Then the draft loop in `transplant` mode against `compile_only` mode on D1 `-O2`.
- M: Truth transplant rate. Binary success rate on D1 `-O2`. Repair rounds for each binary.
- K: A success gain below 10 points on D1 `-O2` against `compile_only` mode after 3 experiments. Or a truth transplant rate below 50% at `-O2` after 3 acceptance attempts of the mechanism enabling item (instrumentation mode and thunk, `docs/ROADMAP.md` R2) and 3 of the pivot item.
- Pivot before the kill: if the truth transplant rate is below 50% at `-O0` or at `-O2` after the 3 acceptance attempts of the mechanism item, start the ELF-copy pivot as a separate enabling item: patch a copy of the ELF file before the run (a static jump at each entry and a slot table that the shim fills). Limit: 3 acceptance attempts.
- Restrict before the kill: if the truth transplant rate at `-O2` is 50% or more and below 80% after the 3 acceptance attempts, give each function of a failing class the status `unsupported_interface`, write the classes in `docs/LOG.md`, and continue with N1 for the other functions.
- F: `compile_only` stays the mode. Repair uses the decision table rows 1, 4, 5 and 6, and N7. The Theseus fraction is not reported. Function reachability and `integrated_pass` counts replace it. Delete the shim and the thunk unless N8 is active. Keep instrumentation mode while N5, N7, N8 or N9 is active.

**N2. Theseus bisection and the Theseus fraction.**
- H: The replacement of sets of functions separates interaction faults and data faults from single-function faults. It gives a progress metric for each binary.
- E: Inject 30 known faults (wrong field offset, wrong signature, wrong initializer, wrong constant) into passing dev reconstructions. Run the decision table. Run the negative transplants of section 7.7.
- M: First-suspect accuracy. Negative transplant detection rate.
- K: First-suspect accuracy below 70% after 3 experiments. N2 also stops when N1 is killed.
- F: Keep the Theseus fraction with step 5 of section 7.8 only (no `ddmin`). Localization uses decision table rows 4 to 6 and N7.

**N4. Self-generated dev set.**
- H: CLI surface recovery, a coverage loop and LLM generators aimed at uncovered branches reach the behavior that the hidden tests reach.
- E: Dev sets with steps 1 to 3 (R1). Then dev sets with step 4 (R3).
- M: `dev_edge_coverage`. Function reachability. Escape rate.
- K for step 4: a gain below 5 points of `dev_edge_coverage` on D1 after 3 experiments.
- Pivot for the technique: an escape rate above 15% on D1 at the end of R3 starts AFL++ in QEMU mode as a second generator (limit: 3 experiments, image below 1.5 GiB) and starts N8.
- F: Steps 1 to 3 stay. Delete step 4.

**N13. Mutant-adequate dev set.**
- H: A surviving mutant of the reconstruction marks behavior that the dev set does not check. An input that separates the mutant from the reconstruction is a case of the kind that the hidden set holds. The original decides which behavior is correct.
- E: After the project matches the full dev set, `devset/mutants.py` applies the fixed operator set of `SPEC.md` section 10.6 to the functions that the dev set executes (at most 300 mutants for each binary, recorded seed). Build the reconstruction and each mutant natively for ARM64. Run the dev set on each mutant. For each surviving mutant, search for a separating input: run `mutate.py` on the native builds (at most 20,000 native runs for each mutant), then one LLM generator call with the mutant diff. Run each separating input on the original (step 5 of section 5.3). If the reconstruction matches, add the case to the dev set. If it does not match, the case is a counterexample for `repair` (decision table row 4).
- The native runs stay inside the Linux containers (AGENTS.md section 4 Hard rules). The technique uses only the binary and the project of the same run (principle 5).
- M: Escape rate on D1 and D2. Counterexamples found for each binary. Mutation score of the dev set against the reconstruction.
- K: A decrease of the escape rate below 5 points on D1 after 3 experiments.
- F: Delete `devset/mutants.py`. Dev-set steps 1 to 4 stay.

**N5. Function input and output examples from the original.**
- H: Argument and return values from the original improve signature recovery and the first-attempt success of drafts.
- E: Draft D1 `-O2` with and without `obs_funcio` rows in the context. Compare the signatures with `tools/truth.py`.
- M: Signature accuracy. The share of functions that pass their check at attempt 1.
- K: A gain below 5 points on both metrics after 3 experiments. Or the pinned QEMU lacks one of the two plugin functions (section 5.3).
- F: Signatures from static analysis only. Remove the `funcio` argument recording if N7 is also killed. Keep the tracer image while N7, N8 or N9 is active.

**N6. Faithful first, readable second.**
- H: Literal mode fixes functions that idiomatic mode cannot fix. Checked polish recovers the readability later.
- E: Count the functions that fail idiomatic attempts 1 and 2 and pass in literal mode. Count the literal-mode functions that `polish` converts.
- M: `draft_failed` share. Literal-mode byte share.
- K: Literal mode fixes less than 30% of the functions that reach it, after 3 experiments.
- F: Attempts 3 and 4 use idiomatic mode with the strongest available model at `xhigh` effort.

**N7. Trace-guided fault localization.**
- H: The alignment of libc event sequences and call sequences finds the faulty function when transplant cannot (failures of the whole project, ARM64-only failures).
- Prior art: [PCodeTrans](https://arxiv.org/html/2603.14855v1) uses breakpoint trace differences. [DecompileBench](https://aclanthology.org/2025.findings-acl.1194/) compares runtime profiles after function replacement. Phoenix adds the thunk, register and shadow-stack handling, negative transplants, and checks that support standalone project construction (section 7).
- E: The injected faults of N2, restricted to decision table rows 4 and 5.
- M: First-suspect accuracy on these rows.
- K: Below 50% after 3 experiments.
- F: Give the LLM the full failing path (the functions that the failing case executes, in call order) as the suspect list.

**N8. In-situ unit check for unreached functions.** (Conditional.)
- Start condition: at the end of R3, `static_only` functions cause more than 25% of the held-out failures on `corpus_dev`.
- H: For a function that no dev case executes, calls with generated arguments inside the initialized original process find draft errors.
- E: In instrumentation mode, the launcher starts one process for each call. The shim stops at `main`, calls the original function (or the draft, in the second process) with arguments generated from the resolved types, writes the return value and a hash of the writable segments, and exits. Compare the two processes.
- M: The share of injected faults that the check finds in `static_only` functions.
- K: Below 40% after 3 experiments.
- F: `static_only` functions keep one literal draft and the `PHOENIX-UNVERIFIED` comment.

**N9. Heap shape tracing and whole-program struct unification.**
- H: Allocation sizes, field accesses and pointer fields from the trace give struct layouts that one function cannot give.
- E: Compare the recovered layouts with the true source structs (`tools/truth.py`) on D1 and D2.
- M: Struct field accuracy. Non-default type share. Binary success rate on D2.
- K: Field accuracy below 60% after 3 experiments.
- F: Keep the Ghidra types and local casts. Readability decreases. Correctness does not depend on this technique.

**N11. Sanitizer-assisted portability repair.**
- H: Sanitizer reports on the ARM64 build find the cause of ARM64-only failures in fewer repair rounds than output differences alone.
- E: Repair ARM64-only failures with and without sanitizer reports.
- M: Repair rounds for each ARM64-only failure.
- K: No reduction after 3 experiments, or one repair that a sanitizer report caused and that breaks a passing case.
- F: Decision table row 5 without sanitizer input.

### 15.3 Requirements

These items have no kill criterion. They are requirements.

**N3. Deterministic data emission.**
- Requirement: data objects come only from section bytes, relocations and resolved types (section 8). The LLM never writes an initializer.
- Check: the byte check of section 8.4 passes for each emitted object of each `corpus_dev` binary.
- Metric: count of binaries with a data-caused failure. Integrity failures caused by data.
- Fallback for one object: the untyped emission of section 8.3. It is always available.

**N10. Import normalization table and arithmetic helpers.**
- Requirement: section 9.
- Check: zero glibc-internal symbols in each `corpus_dev` project. The boundary tests pass on both architectures. The table stays within its size limit.
- Metric: glibc-internal symbols.

**N12. Edit-task harness.**
- Requirement: `phoenix_eval/edit_tasks.py` runs the procedure of `SPEC.md` section 10.8.
- Check: a test proves that one session cannot read the workspace of another session or a task test.
- Metric: edit-task parity and the pass rate of each arm.

### 15.4 Rejected for v1

- **X1. Mechanical assembly-to-C translation as a fallback.** A register-machine translation is an emulator of the original in source form. It breaks integrity rule 1 and is not maintainable.
- **X2. A second decompiler.** The assembly is already the ground truth in each prompt. A second lifter adds storage, build time and a second schema. Reconsider after v1 if `draft_failed` functions cause more than 20% of the failures.
- **X3. Symbolic proof for each function that it behaves as the original function.** The cost is high for optimized code with loops and memory. Transplant and tests give the evidence for v1. This is a ladder item.
- **X4. Evidence shared between binaries of one program.** This breaks the input contract (one binary).
- **X5. AFL++ in QEMU mode as the main generator.** It needs a large image and a second coverage format. It is the pivot of N4.
- **X6. The M2 evidence system** (observation collectors, byte graphs, switch-evidence exports, layout readers). It produced no score. N3, N5 and N9 replace it with smaller parts.

### 15.5 Rank

Rank by expected effect on the headline numbers: N1, N4, N13, N2, N6, N5, N9, N7, N11, N8. N3, N10 and N12 are requirements and have no rank.
