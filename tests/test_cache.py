import json
import multiprocessing
import shutil
import sys
from dataclasses import asdict, replace
from hashlib import sha256
from multiprocessing.connection import Connection
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix import checkpoints, pipeline
from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.cache import (
    CacheError,
    StageCache,
    StageIdentity,
    identity_hash,
    stage_versions,
)
from phoenix.ingest import BinaryMetadata
from phoenix.llm.cache import CachedProvider
from phoenix.llm.codex import CodexProvider
from phoenix.llm.ledger import Ledger, ReplayMissing
from phoenix.llm.provider import Completion, ProviderError, Request, Usage
from phoenix.pipeline_types import Reconstruction, Settings
from phoenix.recover import Function, Program
from phoenix.verify import BUILD_CONFIGURATIONS, Check, Verification
from phoenix.verify.integrity import IntegrityInputs
from phoenix_eval.build import BuildResult, ProjectSnapshot
from phoenix_eval.case import Invocation
from phoenix_eval.integrity import IntegrityReport
from phoenix_eval.model_ledger import TokenUsage, parse_event
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.trace import CodeTrace


@pytest.fixture
def stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Settings, Mock, Mock, Analysis]:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setenv("PHOENIX_JOBS", "2")
    binary = tmp_path / "input.elf"
    binary.write_bytes(b"Synthetic binary bytes.")
    outcome = Outcome(b"hello\n", b"", Exited(0), TreeSnapshot(), CodeTrace(0, 1, (0,)))
    analysis = Analysis((DevelopmentCase(Invocation(), outcome),), 1, 1, 1, 0, 0)
    lift = Mock(
        side_effect=lambda _binary, output, *_: output.write_bytes(b'{"lift":1}\n')
    )
    analyze = Mock(return_value=analysis)
    monkeypatch.setattr(checkpoints, "lift_binary", lift)
    monkeypatch.setattr(checkpoints, "analyze", analyze)
    settings = Settings(
        {"amd64": "pinned-image"},
        17,
        tmp_path,
        tmp_path,
        0,
        False,
        {},
        cache_root=tmp_path / "cache/phoenix",
        stage_versions=stage_versions(
            "source", {"ghidra": "pin"}, {"amd64": "pinned-image"}
        ),
    )
    return binary, settings, lift, analyze, analysis


def test_warm_stages_avoid_lift_and_analysis(
    tmp_path: Path, stages: tuple[Path, Settings, Mock, Mock, Analysis]
) -> None:
    binary, settings, lift, analyze, analysis = stages
    digest = sha256(binary.read_bytes()).hexdigest()
    export, result = checkpoints.prepare_stages(
        binary, digest, tmp_path / "cold", settings
    )
    lift_bytes = export.read_bytes()
    cases = (tmp_path / "cold/analyze/cases.json").read_bytes()
    export, result = checkpoints.prepare_stages(
        binary, digest, tmp_path / "warm", settings
    )
    assert result == analysis
    assert export.read_bytes() == lift_bytes
    assert (tmp_path / "warm/analyze/cases.json").read_bytes() == cases
    assert lift.call_count == analyze.call_count == 1


