The owner needs verified Phoenix completion through SPEC.md section 9.
This report checks only the named local data-format functions at exact
`9672a0f414e6fe128f8a1763c66694f551f2e2f5`.

Verdict is PASS for `phoenix/observe/runtime.py`, `parse_receipt`, and
`_outcome` under the declared data-format contract. No data-format defect
was found. This verdict does not supply the missing full-component review.
It does not verify project completion or close a milestone.

The review used the specified [API](../m2-capture-admission/api.md) and
[report](../m2-capture-admission/report.md). The reviewer read AGENTS.md and
SPEC.md. The requested installed skill was present at
`/Users/devg/.codex/plugins/cache/pstack-claude/pstack/0.9.135/skills/poteto-mode/SKILL.md`.
No replacement was needed. Requested GPT-6.1 Sol and Standard service are
launch settings. The reviewer did not independently attest routing.
No provider or safety setting was changed. No nested agent was started.

The data shapes are a fixed runtime manifest, a fixed receipt, and a complete
process outcome with a file tree. Independent fixtures use JSON dictionaries,
byte strings, and fixed numeric bounds. They do not use target execution.

The source identities are as follows. SHA-256 values hash exact file bytes.

| File | SHA-256 | Git blob |
| --- | --- | --- |
| `phoenix/observe/runtime.py` | `1de1e6e1df74ef49a19731d916548b75df6be1533fdf13f1e9de55da2a4cc6f2` | `0a71a31394237f9986bc09da51d3c5bbccaaa32d` |
| `phoenix/observe/admission.py` | `9fab8a358b5f7181bcab69bf7c7a00f7274ccb44c0658a7a6d9348908efd9082` | `3781b32e0b5542ed954e3f00ff9f23000768ef3f` |
| `tests/test_observe_admission.py` | `d21c9d694fbbf393ba55ac4c4ab085c2df23c0cb60fd04ef24055a89ce5df2d0` | `60cc9542c582a328ea697c13e4a76046c748e04a` |

`parse_receipt` occupies lines 62 through 121. Its function text SHA-256 is
`3c8c81f5f7ec9d31e2cf7cc43133f84ca70c947193c70773a47b82d057667389`.
`_outcome` occupies lines 124 through 138. Its function text SHA-256 is
`e49a7f741d5b3d57f1a23e44b4b1f03328f0b6f80fc12c5896ed8e7347b0982a`.
These function hashes exclude the final line feed.
[verify_source.py](verify_source.py) defines the exact extraction method.

The following checks passed.

| Contract | Result and evidence |
| --- | --- |
| Exact fields and types | Each declared field is required. Unknown fields fail at each object level. Tests replace every field with other JSON types. Booleans and floats fail in integer fields. |
| Runtime profile | Schema strings, version, commit, both image IDs, and all six ordered register pairs are checked. Each register width must be integer 64. Missing pairs, extra pairs, changed order, and wrong widths fail. No instruction meaning was assessed. |
| SHA-256 | Digest fields require 64 lowercase hexadecimal characters. Image IDs also require the `sha256:` prefix. The runtime pin compares the exact input bytes. The guard digest matches an independent JSON and SHA-256 calculation. |
| Integer bounds | Receipt sequence values accept 0 through 9,999. Emitted events accept 0 through 10,000. Each other count accepts 0 through 1,000,000. Numeric address and stack fields accept 0 through 2^64 minus 1. Both endpoints and values outside each bound were tested. |
| Byte limits | Runtime manifests and receipts reject empty input and input above 65,536 bytes. A receipt at exactly 65,536 bytes parses. The canonical serializer accepts exactly 65,536 bytes and rejects one more byte. Outcomes accept an independently built canonical record at exactly 33,554,432 bytes and reject one more byte. |
| Duplicate keys | Equal duplicate keys and escaped duplicate keys fail. Nested receipt and outcome duplicates also fail. |
| Deterministic serialization | Runtime JSON uses ASCII, sorted keys, compact separators, and one final LF. Outcomes use the exact existing outcome protocol bytes. Different spacing, key order, or a final LF on an outcome fails. Noncanonical Base64 fails. Unicode escapes are deterministic. |
| Receipt serialization | Equivalent JSON spacing and UTF-16 JSON parse to equal receipts. The API requires strict JSON fields but does not require canonical receipt bytes. A false Boolean guard value is valid syntax. Admission must check its meaning separately. |
| Complete output | Parsing preserves stdout, stderr, termination, root mode, paths, entry kinds, entry modes, contents, and link targets. Changing each tested component changes the parsed outcome. Existing admission tests reject changed accepted outputs and invocation data. |
| Outcome validity | Exit codes accept 0 through 255. Signal numbers accept 1 through 64. Exactly one termination field must be non-null. Modes accept 0 through 4,095. Duplicate paths, invalid paths, missing directory parents, and invalid link data fail. Failure records and analysis traces fail. |
| Immutable results | Assignment to parsed manifests, receipts, nested receipt records, outcomes, termination records, and tree records raises `FrozenInstanceError`. Collections are tuples. Data values are bytes. This is normal Python frozen-model behavior. |
| Schema round trips | Independent generated runtime, receipt, and outcome records preserve their declared values. Existing generated tests also pass. |
| Failed parses | Every negative independent case requires `MappingError` and leaves the caller's return variable unchanged. Source inspection confirms that the named parsers return only after their checks finish. No rejected parse returns a partial model. |
| Source-file identity | An independent calculation matches `admission_implementation_sha256`. Synthetic source trees test every listed file separately. A missing file, directory, file symlink, or parent-directory symlink fails. |

