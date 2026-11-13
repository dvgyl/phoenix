The goal is to support Phoenix through every SPEC section 9 condition. This task resolves only the source schema 2 validation boundary before Unit B implementation. Root retains all product changes, integration, Git writes, and later project work.

**Decision. PASS-to-implement for Unit B under `api.md` and `test-plan.md`.** Use graph bytes with explicit lift, pass, raw C, source limits, and graph limits. Revalidate those inputs at every public boundary. Use separate schema 2 token types and a minimal supplied-view checker. This decision does not approve a source implementation because none exists in the frozen checkout. Producer admission, semantic use, emission, and production remain HOLD.

The exact frozen revision is `d43f604bfdb6ef63b2b9086352c440be3559b1d5`. The checkout is `/Volumes/PhoenixWork/worktrees/m1-preflight-review-2`. Its initial HEAD matched the supplied `source-head.json`, and initial Git status was clean. Final identity and artifact hashes are in `final-check.json`.

**Concrete findings and resolutions.**

| Finding | Evidence | Resolution |
| --- | --- | --- |
| F1. The proposed projection cannot perform its promised graph validation. | The original `api.md` gives projection only source, graph, and raw C. `byte_graph_v2.py:913` requires `LiftIndex`, `PassRecord`, and graph limits. The source parser proposal also lacks the lift. | Require all validation inputs on parsing, projection, and supplied-view checking. Call the unchanged graph parser on every call. |
| F2. A typed graph serializer is not an exact typed-object validator. | `_wire` uses `hex` for a `Location` at `byte_graph_v2.py:263`. The independent control replaces ordinary-entry offset 1 with `True`. Both objects serialize to identical bytes, and those bytes parse. | Accept graph bytes only. Reject a graph object at the new public boundary. Do not add a typed convenience overload. For typed source and candidate inputs, check exact nested types before conversion or comparison. |
| F3. The old positive token type uses schema 1 keys. | `byte_source.py:9` imports graph schema 1 keys. `SourceToken` at `:62` uses those keys. Graph v2 defines distinct key classes. | Define `SourceTokenV2` with the same wire fields and exact graph v2 key types. Define a new source gap type with nullable item ordinal. Keep old modules exact. |
| F4. A computation-only API cannot reject a supplied mutated view. | Original design section 7 promises candidate rejection, but its projection signature accepts no candidate. | Keep computation pure. Add `check_positive_span_view(candidate, *, source, graph_bytes, lift, raw_c_bytes, pass_record, limits, graph_limits) -> None`. Recompute and compare every field. |
| F5. Digest claims are not authenticated producer pins. | `_pass` at `byte_graph_v2.py:440` checks the shapes of source/tool digest claims. The graph parser binds the pass hash. It never receives a reviewed manifest. Coherently changed claims pass the independent control. | Preserve the distinction between fixed profile constants, supplied digest claims, manifest consistency, installation verification, and producer admission. Add no authentication claim to Unit B. |

F2 is a defect in the proposed serialize-then-parse strategy, not a defect in a graph parser that accepts bytes by contract. A byte parser cannot recover a malformed Python value that the caller already converted into valid JSON. The selected API makes that limit explicit. A directly supplied malformed source or view remains observable and must refuse before coercion.

**Alternatives and trade-offs.**

| Approach | Exact input concept | Benefit | Cost and decision |
| --- | --- | --- | --- |
| Existing validation inputs with a typed graph | `source, graph: ByteGraphV2, lift: LiftIndex, pass_record: PassRecord, raw_c_bytes: bytes, limits: ByteSourceV2Limits, graph_limits: ByteGraphV2Limits` | Closest to the proposed signatures. All dependencies are visible. | Requires a complete bounded graph type walk before graph serialization, or a new public graph-object validator. Serialization alone loses Boolean address types. This duplicates graph shape knowledge or expands Unit A. Valid alternative, not selected. |
| Bounded immutable binding value | A frozen `SourceBinding` containing graph bytes, a detached bounded immutable lift snapshot, pass, raw C, and both limit objects. Every public use revalidates all fields. | Shorter signatures and fewer accidental caller mismatches. | A constructor is still unchecked. `LiftIndex.functions` can be a mutable map in a directly constructed object. A true snapshot needs explicit deep shape handling. A bytes-only variant must retain bounded lift and binary bytes and reparse them. Either adds ownership and lifetime rules for one consumer. Valid alternative, not selected. |
| Graph bytes with explicit inputs | The exact three signatures in `api.md`. `graph_bytes` is exact immutable bytes. | Reuses the existing public graph parser. Avoids a second graph-object validation algorithm and a certificate-like wrapper. Caller reductions remain visible. | More keyword arguments. Every call reparses the graph. Typed source and candidate checks still need exact validation. Selected as the smallest clear interface. |