def test_replay_packages_identical_bytes_from_recorded_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stages: tuple[Path, Settings, Mock, Mock, Analysis],
) -> None:
    binary, settings, lift, analyze, analysis = stages
    program = Program(
        0,
        0,
        0,
        0,
        (Function(0, "main", "main", ((0, 1),), "return 0;", "int main(void)"),),
        (),
        (),
    )
    monkeypatch.setattr(pipeline, "recover", lambda *_: program)
    monkeypatch.setattr(pipeline, "reached_functions", lambda *_: frozenset({0}))
    monkeypatch.setattr(
        IntegrityInputs,
        "check",
        lambda *_: IntegrityReport(True, {}, 0, 4, (), (), ()),
    )

    def verify(project: ProjectSnapshot, destination: Path, *_: object) -> Verification:
        destination.mkdir(parents=True, exist_ok=True)
        checks = []
        for engine, compiler in BUILD_CONFIGURATIONS:
            executable = destination / f"{engine.value}-{compiler}.elf"
            executable.write_bytes(b"Synthetic build bytes.")
            checks.append(
                Check(
                    BuildResult(engine, compiler, executable, 0, ""),
                    (analysis.cases[0].expected,),
                    ((),),
                    executable.read_bytes(),
                )
            )
        return Verification(tuple(checks), 1)

    monkeypatch.setattr(checkpoints, "verify_project", verify)
    provider = _provider()
    provider.complete.side_effect = lambda request: Completion(
        json.dumps(
            {
                "declarations": "",
                "functions": {
                    "0x0": {
                        "signature": "int main(void)",
                        "body": "return 0;",
                        "evidence": "Synthetic fixture.",
                    }
                },
            }
        ),
        Usage(5, 2, 3),
        request.model,
    )
    assert settings.cache_root is not None
    metadata = BinaryMetadata(sha256(binary.read_bytes()).hexdigest(), 0, ())
    cached = CachedProvider(
        provider, settings.cache_root, "version", binary_sha256=metadata.sha256
    )
    ledger = Ledger(tmp_path / "original")
    original = pipeline.reconstruct(
        tmp_path / "original",
        "key",
        binary,
        metadata,
        settings,
        ledger,
        cached,
        started=123.0,
    )
    expected = {
        path.relative_to(original.project): path.read_bytes()
        for path in original.project.rglob("*")
        if path.is_file()
    }
    shutil.rmtree(settings.cache_root)
    ledger_bytes = ledger.path.read_bytes()
    replay = pipeline.reconstruct(
        tmp_path / "replay",
        "key",
        binary,
        metadata,
        settings,
        ledger,
        cached,
        started=456.0,
        replay=True,
    )
    assert {
        path.relative_to(replay.project): path.read_bytes()
        for path in replay.project.rglob("*")
        if path.is_file()
    } == expected
    assert provider.complete.call_count == lift.call_count == analyze.call_count == 1
    assert ledger.path.read_bytes() == ledger_bytes
    assert not (tmp_path / "replay/llm.jsonl").exists()
    evidence = json.loads((tmp_path / "replay/key/recover/evidence.json").read_bytes())
    assert evidence["binary_sha256"] == metadata.sha256


@pytest.mark.parametrize(
    "change", ["binary", "lift-version", "devset-version", "seed", "cold-root"]
)
def test_stage_evidence_is_bound_to_inputs(
    tmp_path: Path,
    stages: tuple[Path, Settings, Mock, Mock, Analysis],
    change: str,
) -> None:
    binary, settings, lift, analyze, _ = stages
    digest = sha256(binary.read_bytes()).hexdigest()
    checkpoints.prepare_stages(binary, digest, tmp_path / "a", settings)
    if change == "binary":
        binary.write_bytes(b"Different binary bytes.")
        digest = sha256(binary.read_bytes()).hexdigest()
    elif change == "seed":
        settings = replace(settings, seed=18)
    elif change == "cold-root":
        settings = replace(settings, cache_root=tmp_path / "empty-cache")
    else:
        assert settings.stage_versions is not None
        name = change.removesuffix("-version")
        settings = replace(
            settings, stage_versions={**settings.stage_versions, name: "f" * 64}
        )
    checkpoints.prepare_stages(binary, digest, tmp_path / "b", settings)
    assert lift.call_count == (1 if change in ("seed", "devset-version") else 2)
    assert analyze.call_count == (1 if change == "lift-version" else 2)


@pytest.mark.parametrize("stage", ["lift", "devset"])
@pytest.mark.parametrize("change", ["artifact", "manifest", "missing", "identity"])
def test_corrupt_stage_entries_fail_without_rebuilding(
    tmp_path: Path,
    stages: tuple[Path, Settings, Mock, Mock, Analysis],
    stage: str,
    change: str,
) -> None:
    binary, settings, lift, analyze, _ = stages
    digest = sha256(binary.read_bytes()).hexdigest()
    checkpoints.prepare_stages(binary, digest, tmp_path / "a", settings)
    assert settings.cache_root is not None
    manifest = next((settings.cache_root / stage).rglob("stage.json"))
    artifact = manifest.parent / ("lift.json" if stage == "lift" else "cases.json")
    if change == "artifact":
        artifact.write_bytes(b"corrupt")
    elif change == "missing":
        artifact.unlink()
    elif change == "identity":
        record = json.loads(manifest.read_bytes())
        record["identity"]["binary_sha256"] = "0" * 64
        manifest.write_text(json.dumps(record))
    else:
        manifest.write_bytes(b"invalid JSON")
    with pytest.raises(CacheError, match="corrupt or mismatched"):
        checkpoints.prepare_stages(binary, digest, tmp_path / "b", settings)
    assert lift.call_count == analyze.call_count == 1


