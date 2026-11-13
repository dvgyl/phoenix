Phoenix must meet every condition in SPEC section 9. This advisory addresses only F2 in the public ordinary-byte diagnostic. It recommends a local Python 3.12 compatibility correction. It does not approve the producer or any semantic claim.

Select a dedicated `_resolve(path: Path, *, strict: bool = False) -> Path` helper in `phoenix/lift/byte_export.py`. Use it at the six caller-controlled resolution sites. Keep `_io` unchanged. The recommendation is ready for implementation. F2 remains **HOLD** until the actual correction passes its controls and independent review.

The inspected HEAD is `b252452d4bc2dbae1474a3b266ca5a5b767f5892`. The exporter SHA-256 is `46758831eaa2fa3f0cd2d14be28a4231c67b0f3f9e1602ea7a7cd9fff066a09d`. Root's six new controls are already present in the test file. Its current SHA-256 is `771769a1148880230ed8cea34c52b71a682503fab41eb4d7ea740730d8deadf7`. I changed no checkout file.

The root cause is the exception type used by the installed Python 3.12.13 implementation. [Path.resolve](/Volumes/PhoenixWork/tools/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/pathlib.py:1228) calls `check_eloop` while it handles an `OSError`. For `errno.ELOOP`, that function raises a plain `RuntimeError`. The original `OSError` becomes its immediate `__context__`. The exception has no explicit cause and does not suppress its context. `_io` catches only `OSError`, so this filesystem failure escapes the finite diagnostic contract.

Strict resolution obtains the error from `realpath`. Nonstrict resolution first obtains a path from `realpath`, then calls `stat()` on that path. It converts `ELOOP` in the same way. Other `OSError` values from that final nonstrict `stat()` are ignored. Thus a missing nonstrict path is not an error at this boundary. The staging call uses `strict=True` and must retain that behavior.

