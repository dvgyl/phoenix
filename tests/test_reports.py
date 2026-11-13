import json
from pathlib import Path

import pytest

from phoenix_eval.reports import compare_public_reports


def test_compare_checks_native_and_emulated_outcome_evidence(tmp_path: Path) -> None:
    paths = []
    for mode in ("native-amd64", "native-arm64", "apple-silicon"):
        folder = tmp_path / mode
        folder.mkdir()
        report = {
            "mode": mode,
            "run_id": f"run-{mode}",
            "seed": 42,
            "evaluator": {"commit": "same", "worker_source_sha256": "same"},
            "behavior_checks_passed": True,
            "programs": [
                {
                    "program": "probe",
                    "cases": 1,
                    "outcome_sha256": "result",
                    "self_match": True,
                }
            ],
        }
        (folder / "m0.json").write_text(json.dumps(report))
        paths.append(folder)
    assert compare_public_reports(paths)["runs"] == {
        "native-amd64": "run-native-amd64",
        "native-arm64": "run-native-arm64",
        "apple-silicon": "run-apple-silicon",
    }
    report["programs"] = [
        {
            "program": "probe",
            "cases": 2,
            "outcome_sha256": "result",
            "self_match": True,
        }
    ]
    (paths[-1] / "m0.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="case counts"):
        compare_public_reports(paths)


@pytest.mark.parametrize("mode", ["native-amd64", "native-arm64", "apple-silicon"])
@pytest.mark.parametrize("value", [False, None, 0, 1, 1.0, "true", [], {}])
def test_compare_refuses_nonpassing_program_self_match(
    tmp_path: Path, mode: str, value: object
) -> None:
    paths = []
    for current in ("native-amd64", "native-arm64", "apple-silicon"):
        program = {
            "program": "probe",
            "cases": 1,
            "outcome_sha256": "result",
            "self_match": value if current == mode else True,
        }
        report = {
            "mode": current,
            "run_id": f"run-{current}",
            "seed": 42,
            "evaluator": {"commit": "same", "worker_source_sha256": "same"},
            "behavior_checks_passed": True,
            "programs": [program],
        }
        path = tmp_path / f"{current}.json"
        path.write_text(json.dumps(report))
        paths.append(path)
    with pytest.raises(ValueError, match="self-match"):
        compare_public_reports(paths)


@pytest.mark.parametrize("mode", ["native-amd64", "native-arm64", "apple-silicon"])
def test_compare_refuses_missing_program_self_match(tmp_path: Path, mode: str) -> None:
    paths = []
    for current in ("native-amd64", "native-arm64", "apple-silicon"):
        program = {
            "program": "probe",
            "cases": 1,
            "outcome_sha256": "result",
            "self_match": True,
        }
        if current == mode:
            del program["self_match"]
        report = {
            "mode": current,
            "run_id": f"run-{current}",
            "seed": 42,
            "evaluator": {"commit": "same", "worker_source_sha256": "same"},
            "behavior_checks_passed": True,
            "programs": [program],
        }
        path = tmp_path / f"{current}.json"
        path.write_text(json.dumps(report))
        paths.append(path)
    with pytest.raises(ValueError, match="self-match"):
        compare_public_reports(paths)
