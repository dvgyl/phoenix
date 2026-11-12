Phoenix requires verified completion through SPEC.md section 9. This review checks only the structural source-token reader. It does not establish completion of U5 or Phoenix.

HOLD for this unit at `8d167b18bf5d83b4fc8826f74ce9f4c6c6fd92ae`. One medium-severity defect remains. The reader converts some unexpected hashing errors into malformed-data errors. Six independent controls reproduce this defect. The structural data controls passed. The verdict follows source inspection and the controls below. A zero exit code alone is not approval.

| Review identity | Exact value |
| --- | --- |
| Worktree | `/Volumes/PhoenixWork/worktrees/m1-follow-up-review-e07ec17` |
| Branch | `agent/m2-byte-source-reader` |
| Revision | `8d167b18bf5d83b4fc8826f74ce9f4c6c6fd92ae` |
| Base | `fbcdab586571170a80f7472475100e1083bc74d8` |
| Revision manifest | [revisions.json](revisions.json) |
| Prerequisite approval | [review-ready.json](review-ready.json) |
| Final evidence | [verification.json](verification.json), [after.json](after.json) |
| Exact check commands | [commands.md](commands.md) |

The revision and branch match the manifest. The worktree is clean. `git ls-remote` returned the exact revision for the remote branch. The named commit-hook receipt reports `Phoenix quality checks ... Passed`. Its separate exit file contains `0`. These are prerequisite records. I did not run a hook, commit, or push. I did not infer a test count from that receipt. The parent report is supporting evidence and is not approval.

The parent approved the graph prerequisite in review-ready.json. Its frozen report digest is `d5acb2d8635bb50ed68d66abfd87640521d73e6c8d9a779798bd672571bf92f0`. I read the actual [graph review](/Volumes/PhoenixWork/audit/m2-byte-graph-review-sol-20261112/report.md) and checked that digest. The graph source is byte-identical to the source-reader base. Its SHA-256 is `f3f20ccbc92ad1cfeadf6912d8943871bf4e852d60008f2652d5f8f62b218bf3`.

I read AGENTS.md, SPEC.md, the required poteto-mode skill, and the comment-sicko reference. I used direct source inspection under the Investigation workflow. The explicit user prohibition replaced all nested-model steps. The fixed write boundary replaced repository task and progress writes. I also read the no-comments, how, and unslop skill instructions. No delegation, shipping, or source-edit step ran. `throughput checkpoint: n/a, read-only investigation`.

I read the approved U5 [design](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/design.md), [API](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/api.md), and [report](/Volumes/PhoenixWork/audit/m2-byte-idiom-design-astra-20261112/report.md). I inspected the actual new source, tests, ADR 0038, and progress additions. The complete diff is retained in [reviewed.diff](reviewed.diff). I also inspected the actual graph reader, old lift launcher, lift index, mapping helpers, and static StoragePiece definition and validation. These dependencies explain what the reader can compare and what remains a producer proposal.

Only five files differ from the base. There are 1,021 added lines and no removed lines. The two progress files retain their complete base prefix. Every previous implementation file remains unchanged. The source hashes match the supervisor's source-identities.json before and after the checks.

| Added file | SHA-256 |
| --- | --- |
| `phoenix/lift/byte_source.py` | `eff89e91dbfd11d6e04c9cce9115bf3b4e62882b1e581c209480280d9b643c4c` |
| `tests/test_byte_source.py` | `33dfb0b494d50400c66721f284f30e0817419e7b48c40f346b35ba4931434778` |
| `docs/adr/0038-byte-source-observations.md` | `26d804311c49e27ff7b6f2ae3d05f92dfe28f290d7607d806085286647127d11` |

F1 has medium severity. It concerns programming-error visibility in [parse_byte_source](/Volumes/PhoenixWork/worktrees/m1-follow-up-review-e07ec17/phoenix/lift/byte_source.py:469). The outer handler covers the complete parser. It catches `UnicodeError`, `RecursionError`, and `OverflowError` from the source hash at line 338 and the token hash at line 382. It converts each error to `ByteSourceError("Invalid source observation data.")`. The original error remains the cause, but its public classification changes. A caller that catches ByteSourceError as a bad proposal can classify an internal hashing failure as an input rejection. This violates the explicit requirement that unexpected hashing errors remain visible.