The [independent HOLD report](/Volumes/PhoenixWork/audit/m2-byte-export-f1-review-sol-20261112/report.md) records six failing real-loop contract controls. Its [observation controls](/Volumes/PhoenixWork/audit/m2-byte-export-f1-review-sol-20261112/test_loop_observation.py) separately verify the direct `ELOOP` context. They also verify no job, no conversion, and an unchanged selector. The [root's second before log](/Volumes/PhoenixWork/audit/m2-byte-export-producer-root-20261112/f2-before2.log) reports six failures in the permanent controls. These are retained results from earlier commands, not tests rerun by this advisory.

| Choice | Benefit | Cost and limit | Decision |
| --- | --- | --- | --- |
| Dedicated resolver around `Path.resolve` | Retains the existing strict and nonstrict algorithms. Restricts legacy exception conversion to six resolution calls. | Depends on the inspected legacy exception shape. Needs negative controls for other exception shapes. | Select. |
| Lower-level `os.path.realpath` resolver | Keeps strict `ELOOP` as `OSError`. Avoids the legacy `RuntimeError` conversion. | Nonstrict `realpath` alone permits loops. Matching Python 3.12 requires its extra `stat()` and selective error handling. This duplicates library behavior. | Do not select for F2. |
| Catch all `RuntimeError` in `_io` | Requires little code. | Converts unrelated programming failures from every wrapped operation. It does not establish a filesystem cause. | Reject. |

The selected helper uses the existing `Path` input and `Path` result. It adds no new record or state. Add `import errno`. The following is the exact proposed helper. It is advisory code and has not been installed or executed.

```python
def _resolve(path: Path, *, strict: bool = False) -> Path:
    try:
        return _io(lambda: path.resolve(strict=strict))
    except RuntimeError as error:
        context = error.__context__
        if (
            type(error) is not RuntimeError
            or not isinstance(context, OSError)
            or context.errno != errno.ELOOP
            or error.__cause__ is not None
            or error.__suppress_context__
        ):
            raise
        raise ByteExportError(
            "io", "Cannot complete a diagnostic file operation."
        ) from error
```

The exact-type check keeps subclasses such as `RecursionError` visible. The direct-context check excludes unrelated errors and deeper chains. The last two checks retain the implicit exception shape of the inspected library. They exclude explicit chaining and suppressed contexts. No message text is examined. The new diagnostic preserves the original `RuntimeError` as its cause. That exception retains the underlying `ELOOP` context.

Use these exact replacements at the current source locations.

| Entry point and current line | Proposed expression |
| --- | --- |
| `convert_byte_export`, line 638, installation | `_resolve(installation)` |
| `convert_byte_export`, line 638, Java home | `_resolve(java_home)` |
| `export_byte_diagnostic`, line 703, workspace | `_resolve(Path(os.environ["PHOENIX_ROOT"]))` |
| `export_byte_diagnostic`, line 704, staging | `_resolve(staging_root, strict=True)` |
| `export_byte_diagnostic`, line 710, installation | `_resolve(installation)` |
| `export_byte_diagnostic`, line 710, Java home | `_resolve(java_home)` |

The converter context expression becomes `_context(binary, _resolve(installation), _resolve(java_home), limits)`. The exporter tool assignment becomes `installation, java_home = _resolve(installation), _resolve(java_home)`. Keep the current order of validation and resolution. Keep environment lookup and `Path` construction outside the helper. A missing environment key or invalid path argument must retain its programming error.

Do not change the import-time `_ROOT = Path(__file__).resolve().parents[2]`. It is not one of the caller-controlled boundaries in F2. Do not change the old launcher or shared path helpers. [The tool identity helper](/Volumes/PhoenixWork/worktrees/m1-follow-up-review-e07ec17/phoenix_eval/provenance.py:86) hashes named files after these paths have resolved. It does not need a new resolver for F2.

The lower-level alternative can preserve the inspected POSIX behavior, but only with more logic. First call `os.path.realpath(path, strict=strict)`. Convert its returned absolute string to `Path`. In nonstrict mode, call `stat()` on that result. Reraise only `OSError` with `errno.ELOOP` from this final check. Ignore the other `OSError` values there, as Python 3.12 does. Wrap this complete filesystem operation with `_io`.

`realpath` already handles relative paths, the current directory, relative symlink targets, and `..`. A preliminary lexical normalization can change symlink meaning and is unnecessary. Setting `strict=True` for every path would incorrectly reject missing nonstrict paths. Omitting the final nonstrict check would return a loop path. Converting every final `stat()` error would incorrectly reject other paths that Python 3.12 returns. This alternative also loses `Path` subclass behavior supplied through `with_segments`. It requires POSIX and version-specific parity controls. No hand-written traversal or dependency is justified.

A broad `_io` catch would hide a `RuntimeError` from `mkdir`, `write_bytes`, directory enumeration, log operations, or cleanup. The independent review already contains programming-error controls for these operations. Hash and context calculations currently remain outside `_io`. Merely broadening `_io` would not directly catch those separate calculations. Keep them outside it. A new outer catch around the exporter would also hide those failures and is unacceptable. Keep process-launch `OSError` handling in `_headless` unchanged. Its category remains `headless`.

The compatibility claim is limited to the inspected CPython 3.12.13 POSIX implementation. Its `pathlib.py` SHA-256 is `10ba48ae8063cfe7589436041d0d4628c05f427c7709cf8e75e486f8930cc32c`. Its `posixpath.py` SHA-256 is `03825681086638649a43480954f7f6a16b4da3bd41ece956864ae96e4f795cd9`. Use `errno.ELOOP`, not the numeric errno from macOS. No Linux runtime test or Windows compatibility test ran here. Windows-only `winerror` handling is outside this correction. Recheck library behavior when the Python version changes.

If a future resolver raises `OSError` directly, the existing `_io` path can convert that error. If a future nonstrict resolver returns a loop without an exception, this helper cannot reject it by exception conversion. No future-version guarantee is supplied. The helper also does not prevent filesystem races or authenticate exception origin. Arbitrary replacement code can deliberately raise the exact legacy exception shape. Distinguishing such code would require a different trust boundary. The selected correction assumes the ordinary installed `Path.resolve` implementation.

The following controls are required for the implemented correction. They are proposed controls unless identified as existing evidence.

1. Retain root's six real self-link controls. Require `ByteExportError.code == "io"`, no job or conversion, and the unchanged previous selector. Inspect the cause and its immediate `ELOOP` context. Add a two-link cycle and a loop in a parent directory in both strict modes.
2. Check existing absolute and relative paths, valid relative symlinks, and symlinks followed by `..`. Require the same resolved path as the installed `Path.resolve`.
3. Check missing paths and dangling links. Nonstrict calls must retain the original return behavior. Strict calls must reject with `io` and the original `OSError` as cause. Keep file-as-staging rejection unchanged.
4. At the resolver boundary, inject plain `RuntimeError`, `TypeError`, `ValueError`, and `RecursionError`. Require the original exception object. Include a runtime error with direct `OSError(EACCES)`, one with no context, and one with `ELOOP` only deeper in its chain.
5. Inject a `RuntimeError` with an explicit cause, a suppressed context, or a runtime-error subclass, each with direct `ELOOP` context. Require the original object. Vary the message to prove there is no message matching.
6. Inject native `OSError(ELOOP)` and `PermissionError` directly from resolution. Require `io` and the original exception as cause. These controls verify the existing `_io` branch.
7. Inject a legacy-shaped `RuntimeError` into a non-resolution filesystem operation. Require that the original object escapes `_io`. This control distinguishes the selected helper from a broad `_io` correction.
8. Repeat the existing tool-hash and context exception controls. Include hash and context failures raised while handling `OSError(ELOOP)`. Require unchanged exception identity. Repeat launch controls to retain `headless` for launch `OSError` and visible programming exceptions.
9. Repeat the five original F1 controls and the affected host suite. Verify old schemas, defaults, publication versions 1 through 3, and source-pin contents. The exporter source digest must change naturally after an edit. Do not retain a stale digest or change a tool pin to hide that change.

I read AGENTS.md and SPEC.md in full. I read the installed `poteto-mode` skill, its Investigation steps, and the local prose guidance. I inspected the complete exporter, permanent test file, ADR 0040, relevant path and tool code, and the two independent loop-control files. The [checklist](todo.md) records the read-only scope. The user prohibition overrides skill delegation and shipping steps. No plugin was loaded.

No new Python test executed in this advisory. The first explicit sandbox wrapper failed before Python started. It returned `sandbox_apply: Operation not permitted`. [setup-failure.log](setup-failure.log), [setup-result.json](setup-result.json), and [run.sh](run.sh) preserve this attempt. I did not retry it, remove the sandbox, inspect the guard, or run an alternate Python entry point. The unexecuted `record.py` file is a retained setup artifact, not test evidence. Shell SHA-256 checks supplied the source identity records instead.

The retained test evidence is as follows. These software-control counts are not `phoenix-eval` results.

| Record inspected | Recorded result | Meaning |
| --- | --- | --- |
| Independent real-loop contract and exit record | Six failed. | F2 is reproduced at all six public call sites. |
| Independent observation controls and exit record | Six passed. | The raw exception and absence of side effects are confirmed. F2 stays open. |
| Root `f2-before2.log` and result record | Six failed, 146 deselected, exit 1. | The permanent controls reproduce F2 on the current source. |
| Root first wrapper error record | The wrapper used the read-only zsh `status` variable. | Its failed setup record remains intact. |
| This advisory's sandbox setup | Failed before Python started. | No new runtime PASS or correction validation. |

The general filesystem contract and the complete diagnostic-unit review remain HOLD. Complete producer admission also remains HOLD for analyzed entry association, native liveness evidence, and zero-length printer items. No production caller is enabled. No schema, reader, source pin, default, or publication changes are authorized by this advisory. Full capture review remains OPEN after provider screening. It was not retried or replaced. Semantic proof, byte-loop emission, live behavior, M2 through M4, and SPEC section 9 completion remain open.

No nested model, agent, model API, model CLI, session, or dispatch wrapper ran. No service setting changed and Fast mode was not enabled. No network, credential, target, compiler, Ghidra, Docker, Colima, Lima, or VM access occurred. No private source, held-out input, archive, private run, Author material, dispatcher event, dispatcher stderr, dispatcher summary, or session history was read. Writes stayed in the two assigned directories. [final-check.json](final-check.json) records the before and after source hashes and the final scope check.
