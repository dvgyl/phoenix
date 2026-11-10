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
            "programs": [{"program": "probe", "cases": 1, "outcome_sha256": "result"}],
        }
        (folder / "m0.json").write_text(json.dumps(report))
        paths.append(folder)
    assert compare_public_reports(paths)["runs"] == {
        "native-amd64": "run-native-amd64",
        "native-arm64": "run-native-arm64",
        "apple-silicon": "run-apple-silicon",
    }
    report["programs"] = [{"program": "probe", "cases": 2, "outcome_sha256": "result"}]
    (paths[-1] / "m0.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="case counts"):
        compare_public_reports(paths)