The independent control replaces only the source module's `sha256` function. It raises a sentinel at the first hash call or the second hash call. The first call hashes the complete source. The second hashes the first token. The expected result is the original error type and message. All six combinations of the two sites and the three error types fail. The corresponding ValueError, RuntimeError, and TypeError sentinels remain visible and pass. These are controlled programming-error injections. I found no ordinary bounded byte input that makes the current standard hashlib implementation raise these three error types. This finding concerns the promised error boundary. It does not demonstrate false acceptance or emission authority.

| Reproducible failing control | Actual result |
| --- | --- |
| `test_unexpected_hashing_errors_remain_visible[source-OverflowError]` | ByteSourceError replaces OverflowError. |
| `test_unexpected_hashing_errors_remain_visible[source-RecursionError]` | ByteSourceError replaces RecursionError. |
| `test_unexpected_hashing_errors_remain_visible[source-UnicodeError]` | ByteSourceError replaces UnicodeError. |
| `test_unexpected_hashing_errors_remain_visible[token-OverflowError]` | ByteSourceError replaces OverflowError. |
| `test_unexpected_hashing_errors_remain_visible[token-RecursionError]` | ByteSourceError replaces RecursionError. |
| `test_unexpected_hashing_errors_remain_visible[token-UnicodeError]` | ByteSourceError replaces UnicodeError. |

Keep JSON value and encoding conversion inside `_canonical`. Keep Unicode conversion at the actual source, token, kind, and storage text encoding or decoding operations. Remove the broad conversion around hashing and structural processing. Retain the existing malformed-input controls. Add the six hashing controls to the permanent tests. Then run the affected checks and obtain review of the exact correction. I made no source change. The failing suite and full tracebacks remain in [test_independent_initial.py](test_independent_initial.py) and [independent.log](independent.log).

The remaining structural checks support the following conclusions under the stated contract.

| Contract | Source and independent evidence | Result |
| --- | --- | --- |
| Complete immutable records | SourceSpan, SourceToken, and ByteSourceObservation are frozen and slotted. Parsed collections are tuples. Function, operation, value, gap, and StoragePiece children are immutable records. `record()` returns detached mutable containers. | PASS. Complete wire round trips and child-mutation controls passed. Direct dataclass construction is not authentication. |
| Canonical wire and complete digest | `_canonical` uses sorted keys, compact separators, ASCII escapes, no nonfinite values, and one final LF. Parsing compares those bytes with the complete input. The digest hashes the complete canonical bytes outside the record. | PASS. Whitespace, ordering, escaped-key aliases, duplicate nested keys, UTF-8 alternatives, UTF-16, BOM, and LF changes reject. Canonical renderer error conversion passed at its own boundary. |
| Closed objects and exact numeric types | Each wire object has the exact required keys. Counts, ordinals, offsets, schema, and formal ordinals reject Boolean and float aliases. Addresses require minimal lowercase hexadecimal text. | PASS. There are 372 field-removal, field-alias, and extra-field cases. There are 45 address-alias cases. JSON-node replacements cover malformed nested types. |
| Function, binary, pass, lift, and source identity | The top-level and nested keys match the supplied graph function and pass. The function exists in the supplied lift. Graph and observation lift identities match the lift. Binary identities agree. Exact UTF-8 source digest and byte count agree with the ordinary lift and graph. | PASS for consistency with a graph from its separate reader. All 27 nested scope substitutions reject. Changed same-length source bytes and changed source counts reject. Failed ordinary decompilation status supplies no accepted raw C. The pass record itself remains unauthenticated. |
| Token spans and ordinals | Ordinals start at zero and are contiguous. Spans have positive length, are ordered, do not overlap, and stay inside the source. Each substring decodes as UTF-8 and has its exact digest. | PASS. Duplicate and reordered tokens, skipped ordinals, overlap, zero length, out-of-range endpoints, wrong hashes, and cuts inside two-byte and four-byte UTF-8 characters reject. Gaps between spans remain permitted. |
| Nullable links and operation domains | Null links remain null. Token operations must name analyzed active or excluded-dead records. Values must exist in the graph. Formal ordinals are bounded to 127. | PASS. Equal raw and analyzed sequence identities remain distinct. Raw token links reject. Raw gap links pass without a block. Excluded-dead token and gap links remain proposals. A valid reference does not authenticate its token association. |
| Complete StoragePiece retention | The reader retains address space, canonical offset, size, register, and signed stack offset for every piece. Width is positive and at most 8,192 bytes. Spans do not wrap. | PASS. The four-piece default boundary and fifth-piece rejection passed. Round trips retain all fields and their order. No capacity, storage role, or interface claim follows. |
| Signed stack boundaries | Stack offset matches the unsigned address representation. Stack pieces have no register label. They cannot cross zero or the upper signed boundary. Non-stack pieces cannot have a stack offset. | PASS. Controls cover minus 2**63, minus one, zero, 2**63 minus one, exact boundary endings, crossed boundaries, and unsigned wrap. |
| Gaps and ownership | The six finite gap codes are retained. Block, operation, and value references resolve. A block paired with an operation must own that active analyzed operation. Duplicate gaps reject. | PASS. Wrong owners, raw or dead operations paired with blocks, missing references, duplicate gaps, and unsupported codes reject. |
| Unavailable observations | An unavailable observation has no tokens and at least one source_unbound gap. It still binds exact ordinary source identity. | PASS. An unavailable observation without that gap rejects. The permanent tests also reject tokens under unavailable status. |
| Caller limits and default caps | Wire bytes are bounded before JSON parsing. Source character count is checked before UTF-8 allocation. Exact source bytes are bounded before hashing. Token, piece, and gap counts are bounded without truncation. | PASS. Every lower limit passed at its exact inclusive boundary and rejected one lower. Minimum limits passed. Defaults passed at 65,536 tokens, 256 distinct gaps, four storage pieces, and 1 MiB of source. Each count or source cap plus one rejected. Invalid, raised, and mutated limit records reject. |
| Malformed data and failures | JSON parsing rejects malformed bytes and duplicate keys. The encoding boundary rejects nonfinite data. Nesting and large numeric text reject with ByteSourceError. | PASS for supplied data controls. There were no uncontrolled malformed-data exception escapes in 1,584 JSON-node replacements. F1 remains a separate programming-error classification defect. |

