import json
import shutil
import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from phoenix.llm.provider import Model, Request, Usage
from phoenix.public_checks import switch_gate
from phoenix.public_checks.switch_manifest import load_suite
from phoenix.public_checks.switch_response import FixedPublicProvider, PublicResponse
from phoenix_eval.pair import BuildReport, PairReport
from phoenix_eval.toolchain import Compiler

_FIXTURE = Path(__file__).resolve().parents[1] / "corpus_public/mechanisms/switch"


def response(source: str | None = None) -> PublicResponse:
    signature = "uint32_t fn_100(uint32_t key, uint32_t value)"
    if source is None:
        arms = "".join(
            f"case {value}u: state = value + {value}u; break;" for value in range(12)
        )
        source = (
            signature
            + "{switch(key & 15u){"
            + arms
            + "default:state = value;}return state;}"
        )
    return PublicResponse(
        "fixed response",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        sha256(source.encode()).hexdigest(),
        source,
        signature,
        (),
    )


def report(count: int = 56) -> PairReport:
    return PairReport(
        count,
        count,
        0,
        0,
        {},
        4,
        4,
        tuple(
            BuildReport(architecture, compiler, True, 0, count, 0, {})
            for architecture in ("amd64", "arm64")
            for compiler in (Compiler.GCC, Compiler.CLANG)
        ),
        True,
    )


def test_public_suite_covers_selectors_and_omits_eleven_from_development() -> None:
    suite = load_suite(_FIXTURE)
    assert len(suite.cases) == 56
    assert sum(case.development for case in suite.cases) == 53
    unseen = [case.invocation for case in suite.cases if not case.development]
    assert {case.args for case in unseen} == {("11",)}
    assert {case.stdin for case in unseen} == {b"\0", b"\xff", b"A"}
    assert {case.invocation.args for case in suite.cases} >= {
        (str(value),) for value in range(16)
    }


@pytest.mark.parametrize("filename", ("main.c", "cases.json"))
def test_public_suite_rejects_changed_commitments(
    tmp_path: Path, filename: str
) -> None:
    directory = tmp_path / "suite"
    shutil.copytree(_FIXTURE, directory)
    path = directory / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="commitment"):
        load_suite(directory)


@pytest.mark.parametrize("mutation", ("duplicate", "missing", "development", "input"))
def test_public_suite_rejects_changed_roster(tmp_path: Path, mutation: str) -> None:
    directory = tmp_path / "suite"
    shutil.copytree(_FIXTURE, directory)
    cases_path = directory / "cases.json"
    document = json.loads(cases_path.read_bytes())
    cases = document["cases"]
    if mutation == "duplicate":
        cases[-1]["id"] = cases[0]["id"]
    elif mutation == "missing":
        cases.pop()
    elif mutation == "development":
        next(case for case in cases if case["args"] == ["11"])["development"] = True
    else:
        cases[0]["stdin_hex"] = "42"
    cases_path.write_text(json.dumps(document))
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["cases_sha256"] = sha256(cases_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="roster|values|omit"):
        load_suite(directory)


def test_source_contract_rejects_disabled_emitter_with_stale_metadata() -> None:
    prepared = response()
    original = ("/* public metadata */\n" + prepared.protected_source).encode()
    switch_gate.check_source(original, prepared)
    altered = switch_gate.disabled_source(original, prepared)
    assert b"public metadata" in altered
    assert b"return 0;" in altered
    with pytest.raises(ValueError, match="protected source"):
        switch_gate.check_source(altered, prepared)


@pytest.mark.parametrize("mutation", ("label", "default", "mask", "duplicate"))
def test_source_contract_requires_actual_complete_switch(mutation: str) -> None:
    source = response().protected_source
    if mutation == "label":
        source = source.replace("case 11u:", "case 12u:")
    elif mutation == "default":
        source = source.replace("default:", "case 12u:")
    elif mutation == "mask":
        source = source.replace("& 15u", "& 31u")
    prepared = response(source)
    project = source.encode() * (2 if mutation == "duplicate" else 1)
    with pytest.raises(ValueError):
        switch_gate.check_source(project, prepared)


def test_fixed_provider_prepares_once_and_reports_standard_software_control() -> None:
    calls = []

    def prepare() -> PublicResponse:
        calls.append(True)
        return response()

    provider = FixedPublicProvider(prepare)
    assert not calls
    assert provider.maximum_usage(Request("cleanup")) == Usage(0, 0, 0)
    first = provider.complete(Request("cleanup"))
    assert provider.complete(Request("same cleanup")) == first
    assert calls == [True]
    assert first.service_tier == "standard"
    assert first.usage == Usage(0, 0, 0)
    assert provider.name == "fixed-public-cleanup"
    with pytest.raises(ValueError, match="Sol request"):
        provider.complete(Request("cleanup", model=Model.ASTRA))


@pytest.mark.parametrize("mutation", ("empty", "partial", "duplicate", "failed"))
def test_positive_gate_requires_all_four_distinct_builds(mutation: str) -> None:
    valid = report()
    assert switch_gate._passed(valid, 56)
    builds = valid.builds
    if mutation == "empty":
        builds = ()
    elif mutation == "partial":
        builds = builds[:3]
    elif mutation == "duplicate":
        builds = builds[:3] + (builds[0],)
    else:
        builds = (replace(builds[0], compiled=False),) + builds[1:]
    assert not switch_gate._passed(replace(valid, builds=builds), 56)


@pytest.mark.parametrize("mutation", ("excluded", "disagreement", "error", "mismatch"))
def test_positive_gate_requires_every_case_without_errors(mutation: str) -> None:
    valid = report()
    if mutation == "excluded":
        invalid = replace(valid, eligible_cases=55)
    elif mutation == "disagreement":
        invalid = replace(valid, emulator_disagreements=1)
    elif mutation == "error":
        invalid = replace(valid, evaluation_errors=1)
    else:
        invalid = replace(
            valid,
            builds=(replace(valid.builds[0], matched_cases=55),) + valid.builds[1:],
        )
    assert not switch_gate._passed(invalid, 56)


def test_linux_lease_guard_runs_before_any_external_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PHOENIX_VM_LEASE", raising=False)

    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("The closed lease reached an external command.")

    monkeypatch.setattr(subprocess, "check_output", forbidden)
    with pytest.raises(ValueError, match="Linux window"):
        switch_gate.run_gate(tmp_path, tmp_path, "public-u2-test")


@pytest.mark.parametrize("identifier", ("../escape", "/absolute", "bad/id", ""))
def test_invalid_run_id_is_rejected_before_external_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identifier: str
) -> None:
    monkeypatch.setenv("PHOENIX_VM_LEASE", "public-u2")

    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("The invalid ID reached an external command.")

    monkeypatch.setattr(subprocess, "check_output", forbidden)
    with pytest.raises(ValueError, match="run ID"):
        switch_gate.run_gate(tmp_path, tmp_path, identifier)
