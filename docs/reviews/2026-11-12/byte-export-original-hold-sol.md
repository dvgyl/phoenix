Phoenix must meet every requirement in SPEC section 9. This review checks the exact unpublished ordinary-byte diagnostic unit at `d1a17795c0a172dbfeebd91057f4ee9808421415` on `agent/m2-byte-export-producer`.

The diagnostic-unit verdict is **HOLD**. One P2 finding remains in the finite I/O error contract. Five fresh controls reproduce it. The intended entry, printer, and Java dead-flag gaps are correct diagnostic results.

The separate complete-producer verdict is **HOLD**. This review gives no producer admission, compiled byte-loop positive, native liveness proof, source grammar approval, emission approval, or publication version 4 approval. The full capture review remains OPEN after provider screening.

F1 is a P2 error-contract defect in [byte_export.py](/Volumes/PhoenixWork/worktrees/m1-follow-up-review-e07ec17/phoenix/lift/byte_export.py:689). Staging resolution, staging creation, staged writes, and log creation do not convert expected filesystem errors to `ByteExportError`. Other affected locations are lines 697, 707, and 633. A missing staging directory raises `FileNotFoundError`. A file used as the staging directory raises `NotADirectoryError`. Denied staging creation raises `PermissionError`. An input-copy write that reports `ENOSPC` raises raw `OSError`. An existing owned log raises `FileExistsError` before process creation. These errors bypass the documented finite diagnostic categories. A caller that handles `ByteExportError` cannot handle these routine failures through that contract. No partial diagnostic result escaped in these controls.

The reproducer is [test_io_contract.py](test_io_contract.py). Its [command](io-contract-command.json), [log](io-contract.log), and [exit](io-contract.exit) preserve all five failures. The first two staging failures use real filesystem states. The denied creation and full-disk write use local fault injection. The log control uses a real existing file. No headless process starts in these five controls. Add local `OSError` conversions at these I/O boundaries. Use the `io` category for staging and log failures. Keep the existing process-start category and unexpected programming exceptions. Retain the cleanup path. Run these five controls again after a correction. I made no source correction.

The exact source root is `/Volumes/PhoenixWork/worktrees/m1-follow-up-review-e07ec17`. The parent revision is `9a3899dfe4a0e0ff774223c04002cf71d91d9102`. The branch and HEAD remained fixed. The worktree is clean. [source-before.json](source-before.json) records all 229 tracked file hashes. [unchanged-source.json](unchanged-source.json) records the final comparison. Every tracked file matches the first snapshot. All 222 files outside this commit's seven changed paths also match the parent revision. No source edit, commit, push, tag, or branch change occurred.

| Source file | SHA-256 |
| --- | --- |
| `ghidra_scripts/ExportLift.java` | `97a658868ca8b34ebf694ccc35ff0301a19f8893e25562039aab40dc521e0e38` |
| `ghidra_scripts/OrdinaryByteEvidence.java` | `d379fa3a37b985d3146bbe07188c5a1eb32edb2cec32e3c6b26987d129cfa378` |
| `phoenix/lift/byte_export.py` | `d275b6c40820ac96bc185a8752eb977a7646a01af598bcc05b12ecb64cd8606f` |
| `tests/test_byte_export.py` | `1ebe0db73eb10be2e6f57c0b7885a1b6388a8264f980031e44657f0c2a0853c3` |
| `docs/adr/0040-ordinary-byte-evidence-export.md` | `9b9b264b30ed81f8c8bb8a5365fd744d0e1f9cf4902f6a4d1aec88ef0b24f1a6` |
| `docs/STATUS.md` | `7b016fb94669d4d4880ea7d79060a0a91d42bd23e86de31042ced4e71b4852dc` |
| `docs/LOG.md` | `0894b18cd1693531402a8dd3921e8d3dd579f4deda0b76655aa9fe69b3912759` |

I read the complete exporter diff, 631-line Java helper, 805-line converter, 791-line test file, and ADR 0040. I read both unchanged byte readers. I inspected the ordinary launcher, index, mapping and publication code, source/tool identity helpers, and relevant ordinary switch collection. I read AGENTS.md, SPEC.md, ADR 0036, ADR 0038, and all three named U5 design documents. I read the full writer report and the parent's scope, after-push, and actual static proofs. [input-identities.json](input-identities.json) records the named public document hashes. The parent's server verification remains evidence from its public after-push record. This review made no network request.