The independent tests construct their own ordinary lift document, graph wire, and source wire. They use the real parse_lift and parse_byte_graph readers. They do not import the worker's fixtures or construct a graph dataclass as authority. The synthetic binary bytes provide only an identity for the pure readers. They are not executed or claimed as a compiled program. The fixture has active and excluded analyzed operations, raw/analyzed sequence collisions, distinct value IDs, an empty second block, non-ASCII source, storage, and gap references. Expected wire bytes use an independent JSON encoder.

The original independent suite ran 587 pytest cases. It passed 581 and failed the six F1 controls. One passing case performs 1,584 JSON-node replacements. Those replacements are not additional pytest cases. I then added address-alias, coherent-pass, association-limit, and mutated-limit controls. A separate run passed all 52 new cases and deselected the original 587 cases. Across the two runs, 633 distinct cases passed and six failed. No failing case was removed, weakened, or rerun to obtain a green result. The current full test file contains 639 cases.

| Executed check | Actual result | Exit |
| --- | --- | --- |
| [Affected host tests](affected.log) | 617 passed. Two live tests deselected. | 0 |
| [Initial independent suite](independent.log) | 581 passed. Six failed for F1. | 1 |
| [Additional independent controls](additional.log) | 52 passed. Original 587 cases deselected. | 0 |
| [Ruff check](ruff-check.log) | All checks passed for both new Python files. | 0 |
| [Ruff format check](ruff-format.log) | Two files already formatted. | 0 |
| [Strict mypy](mypy.log) | No issues in the new reader and test file. | 0 |
| Initial additional-run helper import | No tests ran. IndexError in the review script. | 1 |
| Final identity and diff checks | Exact clean revision, unchanged source hashes, unchanged graph, identical test copies, append-only progress files, and clean diff checks. | 0 |
| Remote branch check | Exact reviewed revision returned. | 0 |

The affected run used byte-identical copies of the five named test files in this audit directory. Production imports came from the exact reviewed worktree. Both `--rootdir` and `--confcutdir` name this exact audit directory in every pytest command. The guard stayed unchanged. The two excluded live tests are `test_headless_bitstats` and `test_public_phase_grid_storage`. No excluded live test counts as passed.