def test_changed_input_is_rejected_before_stage_use(
    tmp_path: Path, stages: tuple[Path, Settings, Mock, Mock, Analysis]
) -> None:
    binary, settings, lift, analyze, _ = stages
    with pytest.raises(ValueError, match="SHA-256 has changed"):
        checkpoints.prepare_stages(binary, "0" * 64, tmp_path / "a", settings)
    lift.assert_not_called()
    analyze.assert_not_called()


def test_stage_publication_recovers_after_producer_failure(tmp_path: Path) -> None:
    cache = StageCache(tmp_path / "cache")
    identity = StageIdentity("a" * 64, "b" * 64)
    destination = tmp_path / "run/lift.json"

    def fail(output: Path) -> None:
        output.write_bytes(b"partial")
        raise RuntimeError("Synthetic interruption.")

    with pytest.raises(RuntimeError):
        cache.materialize("lift", identity, destination, fail)
    assert not destination.exists()
    cache.materialize(
        "lift", identity, destination, lambda output: output.write_bytes(b"complete")
    )
    assert destination.read_bytes() == b"complete"


def test_stage_versions_bind_source_tools_and_images() -> None:
    versions = stage_versions("source", {"ghidra": "v1"}, {"amd64": "image-v1"})
    source = stage_versions("changed", {"ghidra": "v1"}, {"amd64": "image-v1"})
    tools = stage_versions("source", {"ghidra": "v2"}, {"amd64": "image-v1"})
    images = stage_versions("source", {"ghidra": "v1"}, {"amd64": "image-v2"})
    assert source["lift"] != versions["lift"]
    assert source["devset"] != versions["devset"]
    assert tools["lift"] != versions["lift"]
    assert tools["devset"] == versions["devset"]
    assert images["devset"] != versions["devset"]
    assert images["lift"] == versions["lift"]


def _shared_cache_worker(root: str, number: int, pipe: Connection) -> None:
    path = Path(root)
    provider = _provider()

    def complete(request: Request) -> Completion:
        with (path / "calls").open("a") as calls:
            calls.write("live\n")
        return Completion("answer", Usage(5, 2, 3), request.model)

    provider.complete.side_effect = complete
    cached = CachedProvider(provider, path / "cache", "version", binary_sha256="a" * 64)
    assert pipe.recv() == "start"
    ledger = Ledger(path / f"run-{number}")
    ledger.call("key", Request("prompt"), cached)
    pipe.send(ledger.summary("key").cost_nanodollars)
    pipe.close()