No performance result was measured. Revalidation costs are bounded by the existing graph limits and the new source limits. Canonical graph bytes can be retained by the caller as data. Retaining them must not skip parsing on a later call. The implementation may share private source validation logic within one call. It may not introduce a global cache, success bit, private unchecked capability passed across public calls, or a general producer framework.

A future binding abstraction is justified only if real call sites show repeated mistakes or measured cost. This task does not authorize that abstraction. The installed Minimize Reader Load principle changed this choice. The selected design removes the need to trace a wrapper's validity and lifetime.

**Required preserved behavior.**

`api.md` defines every source type, all nine exact source limits, inherited graph limits, finite errors, validation order, and the dependency boundary. It defines every class and association rule from the final design. It also states the inherited-null getter restrictions from the pinned primary classes.

The source inventory keeps every line, item, empty item, direct link, original/rendered pair, and source gap. A sequential cursor checks indentation, ordered items, and the exact separator on every line. Empty markup remains distinct from an empty line. Zero-width items retain multiplicity and scalar boundaries. Source-only values remain legal because graph v2 retains the full value bank. Equal storage never supplies identity. Ordered repeated storage remains exact.

The projector recomputes the complete row inventory and every positive token field. It binds the full source hash, including empty-item associations and gaps. The checker rejects a changed candidate against the supplied complete source. A coherent different source is new supplied content. Neither a partition nor a digest proves that Java actually emitted every item. Actual inventory completeness and same-call links still require capture review.

The pure reader retains an `illegal_char_cpp` original/rendered pair as a supplied observation. It does not reproduce Java Unicode rules in Python. The class/syntax selection is checkable. The transformation result still needs independent pinned Java controls. No C grammar, symbol meaning, callable interface, pointer range, machine effect, or native state is established.

The source boundary checks the actual supplied raw C bytes against strict UTF-8 of the same selected ordinary lift function. It also checks graph and source digests. The graph hash uses accepted canonical graph bytes. The pass hash remains a content identity. Source/tool manifest digest claims can change consistently without authenticating any source file or installation. Unit D later checks supplied manifest binding. Independent producer admission must still verify actual source, tools, installation, capture, and process controls.

**Independent design controls completed.**

`boundary_probe.py` is a small synthetic Python control in the matching temporary root. It imports only exact frozen project modules and standard-library code. It does not import product test fixtures or run pytest. `boundary-probe.json` records its observations and import hashes.

The control constructs a literal graph with one empty entry block, no operations, all five mandatory graph gaps, and ordinary source `b"\n"`. The graph parses. A separately constructed typed graph with Boolean ordinary-entry offset serializes to the same valid bytes. This confirms that serialization and reparsing alone cannot reject that original typed defect.

The control also confirms finite refusals for a graph object used as bytes, changed ordinary raw C, an unbound changed source-manifest claim, a changed fixed revision pin, a reduced graph byte limit, and a Boolean direct pass entry. Coherently rebound source/tool digest claims parse. These observations directly support the interface and authority decisions. They are host design controls, not Phoenix evaluation results.

No source-reader or candidate-checker test has run. `test-plan.md` gives independent literal fixtures, exact mutation matrices, direct typed-object controls, bound tests, property tests, schema 1 regressions, and later implementation gates. It distinguishes a malformed omission from a coherent fabricated inventory. A test plan that requires all coherent fabrications to refuse would assign authority that the data does not provide.

**Read scope and evidence.**

The complete `AGENTS.md` and `SPEC.md` were read. The installed Poteto 0.9.138 skill and its Investigation, How, Codex mapping, Minimize Reader Load, Unslop, technical-writing, No Comments, and Comment Sicko guidance were read. The explicit task limits replace nested dispatch and source changes in those workflows. Throughput checkpoint is not applicable to this read-only investigation. The decision checklist is `todo.md`.

All four final design documents under `docs/checkpoints/2026-11-13-pause/byte-adapter-design` were read completely. Split reads covered large truncated displays. The full 1,023-line graph v2 implementation, full 1,978-line graph v2 test file, full 480-line old source reader, full 465-line old source tests, full index, and full mapping were read. The old graph key contracts and evidence storage contracts were read. ADR0042 and the complete current graph repair and main integration review records were read. The relevant accepted-source record was read. Historical partial review displays were not used as current approval.

The current graph module hash matches the graph main integration review's exact approved bytes. The current review records retain a historical test-file hash assertion failure. This task did not rerun that assertion, reinterpret it as behavior, or replace the prior functional review. No full implementation or integration approval is claimed here.