The same-call boundary passes source inspection. `ExportLift.decompile` makes one ordinary `decompileFunction` call. It passes that result object directly to the byte helper. Ordinary raw C, analyzed operations, and printer markup come from that object. The diagnostic path does not invoke the normalized switch exporter. Listing reads supply raw operations without a second decompile call. The roster is checked before collection and checked again against the ordinary lift during conversion.

The helper uses `SequenceNumber.getTime()` for operation identity and actual `VarnodeAST.getUniqueId()` values for value identity. Identity maps check the actual Java objects. Equal storage does not combine distinct values. Ordered input slots remain ordered. The helper retains block order, empty blocks, unreachable blocks, reciprocal edge slots, conditional polarity, and phi operand order. Its complete analyzed inventory includes block-owned operations and explicitly excluded operations. Exclusion requires a dead flag and no parent. Active values cannot depend on excluded definitions. Raw effects remain in the ordinary lift. Structural parsing supplies no raw/analyzed semantic effect proof.

The separate facts record retains actual input/free flags and actual operation dead/parent fields. A block-owned operation with a true Java dead flag stays in its block. Its `cfg_unclosed` gap is required. Neither the producer nor this review interprets that flag as proved native liveness. A graph refusal returns no partial graph, source, or facts. A printer refusal can retain a complete structural graph with an unavailable source record and an explicit source gap.

Printer accounting uses one forward UTF-8 byte offset. It encodes and compares each indent, token, and line separator once. It does not encode the preceding source for each token. Unpaired surrogates and byte mismatches give gaps. Actual null token links stay null. Operation and varnode links require object membership. `getHighSymbol(null)` disables the storage-address fallback. Formal ordinals and complete static storage fields remain proposals. The independent Java controls check exact UTF-8 bounds, Unicode segments, surrogate refusal, mismatches, empty segments, canonical bytes, and the exact canonical byte limit. The E1 job supplies no complete printer observation, so it supplies no actual positive complete-token evidence.

The source manifest hashes the named installed source files. The tool manifest hashes the specific files selected by `lifting_tool_identity`. It does not hash every installed file. The pinned tools are Ghidra 12.2 at `8ca9077040cc43cd790babcfccf19475622a3e9a` and Java `25.0.5+8-LTS`. The pass retains the function, call ordinal, language, compiler specification, simplification style, timeout, null configured-options object, and manifest digests. Null options mean no explicit `setOptions` call. Pass IDs and hashes are consistency labels. They do not authenticate process origin.

The converter inserts the completed ordinary lift hash and calls both unchanged strict readers. Identity, inventory, and disposition contradictions reject the whole bundle. A contradiction in a later function returns no earlier function result. A coherent local value-ID rename can remain a valid proposal. A coherent empty token inventory can also pass structural conversion. Fresh controls retain both limits. These outcomes give no emission authority. Changing only the on-disk context file after the mocked job has consumed it does not change the retained initial context. The converter still compares the draft to that retained context. This is also a consistency check, not process authentication.

The actual static input was the approved public E1 binary at `/Volumes/PhoenixWork/tmp/m2-production-u1-e1.ibT17k/gcc-pie-plt-standard.elf`. Its SHA-256 is `8b4316d8f2975fe6a0ff61876c483d8089309c3b6371c32b6da9de9d5db96bca`. No target executed. [static_check.py](static_check.py), [static/command.json](static/command.json), and [static-verified.json](static-verified.json) retain the static procedure and checks.

| Actual diagnostic observation | Result |
| --- | --- |
| Complete ordinary roster | 19 functions. |
| Raw and analyzed inventories | 472 raw operations and 101 analyzed operations. |
| Entry gaps | Nine `entry_unrepresentable` functions. |
| Printer gaps | Ten `empty_printer_token` functions. |
| Complete source observations | Zero. |
| Retained block-owned Java dead-flag conflicts | 13 operations with required conflict gaps. |
| Parent comparison | All six saved artifacts match byte for byte. |

The six artifacts are `lift.json`, `mapping.json`, `byte-draft.json`, `context.json`, `result.json`, and `inspection.json`. Their exact copies are in [static](static). These are diagnostic counts, not `phoenix-eval` headline measurements.

I also ran the unchanged default launcher against the current source. It produced only `lift.json`. This run proves that the current default script can resolve the added helper from the ordinary script directory. I then ran the parent exporter and parent launcher from an owned source copy without the byte helper. Base default, current default, and diagnostic lift bytes are identical. Their lift hash is `74939e9fd429f31e9060d23b4de8733415f88dfdb041c00ebc1107be0229fec8`. The diagnostic mapping hash is `3802a0d54d1868a03b5cd09b99924523594dfbf47a4823bc6c5abd06206205bc`, and it matches the parent's saved mapping. [base_default.py](base_default.py) and [base-default-verified.json](base-default-verified.json) retain the independent base comparison. The controller added its command and log files after separating them from product output accounting.

