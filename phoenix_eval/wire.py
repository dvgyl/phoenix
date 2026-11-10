import json
from base64 import b64decode, b64encode
from typing import cast

from phoenix_eval.case import CaseFailure, CaseResult, FailureKind, Invocation
from phoenix_eval.outcome import (
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
)
from phoenix_eval.trace import CodeTrace

PROTOCOL_VERSION = 1


def encode_invocation(case: Invocation) -> str:
    return json.dumps(
        {
            "args": case.args,
            "stdin": _encode_bytes(case.stdin),
            "tree": _encode_tree(case.tree),
            "environment": dict(case.overlay),
        }
    )


def decode_invocation(line: str) -> Invocation:
    data = _object(json.loads(line))
    return Invocation(
        args=tuple(_string(arg) for arg in _array(data["args"])),
        stdin=_decode_bytes(data["stdin"]),
        tree=_decode_tree(data["tree"]),
        overlay=tuple(
            (name, _string(value))
            for name, value in _object(data["environment"]).items()
        ),
    )


def encode_result(result: CaseResult) -> str:
    if isinstance(result, CaseFailure):
        return json.dumps({"failure": result.kind, "detail": result.detail})
    termination = result.termination
    trace = result.trace
    return json.dumps(
        {
            "stdout": _encode_bytes(result.stdout),
            "stderr": _encode_bytes(result.stderr),
            "exit": termination.code if isinstance(termination, Exited) else None,
            "signal": termination.number if isinstance(termination, Signaled) else None,
            "tree": _encode_tree(result.tree),
            "trace": (
                {
                    "start": trace.start,
                    "end": trace.end,
                    "entry": trace.entry,
                    "hits": trace.hits,
                }
                if trace is not None
                else None
            ),
        }
    )


def decode_result(line: str) -> CaseResult:
    data = _object(json.loads(line))
    if "failure" in data:
        return CaseFailure(
            FailureKind(_string(data["failure"])), _string(data["detail"])
        )
    exit_code, signal = data["exit"], data["signal"]
    if (exit_code is None) == (signal is None):
        raise ValueError("The outcome must contain either an exit code or a signal.")
    return Outcome(
        stdout=_decode_bytes(data["stdout"]),
        stderr=_decode_bytes(data["stderr"]),
        termination=Exited(_integer(exit_code))
        if signal is None
        else Signaled(_integer(signal)),
        tree=_decode_tree(data["tree"]),
        trace=_decode_trace(data.get("trace")),
    )


def _decode_trace(value: object) -> CodeTrace | None:
    if value is None:
        return None
    trace = _object(value)
    return CodeTrace(
        start=_integer(trace["start"]),
        end=_integer(trace["end"]),
        entry=_integer(trace["entry"]),
        hits=tuple(_integer(hit) for hit in _array(trace["hits"])),
    )


def _encode_bytes(data: bytes) -> str:
    return b64encode(data).decode("ascii")


def _decode_bytes(value: object) -> bytes:
    return b64decode(_string(value), validate=True)


def _encode_tree(tree: TreeSnapshot) -> dict[str, object]:
    return {
        "mode": tree.root_mode,
        "entries": [
            {
                "path": entry.path,
                "kind": entry.kind,
                "mode": entry.mode,
                "data": _encode_bytes(entry.data),
            }
            for entry in tree.entries
        ],
    }


def _decode_tree(value: object) -> TreeSnapshot:
    tree = _object(value)
    entries = []
    for item in _array(tree["entries"]):
        entry = _object(item)
        entries.append(
            TreeEntry(
                path=_string(entry["path"]),
                kind=EntryKind(_string(entry["kind"])),
                mode=_integer(entry["mode"]),
                data=_decode_bytes(entry["data"]),
            )
        )
    return TreeSnapshot(_integer(tree["mode"]), tuple(entries))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Expected a JSON object with string keys.")
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON array.")
    return cast(list[object], value)


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected a string.")
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Expected an integer.")
    return value