The failed helper import was a review-script error. It accessed sys.argv[1] when no mode argument was present. No source reader or pytest control ran during that attempt. I corrected the review script to permit import without an argument. The failed traceback is preserved in [harness-import-failure.log](harness-import-failure.log). The subsequent additional-control run passed. This correction did not change a production file or a test expectation.

Maintainability is acceptable apart from F1. The immutable data shape, wire rendering, storage validation, and cross-reference checks have clear roles. The module uses existing graph keys, mapping validators, and StoragePiece records. It adds no pipeline caller, target execution, mutable global state, or bare exception handler. The boundary docstrings state proposal status and the emission limit. The UTF-8 lower-bound comment explains an allocation check. The test type suppression permits an intentional frozen-record mutation attempt. I found no misleading comment or correctness suppression that requires a separate request. No comment was deleted. There are no cosmetic requests. The error-conversion scope in F1 needs a code correction.

The reader does not authenticate a complete printer inventory. A coherent empty token list passes in both the permanent tests and the independent controls. `exact_printer_bytes` remains the producer's assertion. A coherent pass rename also passes. A token can name a different existing value or an excluded operation and still pass structural checks. These are explicit proposal limits, not additional defects under this contract. The old lift and graph do not contain enough evidence to establish complete token associations. This unit is not a completed source binder.

No type, pointer provenance, original arity, object capacity, live value, dominance, source semantics, recurrence, or effect inference follows from these records. Unknown nonempty token kinds remain data for later refusal. Direct construction of any dataclass supplies no producer authentication. The caller must supply a structural graph from its separate reader. This review does not require the later semantic gates to be implemented inside this bounded reader.

All review writes stayed in this audit directory or `/Volumes/PhoenixWork/tmp/m2-byte-source-review-sol-20261112`. No source edit, commit, push, tag, branch change, compiler, actual Ghidra process, target, Docker action, VM action, model-provider call, nested model session, agent, or delegation ran. Existing launcher tests used synthetic host scripts or test doubles. No sealed source, held-out input, source archive, run artifact, Author output/history, session history, or pre-existing event/stderr/summary file was read. Audit reads outside this directory used only the authorized design, review, and supervisor files, plus the hook receipt named in revisions.json. Repository and skill reads are described above. No sibling audit metadata was traversed. The private Author retains the VM. The external mounts were present. Internal free space was about 15 GiB, above the recorded baseline of 14,432,616 KiB.

The following gates remain open.

| Remaining gate | Required evidence |
| --- | --- |
| This reader | Correct F1. Preserve the encoding-boundary conversions. Pass the hashing-error controls and affected checks. Obtain review of the exact correction. |
| Producer and publication | Collect actual ordinary printer bytes and complete token inventory during the same decompilation as the graph. Retain actual operation/value/formal/storage links and the pass record. Bind the source/exporter manifest and companion atomically. Compile against the pinned APIs and inspect actual public export output. |
| Complete source grammar and correspondence | Parse the complete supported function. Explain every token and executable statement. Independently compare the source recurrence, effects, zero path, and result with checked graph evidence. |
| Recognizer and interface | Check reachability, dominance, use order, predecessor availability, recurrence, widths, complete raw/analyzed effects, aliases, and result. Establish supported callable storage roles, genuine object-pointer bindings, and the ordinary-memory contract. Keep unknown facts as gaps. |
| Emitter and pipeline | Recreate the checks before emission. Use a separate protected byte definition. Reject alternate active definitions and bypasses. Bind the opt-in setting, exact source snapshot, resume, and replay. Preserve defaults and Ghidra-raw. |
| Compiled public behavior | Prove actual mechanism presence and active emitted use. Pass fill/copy, zero, overlap, return, sentinel, changed-effect, and inactive-definition controls. Run the accepted independent oracles, required compiler/architecture builds, native CI, and exact replay after VM release. |
| Full capture and collector | Keep the full capture review open after provider screening. This review does not retry or certify it. Collector production and live gates remain separate. |
| Milestones and SPEC section 9 | Complete and verify M2 through M4. Publish required baselines, ablations, benchmark artifacts, costs, and failure taxonomy. Publish the required committed corpus material under the approved sealing process. Reproduce every headline with phoenix-eval replay. |

These host test counts are software checks. They are not Phoenix evaluation results. No held-out score, live U5 result, or milestone acceptance follows. This unit remains HOLD for F1. Production U5 and verified completion through SPEC section 9 remain open.
