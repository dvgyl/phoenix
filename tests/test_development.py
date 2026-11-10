import json
from pathlib import Path

import pytest

from phoenix_eval import development
from phoenix_eval.case import Invocation
from phoenix_eval.docker import Engine
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot
from phoenix_eval.wire import encode_invocation, encode_result


@pytest.mark.parametrize("changed", [False, True])
def test_frozen_development_results_require_independent_oracle_agreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: bool
) -> None:
    case = Invocation(("public",), b"example")
    original = Outcome(b"actual stdout", b"actual stderr", Exited(2), TreeSnapshot())
    recorded = (
        Outcome(b"changed", b"", Exited(0), TreeSnapshot()) if changed else original
    )
    source = tmp_path / "recorded.json"
    snapshot = tmp_path / "frozen.json"
    source.write_text(
        json.dumps({"cases": [(encode_invocation(case), encode_result(recorded))]})
    )
    digest = development.freeze_development(source, snapshot)
    source.write_text("The original pipeline record changed.")
    engines = []

    def oracle(
        binary: Path, cases: tuple[Invocation, ...], engine: Engine, *, image: str
    ) -> tuple[Outcome, ...]:
        assert binary == tmp_path / "original.elf"
        assert cases == (case,)
        assert image == engine.platform
        engines.append(engine)
        return (original,)

    monkeypatch.setattr(development, "run_cases", oracle)
    images = {"amd64": "amd64", "arm64": "arm64"}
    if changed:
        with pytest.raises(development.DevelopmentError, match="reproduce"):
            development.verify_development(
                tmp_path / "original.elf", snapshot, digest, images
            )
    else:
        result = development.verify_development(
            tmp_path / "original.elf", snapshot, digest, images
        )
        assert result == frozenset({original.stdout, original.stderr})
        assert engines == [Engine.ROSETTA, Engine.QEMU_X86_64]
    snapshot.write_text("The frozen record changed.")
    with pytest.raises(development.DevelopmentError, match="has changed"):
        development.verify_development(
            tmp_path / "original.elf", snapshot, digest, images
        )


def test_refuses_a_saved_outcome_without_a_valid_invocation(tmp_path: Path) -> None:
    path = tmp_path / "recorded.json"
    outcome = Outcome(b"untrusted", b"", Exited(0), TreeSnapshot())
    path.write_text(
        json.dumps({"cases": [("invalid invocation", encode_result(outcome))]})
    )
    with pytest.raises(development.DevelopmentError, match="evidence is invalid"):
        development.freeze_development(path, tmp_path / "frozen.json")