The old two-argument exporter path still selects only ordinary switch collection. The byte helper is absent from that path. The old launcher and publication implementation are unchanged. The affected host group and 48 additional unchanged switch tests check the old launcher file sets, mapping publication, ordinary switch evidence, and publication versions 1 through 3. No byte file enters an old selected generation. No version 4 or current selector is issued by the diagnostic producer.

All verification commands and exits are retained in the named `*-command.json`, `.log`, and `.exit` files below. Each command ran through [run.sh](run.sh). Every review shell sourced the required environment. The test commands use the exact audit `--rootdir` and `--confcutdir`. Logs, caches, TMPDIR, and pytest basetemp use the permitted roots.

| Check | Result | Exit | Exact command |
| --- | --- | ---: | --- |
| First independent suite | 72 passed, six failed. Fixture and inspection errors. | 1 | [Command](independent-1-command.json) |
| Corrected independent suite | 78 passed. | 0 | [Command](independent-2-command.json) |
| Independent suite with an independent final-size oracle | 78 passed. Replaces the earlier size oracle. | 0 | [Command](independent-3-command.json) |
| Profile bounds and nullable storage | Nine passed. | 0 | [Command](profile-bounds-command.json) |
| Additional malformed, bound, flag, and coherent-pass controls | 18 passed. | 0 | [Command](more-controls-command.json) |
| Finite I/O contract controls | Five failed. F1 remains open. | 1 | [Command](io-contract-command.json) |
| Seven affected public host files | 781 passed, two live tests deselected. | 0 | [Command](host-command.json) |
| Four additional switch host files | 48 passed. | 0 | [Command](switch-host-command.json) |
| Ruff | Passed. | 0 | [Command](ruff-command.json) |
| Ruff format | Both source files passed. | 0 | [Command](ruff-format-command.json) |
| Strict mypy | Converter and new product tests passed. | 0 | [Command](mypy-command.json) |
| Pinned Java compilation | Four exact exporter sources and the review control compiled. | 0 | [Command](javac-command.json) |
| Independent Java controls | 16 passed. | 0 | [Command](java-controls-command.json) |
| First static controller | Real job completed. Review oracle failed on JSON key order. | 1 | [Command](static-command.json) |
| Saved static checks and current default | Passed. Six artifact matches and exact default file set. | 0 | [Command](static-saved-default-command.json) |
| Parent default comparison | Passed. Base, current, and diagnostic lift bytes match. | 0 | [Command](base-default-command.json) |

The 105 passing fresh Python controls use [test_independent.py](test_independent.py), [test_profile_bounds.py](test_profile_bounds.py), and [test_more_controls.py](test_more_controls.py). Repeat runs do not add controls to this total. Their final expected data come from explicit fixture records, direct field comparisons, independent JSON encoding, byte slices, and hashlib. Product serializers or schema projections do not supply the final oracle for the same behavior. Fixture helpers supply public synthetic inputs only. Mocked jobs prove transaction checks only. The earlier final-size control used the product serializer to measure a wide result. I replaced that oracle with an independently assembled payload and repeated all 78 controls. The earlier control remains in [test_independent-2.saved.py](test_independent-2.saved.py).

| Fresh control area | Checked behavior |
| --- | --- |
| Exact artifact bounds | Exact binary, lift, mapping, companion, bundle, graph-wire, source-wire, source-byte, token, storage, and reference limits pass. Reduced limits refuse. |
| Profile counts | 32 functions and blocks pass. 33 refuse. Both raw and analyzed banks pass at 256 operations and refuse 257. The analyzed bound includes excluded records. |
| Direct objects | Mutated invalid limit objects and non-byte artifacts refuse before parsing. |
| Malformed and changed records | Invalid JSON, duplicate fields, non-finite numbers, invalid bytes, missing or duplicate functions, changed sequences, widths, phi slots, source hashes, UTF-8 spans, ownership, and extra facts refuse. |
| Identity | Changed coherent pass configurations refuse. Coherent local-ID renaming stays a proposal. Exact raw C bytes remain bound. |
| Flags and storage | Dead flags require their conflict gaps. Null links remain null. Signed stack offsets, register names, sizes, and storage addresses remain intact. |
| Job transaction | One diagnostic job, owned staging, exact output names, original and staged input checks, staged and installed source checks, and post-job tool checks. |
| Output file types | Missing, extra, symlink, hard-link, FIFO, and directory outputs refuse. No FIFO read blocks. |
| Source/tool failures | Missing source, tool, properties, and Java release files use expected I/O/tool categories. Twelve unexpected source/tool hash controls preserve their original exception types. |
| Process control | Actual synthetic children exercise success, nonzero exit, timeout, log excess, and spawn failure. The timeout clock is accelerated. Pipe EOF proves that the controlled descendant closed its inherited descriptor after group cleanup. Direct child processes are waited. |

