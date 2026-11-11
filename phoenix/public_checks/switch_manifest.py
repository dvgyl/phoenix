import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from phoenix.lift.mapping import (
    array,
    bounded_read,
    digest,
    load_json,
    object_fields,
    text,
    uint,
)
from phoenix_eval.case import Invocation


@dataclass(frozen=True, slots=True)
class PublicCase:
    identifier: str
    invocation: Invocation
    development: bool


@dataclass(frozen=True, slots=True)
class SwitchSuite:
    source: Path
    source_sha256: str
    manifest_sha256: str
    cases_sha256: str
    cases: tuple[PublicCase, ...]
    unvisited_selector: int


def load_suite(directory: Path) -> SwitchSuite:
    raw = bounded_read(directory / "manifest.json", limit=4096)
    record = object_fields(
        load_json(raw),
        "schema kind source_file source_sha256 cases_file cases_sha256 "
        "unvisited_selector selector_mask numeric_selectors",
    )
    if (
        type(record["schema"]) is not int
        or record["schema"] != 1
        or record["kind"] != "public-switch-control"
        or record["source_file"] != "main.c"
        or record["cases_file"] != "cases.json"
        or uint(record["selector_mask"]) != 15
        or uint(record["numeric_selectors"]) != 12
        or uint(record["unvisited_selector"]) != 11
    ):
        raise ValueError("The public switch manifest uses an unsupported profile.")
    source = directory / "main.c"
    source_raw = bounded_read(source, limit=65536)
    cases_raw = bounded_read(directory / "cases.json", limit=65536)
    source_hash, cases_hash = (
        digest(record["source_sha256"]),
        digest(record["cases_sha256"]),
    )
    if (
        sha256(source_raw).hexdigest() != source_hash
        or sha256(cases_raw).hexdigest() != cases_hash
    ):
        raise ValueError("The public source or case commitment has changed.")
    cases = []
    case_document = object_fields(load_json(cases_raw), "cases")
    for value in array(case_document["cases"], 256):
        case = object_fields(value, "id args stdin_hex development")
        identifier = text(case["id"])
        if re.fullmatch(r"[a-z0-9-]{1,64}", identifier) is None:
            raise ValueError("The public case ID is invalid.")
        arguments = tuple(text(value) for value in array(case["args"], 4))
        data = text(case["stdin_hex"])
        if re.fullmatch(r"(?:[0-9a-f]{2}){0,64}", data) is None:
            raise ValueError("The public case input is not canonical hexadecimal.")
        if type(case["development"]) is not bool:
            raise ValueError("The public development flag is invalid.")
        cases.append(
            PublicCase(
                identifier,
                Invocation(arguments, bytes.fromhex(data)),
                case["development"],
            )
        )
    if len(cases) != 56 or len({case.identifier for case in cases}) != len(cases):
        raise ValueError("The public case roster has changed.")
    expected = {
        ((str(selector),), data, selector != 11)
        for selector in range(16)
        for data in (b"\x00", b"\xff", b"A")
    } | {
        (args, b"", True)
        for args in (
            (),
            ("-1",),
            ("-16",),
            ("16",),
            ("17",),
            ("4294967295",),
            ("4294967296",),
            ("bad",),
        )
    }
    if {
        (case.invocation.args, case.invocation.stdin, case.development)
        for case in cases
    } != expected:
        raise ValueError("The public case values have changed.")
    omitted = tuple(case for case in cases if not case.development)
    if (
        len(omitted) != 3
        or any(case.invocation.args != ("11",) for case in omitted)
        or any(case.development and case.invocation.args == ("11",) for case in cases)
    ):
        raise ValueError("The public development set does not omit selector 11.")
    return SwitchSuite(
        source, source_hash, sha256(raw).hexdigest(), cases_hash, tuple(cases), 11
    )