The installed admission source identity is
`98bf983bb30a6dc9be5cb183eb11776bed32934c53bd5995e7d8aced7e7f0f0f`.
Its ten relative file names and exact hashes are in
[source-identity-final.log](source-identity-final.log).
This digest identifies the declared source files. It does not attest process
execution, interpreter state, or collector provenance. A parsed digest field
also needs its caller's identity comparison. Those wider checks remain
outside this verdict.

The commands and results are as follows. All scripts run from the worktree.
They source the specified environment file. Test scripts disable bytecode
writes and pytest cache output. Their temporary files and Hypothesis data
stay in `/Volumes/PhoenixWork/tmp/m2-capture-data-formats-sol/`.

| Command | Result |
| --- | --- |
| `git rev-parse HEAD` | Exact requested commit. |
| `git status --porcelain=v1` | Empty before and after the review. |
| `zsh /Volumes/PhoenixWork/audit/m2-capture-data-formats-sol/run-existing.sh` | Exit 0. 69 passed. See [existing-tests.log](existing-tests.log). |
| `zsh /Volumes/PhoenixWork/audit/m2-capture-data-formats-sol/run-independent.sh` | Exit 0. 128 passed. See [independent-tests.log](independent-tests.log). |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" .venv/bin/python /Volumes/PhoenixWork/audit/m2-capture-data-formats-sol/verify_source.py` | Exit 0. Exact source bytes match Git. The independent source identity matches. |
| `.venv/bin/ruff check --no-cache /Volumes/PhoenixWork/audit/m2-capture-data-formats-sol/test_data_formats.py` | Exit 0. All checks passed. |
| `.venv/bin/ruff format --check --no-cache /Volumes/PhoenixWork/audit/m2-capture-data-formats-sol/test_data_formats.py` | Exit 0. File already formatted. |

Python was 3.12.13. Pytest was 9.2.0. Hypothesis was 6.170.15.
Ruff was 0.17.4. Both final test commands use Hypothesis seed 9672.
The independent cases are in [test_data_formats.py](test_data_formats.py).
These counts are local unit-test results. They are not Phoenix evaluation
results or portability measurements.

The first independent command failed during pytest collection. Pytest tried
to inspect an ancestor directory and received `PermissionError` for
`/Volumes/PhoenixWork/holdout`. No file content from that directory was read.
The command then set both `--rootdir` and `--confcutdir` to this audit directory.
The final command passed. The initial error remains in
[independent-collection-error.log](independent-collection-error.log).
No prior session log or dispatch event file was read.

The Prove It Works principle led to executable cases and exact source checks.
The Test Behavior, Not Implementation principle led to assertions on parsed
values and rejected inputs. The Model the Domain principle led to separate
fixtures for each declared record shape. The technical-writing and unslop
skills were applied with the user's ASD-STE100 standard. Skill steps that
require agents, source changes, history reads, or broader work were skipped
under the user's explicit limits. The task list records those choices.

The missing full-component review remains open. Machine-instruction meaning,
frame reduction, collector behavior, runtime process association, live
calibration, actual portability, and evaluation integrity were not reviewed.
No target, container, fetched binary, network call, model-provider call, or
security scan was run. No sealed source, held-out input, private author log,
actual evaluation run, or session history was read. The separate agent-sealed
corpus was not changed.

SPEC.md section 9 still requires verified M4 completion, the full results
report, publication of the required artifacts, and reproducible evaluation
replay. This task does not establish any of those requirements.
Repository files remain unchanged. No commit or push was made.