The supplied root brief at `/Volumes/PhoenixWork/audit/resume-20261113-evening/source-v2-validation-boundary.md` was read. The task's `source-head.json` was checked against actual HEAD and clean status.

Only needed public saved primary files were read under `/Volumes/PhoenixWork/tmp/m2-byte-adapter-design-astra-20261112/primary`. They are `PrettyPrinter.java`, `ClangToken.java`, and all ten allowed token class files. They settle the five render classes, the syntax-5 exemption, base null getters, field output, bit-field behavior, and case predecessor-search exclusion. `input-identities.json` checks these exact bytes against the named saved primary-source manifest at revision `8ca9077040cc43cd790babcfccf19475622a3e9a`. No primary source was fetched or executed.

**Separate comment findings.**

No product source or comment was edited. No product comment deletion, restoration, suppression change, or encoding change is proposed by this task. The graph's current public-contract docstrings correctly limit authority. Unit B comments must not call a frozen object validated merely because it is frozen. Keep the public signatures and authority limits in API docstrings. Put class choices and bounds into types and tests.

One design-prose correction is required. Original `api.md` section 3 says that the pure reader checks supplied data against reviewed expected pins. That wording is too broad for source/tool digests. The actual parser checks fixed profile constants and supplied digest claims. This report and the replacement API state that exact limit. This is a documentation finding, separate from product comment review. The new interface and its regression controls are the concrete design correction. No repository document was changed by this delegate.

**Process and privacy limits.**

The first `pwd` command did not source `task-env.sh` or check stop markers. The next bootstrap command tried the wrong task-env path and continued with read-only instruction reads after that source failed. A later bootstrap sourced the general environment, and another inspected only selected environment names and directory names to identify the assigned task root. Those bootstrap shells did not meet the every-shell task-env rule. This is a process deviation. No file content from excluded dispatch or private data was returned by those probes.

Every later shell sourced `/Volumes/PhoenixWork/audit/m2-source-v2-boundary-design-astra-evening-20261113/task-env.sh` and checked the exact `audit/continue-v1/PAUSED` and `DRAINING` markers before its batch. The environment repeatedly reported a denied mkdir for `/Volumes/PhoenixWork/vm`. That warning was not investigated. No guard was read, probed, altered, relaxed, or nested. This task does not claim an exception-free process.

All intentional writes are limited to this audit directory and its matching temporary root. No source or Git write occurred. The bounded Python control uses `-B`, disabled bytecode, an exact import root, no user site, and a minimal child environment. No dependency was installed. No unnecessary full test or check was run. No process or audit-tree scan occurred. A single directory listing identified the task-related brief location. It was not a recursive audit walk.

No target, compiler, linker, Java, Ghidra, native plugin, VM, network, provider, model CLI, nested agent, session dispatch, or continuation ran. No sealed source, held-out input, private archive, private run or outcome, Author material, Codex session, archived session, dispatcher event file, dispatcher stderr, dispatcher summary, or excluded layout-writer log was read. No runtime admission or publication action occurred. No provider screening was retried, rephrased, replaced, or bypassed.

Standard service was requested. No service setting was changed and Fast was not enabled. No routing attestation is available. The report does not attest the provider's model identity or service tier. All owned foreground commands completed. No background child was created. Exit 0 is not the design verdict.

**Remaining gates.**

Root must implement Unit B in its authorized writer checkout, run the independent controls, obtain exact-revision review, and integrate only accepted bytes. Keep graph v2 and all old modules exact for this unit. Then proceed through the separately authorized pure conversion and same-call collector dependencies.

Full capture remains **OPEN after provider screening**. This design does not close or replace it. Process launcher design, capture, selector integration, manifest and installation verification, producer admission, native facts, entry relation, raw/analyzed and memory effects, exact source grammar, callable interface, pointer proof, deterministic active emission, compiled public positives, Linux controls, replay, and production publication remain open.

All SPEC section 9 requirements remain. Phoenix must complete M4, publish T0 through T3 results against every baseline with costs and failure taxonomy, publish the required harness and benchmark artifacts, and reproduce every headline with `phoenix-eval --replay`. This design supplies no corpus score, milestone acceptance, or completion claim.

The deliverables are `report.md`, `api.md`, `test-plan.md`, and `final-check.json`. The supporting artifacts are explicitly listed in the final record. That list excludes all dispatch data. `final-check.json` records `report={path,bytes,sha256}`, the final revision and clean status, stop-marker state, source identities, process deviations, and remaining gates.
