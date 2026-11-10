import hashlib
import json
from dataclasses import replace
from pathlib import Path

from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine, run_cases
from phoenix_eval.outcome import Outcome
from phoenix_eval.wire import (
    decode_invocation,
    decode_result,
    encode_invocation,
    encode_result,
)

_EVIDENCE_LIMIT = 64 * 1024 * 1024


class DevelopmentError(ValueError):
    pass


def _read(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(_EVIDENCE_LIMIT + 1)
    if not 0 < len(data) <= _EVIDENCE_LIMIT:
        raise DevelopmentError("The development evidence size is invalid.")
    return data


def _cases(data: bytes) -> tuple[tuple[Invocation, Outcome], ...]:
    try:
        document = json.loads(data)
        records = document["cases"]
        if not isinstance(records, list) or not records or len(records) > 4096:
            raise ValueError
        cases = []
        for invocation, saved in records:
            case = decode_invocation(invocation)
            outcome = decode_result(saved)
            if not isinstance(outcome, Outcome):
                raise ValueError
            cases.append((case, replace(outcome, trace=None)))
        return tuple(cases)
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise DevelopmentError("The saved development evidence is invalid.") from None


def freeze_development(path: Path, destination: Path) -> str:
    cases = _cases(_read(path))
    data = json.dumps(
        {
            "cases": [
                (encode_invocation(case), encode_result(outcome))
                for case, outcome in cases
            ]
        },
        ensure_ascii=True,
        sort_keys=True,
    ).encode("ascii")
    if len(data) > _EVIDENCE_LIMIT:
        raise DevelopmentError(
            "The frozen development evidence exceeds its size limit."
        )
    destination.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def verify_development(
    original: Path | bytes,
    path: Path,
    digest: str,
    images: dict[str, str],
) -> frozenset[bytes]:
    data = _read(path)
    if hashlib.sha256(data).hexdigest() != digest:
        raise DevelopmentError("The frozen development evidence has changed.")
    cases = _cases(data)
    inputs = tuple(case for case, _ in cases)
    expected = tuple(outcome for _, outcome in cases)
    for engine in (Engine.ROSETTA, Engine.QEMU_X86_64):
        observed = run_cases(original, inputs, engine, image=images[engine.platform])
        if observed != expected:
            raise DevelopmentError(
                "The original did not reproduce the development outcomes."
            )
    return frozenset(
        value for outcome in expected for value in (outcome.stdout, outcome.stderr)
    )