The artifact limits do not bound all memory. The 160 MiB sum counts the binary, lift, mapping, and one companion representation. Draft and final representations can coexist. JSON trees, strings, graph records, source encoding, and serialization require additional Python heap. Java's new checks do not prevent the ordinary exporter or Ghidra from constructing their own analysis objects first. The Java heap setting is 512 MiB, not a bound on all JVM and native process memory.

The log control wrote 9 MiB before the next poll rejected it. Thus 8 MiB is a rejection threshold. It is not a hard on-disk cap. The code checks at roughly 0.1-second intervals. Neither that threshold nor the artifact limits impose a whole-staging disk quota. Ghidra project files, script caches, and other logs have no aggregate disk bound in this unit. These limits must not be reported as a Python heap bound or a staging quota.

Every failed control remains available. [test_independent-1.saved.py](test_independent-1.saved.py) and [independent-1.log](independent-1.log) preserve the first run. One fixture expected the outer exception for a nested zero limit. Another changed aliased dictionaries repeatedly. Four `ps` checks were denied with EPERM. I corrected the fixtures and used pipe EOF without changing the guard. [static_check-1.saved.py](static_check-1.saved.py) and [static.log](static.log) preserve the first static oracle failure. It compared equivalent sequence dictionaries through JSON strings with different object-key order. The corrected tuple comparison used the saved job artifacts. No failed job artifact was replaced with a new passing job artifact. The five F1 failures are product findings and remain failing.

[process-exceptions.md](process-exceptions.md) records the process exceptions. Initial read-only discovery occurred before explicit sandbox-exec wrapping. It read no protected file data. The necessary v5 profile was then located and copied. Only the permitted audit write destination changed. All v5 read rules remain exact. All tests, compilation, and static jobs used that profile. The first script invocation lacked executable permission. One explicit `/usr/bin/rg` path did not exist. A path glob also produced a no-match error. These setup errors supplied no product evidence. No guard restriction was relaxed.

This was a direct review. No nested agent, model CLI, model API, session, plugin model, or wrapper model ran. No service setting changed and Fast mode was not enabled. I used the requested [poteto-mode skill](/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.137/skills/poteto-mode/SKILL.md) and its direct Investigation and prose guidance. The fixed user scope replaced nested-model, comment-editing, and shipping steps. No network, Docker, Colima, VM, installation, image change, or C build ran. No original or rebuilt target ran on the host. The private Author retained the VM. No sealed source, held-out input, source archive, private run, Author output/history, session history, or pre-existing event/stderr/summary file data was read. Some discovery commands listed names only.

Only one real headless job ran at a time. The diagnostic, current default, and parent default jobs all returned. All direct review child commands returned. The four synthetic cleanup controls passed. No background child is retained. Global process inspection was denied, so this review does not claim a global process census.

F1 requires a correction and fresh review before this diagnostic unit receives PASS. Complete producer admission still requires the separate Astra adapter design for actual analyzed entries, Java bank dead flags, and zero-length printer items. Both existing readers remain unchanged.

The remaining U5 gates include complete producer evidence, a real compiled fill/copy positive, complete raw/analyzed effect relations, recurrence and result checks, finite complete-function source grammar, source-to-IR correspondence, interface and pointer proof, ordinary-memory assumptions, emission, protected active definitions, pipeline binding, resume, and exact replay. Version 4 atomic publication and `ByteLiftGeneration` remain separate work. The frozen public compiler/optimization matrix, four-way builds, differential behavior, integrity controls, mechanism-presence checks, and native checks remain open. This review closes no full capture gate.

M2 through M4 remain open. SPEC section 9 still requires M4 completion, T0 through T3 results against every baseline with costs and a failure taxonomy, publication of the required harness and benchmark artifacts, and reproduction of every headline number through `phoenix-eval --replay`. This static subunit review establishes none of those completion conditions.
