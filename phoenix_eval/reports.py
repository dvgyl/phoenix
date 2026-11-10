import argparse
import json
from pathlib import Path


def compare_public_reports(paths: list[Path]) -> dict[str, object]:
    fingerprints = []
    runs = {}
    for path in paths:
        if path.is_dir():
            files = list(path.rglob("m0.json"))
            if len(files) != 1:
                raise ValueError(f"Expected one public report in {path}.")
            path = files[0]
        report = json.loads(path.read_text(encoding="utf-8"))
        if report["behavior_checks_passed"] is not True or report["mode"] in runs:
            raise ValueError(
                f"The public report failed or repeats an execution mode. {path}"
            )
        programs = {
            item["program"]: [item["cases"], item["outcome_sha256"]]
            for item in report["programs"]
        }
        if not programs or len(programs) != len(report["programs"]):
            raise ValueError(
                f"The public report has missing or duplicate programs. {path}"
            )
        runs[report["mode"]] = report["run_id"]
        fingerprints.append((report["evaluator"], report["seed"], programs))

    modes = {"native-amd64", "native-arm64"}
    if set(runs) not in (modes, modes | {"apple-silicon"}):
        raise ValueError("The comparison requires both native modes.")
    evaluator, seed, programs = fingerprints[0]
    if any(other != fingerprints[0] for other in fingerprints[1:]):
        raise ValueError(
            "The reports differ in revision, seed, case counts, or outcomes."
        )
    return {"evaluator": evaluator, "seed": seed, "runs": runs, "programs": programs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare public M0 reports.")
    parser.add_argument("reports", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps(compare_public_reports(args.reports), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