def test_processes_publish_one_shared_response(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    workers = []
    for number in range(3):
        parent, child = context.Pipe()
        process = context.Process(
            target=_shared_cache_worker, args=(str(tmp_path), number, child)
        )
        process.start()
        child.close()
        workers.append((process, parent))
    try:
        for _, pipe in workers:
            pipe.send("start")
        assert sorted(pipe.recv() for _, pipe in workers) == [0, 0, 36_200]
        assert (tmp_path / "calls").read_text().splitlines() == ["live"]
    finally:
        for process, pipe in workers:
            pipe.close()
            process.join(timeout=30)
            if process.is_alive():
                process.kill()
                process.join()
            assert process.exitcode == 0


def _provider() -> Mock:
    provider = Mock()
    provider.name = "synthetic-provider"
    provider.maximum_usage.return_value = Usage(10, 0, 10)
    provider.complete.side_effect = lambda request: Completion(
        "answer", Usage(5, 2, 3), request.model
    )
    return provider


def test_response_cache_isolates_binaries_with_identical_requests(
    tmp_path: Path,
) -> None:
    from phoenix.generate import request_candidate

    program = Program(
        0,
        0,
        0,
        0,
        (Function(0, "main", "main", ((0, 1),), "return 0;", "int main(void)"),),
        (),
        (),
    )
    changed = replace(
        program, functions=(replace(program.functions[0], ranges=((0, 2),)),)
    )
    request = request_candidate(program)
    assert request_candidate(changed) == request
    provider = _provider()
    for number, digest in enumerate(("a" * 64, "b" * 64)):
        cached = CachedProvider(provider, tmp_path, "version", binary_sha256=digest)
        ledger = Ledger(tmp_path / f"cold-{number}")
        result = ledger.call("key", request, cached)
        assert result.cache_hit is False
        assert ledger.summary("key").cost_nanodollars == 36_200
    assert provider.complete.call_count == 2
    manifests = [
        json.loads(path.read_bytes()) for path in (tmp_path / "llm").rglob("stage.json")
    ]
    assert {record["identity"]["binary_sha256"] for record in manifests} == {
        "a" * 64,
        "b" * 64,
    }
    for number, digest in enumerate(("a" * 64, "b" * 64)):
        cached = CachedProvider(provider, tmp_path, "version", binary_sha256=digest)
        ledger = Ledger(tmp_path / f"warm-{number}")
        ledger.call("key", request, cached)
        assert ledger.summary("key").cost_nanodollars == 0
    assert provider.complete.call_count == 2


@pytest.mark.parametrize("mode", ["live", "resume", "replay"])
def test_response_hit_metadata_survives_ledger(tmp_path: Path, mode: str) -> None:
    provider = _provider()
    cached = CachedProvider(
        provider, tmp_path / "cache", "version", binary_sha256="a" * 64
    )
    request = Request("Synthetic prompt.")
    Ledger(tmp_path / "cold").call("key", request, cached)
    warm = Ledger(tmp_path / "warm")
    result = warm.call("key", request, cached)
    recorded = warm.path.read_bytes()
    completion = json.loads(recorded.splitlines()[-1])["completion"]
    expected = Completion(
        "answer",
        Usage(0, 0, 0),
        request.model,
        cache_hit=True,
        cache_key=completion["cache_key"],
        original_usage=Usage(5, 2, 3),
    )
    shutil.rmtree(tmp_path / "cache")
    if mode != "live":
        result = Ledger(tmp_path / "warm").call(
            "key", request, cached, replay=mode == "replay"
        )
    assert result == expected
    event = parse_event(json.loads(recorded.splitlines()[-1]))
    assert event.cache_hit is True
    assert event.cache_key == expected.cache_key
    assert event.original_usage == TokenUsage(5, 2, 3)
    assert warm.path.read_bytes() == recorded
    assert not (tmp_path / "cache").exists()
    assert provider.complete.call_count == provider.maximum_usage.call_count == 1


@pytest.mark.parametrize("replay", [False, True])
def test_ledger_keeps_completions_without_cache_metadata(
    tmp_path: Path, replay: bool
) -> None:
    provider = _provider()
    ledger = Ledger(tmp_path)
    request = Request("Synthetic old completion.")
    expected = ledger.call("key", request, provider)
    records = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    for name in ("cache_hit", "cache_key", "original_usage"):
        del records[-1]["completion"][name]
    ledger.path.write_text("".join(json.dumps(record) + "\n" for record in records))
    recorded = ledger.path.read_bytes()
    assert ledger.call("key", request, provider, replay=replay) == expected
    assert expected.cache_hit is False
    assert expected.cache_key is None
    assert expected.original_usage is None
    assert ledger.path.read_bytes() == recorded
    assert provider.complete.call_count == 1


def test_response_hit_records_zero_new_usage_and_cost(tmp_path: Path) -> None:
    provider = _provider()
    cached = CachedProvider(
        provider, tmp_path / "cache", "pipeline-version", binary_sha256="a" * 64
    )
    request = Request("Synthetic prompt.")
    original = Ledger(tmp_path / "original")
    original.call("a", request, cached)
    warm = Ledger(tmp_path / "warm")
    warm.call("b", request, cached)
    assert provider.complete.call_count == 1
    assert provider.maximum_usage.call_count == 1
    assert original.summary("a").cost_nanodollars == 36_200
    assert warm.summary("b").cost_nanodollars == 0
    assert warm.summary("b").usage == Usage(0, 0, 0)
    start, completed = [json.loads(line) for line in warm.path.read_text().splitlines()]
    assert start["cost_nanodollars"] == 0
    assert completed["completion"]["cache_hit"] is True
    assert completed["completion"]["original_usage"] == asdict(Usage(5, 2, 3))
    assert completed["request"]["effort"] == "medium"
    recorded = warm.path.read_bytes()
    shutil.rmtree(tmp_path / "cache")
    assert warm.call("b", request, cached, replay=True).text == "answer"
    assert warm.path.read_bytes() == recorded
    assert provider.complete.call_count == 1
    with pytest.raises(ReplayMissing):
        warm.call("b", replace(request, effort="high"), cached, replay=True)


@pytest.mark.parametrize(
    "change",
    [
        "prompt",
        "effort",
        "schema",
        "model",
        "max_output_tokens",
        "provider",
        "pipeline",
    ],
)
def test_response_keys_bind_complete_identity(tmp_path: Path, change: str) -> None:
    provider = _provider()
    request = Request("Synthetic prompt.")
    cached = CachedProvider(provider, tmp_path, "version", binary_sha256="a" * 64)
    Ledger(tmp_path / "a").call("a", request, cached)
    changed = {
        "prompt": replace(request, prompt="Different prompt."),
        "effort": replace(request, effort="high"),
        "schema": replace(request, schema="v2"),
        "model": replace(request, model="gpt-6-astra"),
        "max_output_tokens": replace(request, max_output_tokens=128),
    }
    if change == "provider":
        provider.name = "different-provider"
    cached = CachedProvider(
        provider,
        tmp_path,
        "different" if change == "pipeline" else "version",
        binary_sha256="a" * 64,
    )
    if change in changed:
        request = changed[change]
    Ledger(tmp_path / "b").call("b", request, cached)
    assert provider.complete.call_count == 2


def test_response_cache_off_bypasses_existing_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider()
    cached = CachedProvider(provider, tmp_path, "version", binary_sha256="a" * 64)
    request = Request("Synthetic prompt.")
    Ledger(tmp_path / "a").call("a", request, cached)
    monkeypatch.setenv("PHOENIX_LLM_CACHE", "off")
    ledger = Ledger(tmp_path / "b")
    ledger.call("b", request, cached)
    assert provider.complete.call_count == 2
    assert ledger.summary("b").cost_nanodollars == 36_200


def test_response_requires_preparation(tmp_path: Path) -> None:
    provider = _provider()
    cached = CachedProvider(provider, tmp_path, "version", binary_sha256="a" * 64)
    with pytest.raises(ProviderError, match="reservation"):
        cached.complete(Request("prompt"))
    provider.complete.assert_not_called()


@pytest.mark.parametrize(
    "change", ["usage", "original_usage", "cache_key", "cache_hit"]
)
def test_ledger_validates_cache_hit_metadata(tmp_path: Path, change: str) -> None:
    cached = CachedProvider(
        _provider(), tmp_path / "cache", "version", binary_sha256="a" * 64
    )
    request = Request("prompt")
    Ledger(tmp_path / "cold").call("a", request, cached)
    warm = Ledger(tmp_path / "warm")
    warm.call("a", request, cached)
    record = json.loads(warm.path.read_text().splitlines()[-1])
    changed = {
        "usage": asdict(Usage(1, 0, 0)),
        "original_usage": {
            "input_tokens": -1,
            "cached_input_tokens": 0,
            "output_tokens": 0,
        },
        "cache_key": "invalid",
        "cache_hit": False,
    }
    record["completion"][change] = changed[change]
    with pytest.raises(ValueError, match="malformed or inconsistent"):
        parse_event(record)


@pytest.mark.parametrize("change", ["missing", "corrupt", "changed"])
def test_prepared_response_never_falls_back_to_unreserved_live_call(
    tmp_path: Path, change: str
) -> None:
    provider = _provider()
    cached = CachedProvider(provider, tmp_path, "version", binary_sha256="a" * 64)
    request = Request("Synthetic prompt.")
    Ledger(tmp_path / "a").call("a", request, cached)
    assert cached.maximum_usage(request) == Usage(0, 0, 0)
    directory = next(
        path.parent for path in (tmp_path / "llm").rglob("completion.json")
    )
    if change == "missing":
        shutil.rmtree(directory)
    else:
        artifact = directory / "completion.json"
        data = json.loads(artifact.read_bytes())
        data["text"] = "changed"
        artifact.write_text(json.dumps(data))
        if change == "changed":
            manifest = json.loads((directory / "stage.json").read_bytes())
            manifest["sha256"] = sha256(artifact.read_bytes()).hexdigest()
            (directory / "stage.json").write_text(json.dumps(manifest))
    with pytest.raises(ProviderError, match="cache entry"):
        cached.complete(request)
    assert provider.complete.call_count == 1


def test_codex_command_has_explicit_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("phoenix.llm.codex.inherited_guard", lambda _: True)
    command = CodexProvider(tmp_path, tmp_path)._command(
        Request("prompt", effort="high")
    )
    assert 'model_reasoning_effort="high"' in command
    assert 'service_tier="default"' in command


def test_ledger_parser_keeps_old_request_keys_and_validates_new_effort(
    tmp_path: Path,
) -> None:
    provider = _provider()
    ledger = Ledger(tmp_path)
    ledger.call("a", Request("prompt"), provider)
    record = json.loads(ledger.path.read_text().splitlines()[-1])
    for name in ("effort", "schema"):
        del record["request"][name]
    record["key"] = identity_hash(("a", provider.name, record["request"]))
    assert parse_event(record).text == "answer"
    record["request"].update({"effort": "invalid", "schema": "v1"})
    record["key"] = identity_hash(("a", provider.name, record["request"]))
    with pytest.raises(ValueError, match="malformed or inconsistent"):
        parse_event(record)


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_records_cache_root_and_requires_it_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    explicit: bool,
) -> None:
    from test_provenance import write_project, write_tools

    from phoenix import __main__ as cli
    from phoenix_eval.provenance import BuildEvidence

    checkout = tmp_path / "checkout"
    write_project(checkout)
    ghidra, java = write_tools(tmp_path / "tools")
    binary = tmp_path / "input.elf"
    binary.write_bytes(b"Synthetic binary.")
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
    monkeypatch.setattr(cli, "_PIPELINE_ROOT", checkout)
    monkeypatch.setattr(cli, "pinned_lifting_tools", lambda *_: (ghidra, java))
    monkeypatch.setattr(
        cli, "evaluator_build", lambda _: BuildEvidence("revision", "worker-source")
    )
    monkeypatch.setattr(cli, "checker_source_digest", lambda _: "checker-source")
    monkeypatch.setattr(cli, "verify_runtime", Mock())
    monkeypatch.setattr(
        cli, "freeze_images", lambda _, digest, **_kw: {"amd64": digest}
    )
    monkeypatch.setattr(
        cli,
        "inspect_binary",
        lambda path: BinaryMetadata(sha256(path.read_bytes()).hexdigest(), 0, ()),
    )
    selected = _provider()
    select = Mock(return_value=selected)
    monkeypatch.setattr(cli, "select_provider", select)
    reconstruct = Mock(return_value=Reconstruction(tmp_path / "out", True))
    monkeypatch.setattr(cli, "reconstruct", reconstruct)
    cache_root = tmp_path / ("empty-cache" if explicit else "cache/phoenix")
    options = ["--cache-root", str(cache_root)] if explicit else []
    monkeypatch.setattr(
        sys, "argv", ["phoenix", "run", str(binary), "--run-id", "recorded", *options]
    )
    assert cli.main() == 0
    path = tmp_path / "runs/recorded/input/run.json"
    original = path.read_bytes()
    record = json.loads(original)
    assert record["cache_root"] == str(cache_root)
    assert set(record["stage_versions"]) == {"lift", "devset"}
    assert select.call_args.kwargs["binary_sha256"] == record["binary_sha256"]
    assert select.call_args.kwargs["cache_root"] == cache_root
    assert reconstruct.call_args.args[4].cache_root == cache_root
    monkeypatch.setattr(sys, "argv", ["phoenix", "run", "--resume", "recorded"])
    assert cli.main() == 0
    assert path.read_bytes() == original
    monkeypatch.setattr(
        sys, "argv", ["phoenix", "run", "--replay", "recorded", "--run-id", "replayed"]
    )
    assert cli.main() == 0
    replay = json.loads((tmp_path / "runs/replayed/input/run.json").read_bytes())
    assert replay["cache_root"] == record["cache_root"]
    assert replay["stage_versions"] == record["stage_versions"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "phoenix",
            "run",
            "--resume",
            "recorded",
            "--cache-root",
            str(tmp_path / "changed"),
        ],
    )
    assert cli.main() == 2
    assert path.read_bytes() == original
