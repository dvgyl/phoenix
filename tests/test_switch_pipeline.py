import json
from hashlib import sha256
from pathlib import Path
from time import time
from unittest.mock import Mock

import pytest
from test_protected_switch import protected as protected

from phoenix import pipeline
from phoenix.analyze import Analysis, DevelopmentCase
from phoenix.generate.protected_switch import ProtectedDefinition
from phoenix.generate.switch_plan import SwitchPlan
from phoenix.ingest import BinaryMetadata
from phoenix.llm.ledger import Ledger
from phoenix.llm.provider import Completion, Model, Usage
from phoenix.recover import Program
from phoenix.verify import BUILD_CONFIGURATIONS, Check, Verification
from phoenix.verify.integrity import IntegrityInputs
from phoenix_eval.build import BuildResult, ProjectSnapshot, snapshot_project
from phoenix_eval.case import Invocation
from phoenix_eval.integrity import IntegrityReport
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot


def test_reconstruction_keeps_protected_cases_through_repair_and_replay(
    protected: tuple[Program, ProtectedDefinition],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program, checked = protected
    binary = tmp_path / "original.elf"
    binary.write_bytes(b"Synthetic input for the orchestration control.")
    metadata = BinaryMetadata(sha256(binary.read_bytes()).hexdigest(), 0, ())
    expected = Outcome(b"", b"", Exited(1), TreeSnapshot())
    analysis = Analysis((DevelopmentCase(Invocation(), expected),), 0, 0, 1, 0, 0)
    plan = SwitchPlan(metadata.sha256, "synthetic", (checked,), ())
    selected = Mock(return_value=(tmp_path / "generation", Mock(lift=b"synthetic")))
    monkeypatch.setattr(pipeline, "_analyze", lambda *_: analysis)
    monkeypatch.setattr(pipeline, "recover_bytes", lambda *_: program)
    monkeypatch.setattr(pipeline, "read_selected_generation", selected)
    monkeypatch.setattr(pipeline, "plan_switches", lambda *_: plan)

    def lift(_binary: Path, export: Path, *_a: object, **_k: object) -> None:
        export.parent.mkdir(parents=True, exist_ok=True)
        (export.parent / "evidence-current").write_text("Synthetic selection.")

    lifting = Mock(side_effect=lift)
    monkeypatch.setattr(pipeline, "lift_binary", lifting)
    monkeypatch.setattr(pipeline, "reached_functions", lambda *_: frozenset())
    monkeypatch.setattr(pipeline, "feedback", lambda *_: "Revise the ordinary main.")
    monkeypatch.setattr(
        IntegrityInputs, "check", lambda *_: IntegrityReport(True, {}, 0, 4, (), (), ())
    )
    tested = []

    def verification(
        snapshot: ProjectSnapshot, build_dir: Path, *_: object
    ) -> Verification:
        source = dict(snapshot.files)["src/program.c"]
        assert source.count(checked.source.encode()) == 1
        assert b"case 0u:case 1u:result = 11;" in source
        tested.append(snapshot)
        passed = b"return 1;" in source
        actual = expected if passed else Outcome(b"", b"", Exited(0), TreeSnapshot())
        build_dir.mkdir(parents=True, exist_ok=True)
        executable = build_dir / "synthetic.elf"
        executable.write_bytes(b"Synthetic executable evidence. Never execute.")
        return Verification(
            tuple(
                Check(
                    BuildResult(engine, compiler, executable, 0, ""),
                    (actual,),
                    ((),) if passed else (("termination",),),
                    executable.read_bytes(),
                )
                for engine, compiler in BUILD_CONFIGURATIONS
            ),
            1,
        )

    monkeypatch.setattr(pipeline, "_verify", verification)
    usage = Usage(1, 0, 1)
    provider = Mock()
    provider.name = "synthetic"
    provider.maximum_usage.return_value = usage
    provider.complete.side_effect = [
        Completion(
            json.dumps(
                {
                    "declarations": "",
                    "functions": {
                        hex(program.main): {
                            "signature": "int main(void)",
                            "body": f"return {value};",
                            "evidence": "The orchestration test supplies main.",
                        }
                    },
                }
            ),
            usage,
            Model.SOL,
        )
        for value in (0, 1)
    ]
    settings = pipeline.Settings(
        {}, 0, tmp_path, tmp_path, 1, False, {}, checked_switches=True
    )
    run = tmp_path / "run"
    ledger = Ledger(run)
    args = ("public", binary, metadata, settings, ledger, provider)
    first = pipeline.reconstruct(run, *args, started=time())
    report = json.loads((first.project / "phoenix_report.json").read_bytes())
    assert first.development_passed and len(tested) == 2
    assert snapshot_project(first.project) == tested[-1]
    assert report["checked_switches"] == json.loads(json.dumps(plan.record()))
    assert report["project_sha256"] == sha256(tested[-1].archive).hexdigest()
    assert provider.complete.call_count == 2
    for name, replay in (("run", False), ("replay", True)):
        result = pipeline.reconstruct(
            tmp_path / name, *args, started=time(), replay=replay
        )
        assert result.development_passed
        assert snapshot_project(result.project) == tested[1]
        assert provider.complete.call_count == 2
    assert lifting.call_count == 2


def test_checked_switches_cannot_change_the_raw_baseline(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Phoenix method"):
        pipeline.Settings(
            {},
            0,
            tmp_path,
            tmp_path,
            0,
            False,
            {},
            method=pipeline.Method.GHIDRA_RAW,
            checked_switches=True,
        )
