import json

from phoenix_eval.case import Invocation
from phoenix_eval.wire import decode_invocation


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("The case contains a repeated field.")
        result[key] = value
    return result


def _case(line: str) -> Invocation:
    data = json.loads(line, object_pairs_hook=_unique_fields)
    if not isinstance(data, dict) or set(data) != {
        "args",
        "stdin",
        "tree",
        "environment",
    }:
        raise ValueError("The case fields are invalid.")
    tree = data["tree"]
    if not isinstance(tree, dict) or set(tree) != {"mode", "entries"}:
        raise ValueError("The case tree fields are invalid.")
    if not isinstance(tree["entries"], list) or any(
        not isinstance(entry, dict) or set(entry) != {"path", "kind", "mode", "data"}
        for entry in tree["entries"]
    ):
        raise ValueError("The case entry fields are invalid.")
    return decode_invocation(line)
