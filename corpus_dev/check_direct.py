"""Run direct container checks. This does not replace Phoenix acceptance."""

import base64
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"


def run(command, **kwargs):
    result = subprocess.run(command, check=False, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Command failed: {command!r}\n{result.stderr!r}")
    return result


def outcome(binary, case, sandbox):
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)
    for entry in case["tree"]["entries"]:
        path = sandbox / entry["path"]
        if entry["kind"] == "directory":
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(entry["data"]))
        path.chmod(entry["mode"])
    sandbox.chmod(case["tree"]["mode"])
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        **case["environment"],
    }
    result = subprocess.run(
        [str(binary), *case["args"]],
        input=base64.b64decode(case["stdin"]),
        capture_output=True,
        cwd=sandbox,
        env=env,
        timeout=5,
        check=False,
    )
    tree = []
    for path in sorted(sandbox.rglob("*")):
        tree.append(
            (
                str(path.relative_to(sandbox)),
                path.stat().st_mode & 0o777,
                path.read_bytes() if path.is_file() else None,
            )
        )
    return result.returncode, result.stdout, result.stderr, tree


def check(name):
    program = ROOT / name
    build = WORK / name
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    sources = sorted(
        p for p in (program / "src").glob("*.c") if not p.name.startswith(".")
    )
    binary = build / "coverage"
    run(
        [
            "gcc",
            "-std=c11",
            "-O0",
            "--coverage",
            "-Wall",
            "-Wextra",
            "-o",
            str(binary),
            *map(str, sources),
            "-lm",
        ]
    )
    cases = [
        json.loads(line)
        for line in (program / "holdout/cases.jsonl").read_text().splitlines()
    ]
    repetitions = int(os.environ.get("DIRECT_REPEATS", "3"))
    originals = []
    for case in cases:
        originals.append(outcome(binary, case, build / "sandbox"))
    gcno = sorted(build.glob("*.gcno"))
    run(["gcov", "-b", "-c", "--json-format", *map(str, gcno)], cwd=build)
    taken = 0
    total = 0
    uncovered = []
    for path in build.glob("*.gcov.json.gz"):
        data = json.loads(gzip.decompress(path.read_bytes()))
        for source in data["files"]:
            for line in source["lines"]:
                for branch in line.get("branches", []):
                    total += 1
                    taken += branch["count"] > 0
                    if branch["count"] == 0:
                        uncovered.append([source["file"], line["line_number"]])

    def validate_variant(pair):
        compiler, level = pair
        variant = build / f"{compiler}{level}"
        run(
            [compiler, "-std=c11", level, "-o", str(variant), *map(str, sources), "-lm"]
        )
        for repeat in range(repetitions):
            for index, case in enumerate(cases):
                observed = outcome(variant, case, build / f"sandbox-{compiler}{level}")
                if observed != originals[index]:
                    raise RuntimeError(
                        f"{name} {compiler} {level} repeat={repeat} "
                        f"case={index}: outcome differs"
                    )
        return f"{compiler} {level}"

    pairs = [
        (cc, level) for cc in ["gcc", "clang"] for level in ["-O0", "-O2", "-Os", "-O3"]
    ]
    if os.environ.get("DIRECT_COVERAGE_ONLY") == "1":
        pairs = []
    with ThreadPoolExecutor(
        max_workers=int(os.environ.get("DIRECT_JOBS", "4"))
    ) as pool:
        variants = list(pool.map(validate_variant, pairs))
    report = {
        "program": name,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((program / "src").iterdir())
            if not p.name.startswith(".")
        },
        "cases_sha256": hashlib.sha256(
            (program / "holdout/cases.jsonl").read_bytes()
        ).hexdigest(),
        "status": "direct checks only; Phoenix acceptance pending",
        "cases": len(cases),
        "branch_covered": taken,
        "branch_total": total,
        "branch_percent": 100 * taken / total if total else 100,
        "uncovered": uncovered,
        "variants": variants,
        "repetitions": repetitions if pairs else 0,
        "compiler_image": "phoenix-worker:amd64",
        "gcc": run(["gcc", "-dumpfullversion"]).stdout.decode().strip(),
        "clang": run(["clang", "--version"]).stdout.decode().splitlines()[0],
        "mutation_score": None,
        "arm64_validation": False,
        "runner_validation": False,
    }
    (program / "direct-check.json").write_text(json.dumps(report, indent=2) + "\n")
    print("REPORT " + json.dumps(report), flush=True)
    print(
        f"{name}: cases={len(cases)} branches={taken}/{total} "
        f"({report['branch_percent']:.2f}%)",
        flush=True,
    )

    if total and 100 * taken / total < 90:
        raise RuntimeError(f"{name}: branch coverage is below 90 percent")


if __name__ == "__main__":
    if (
        sys.platform != "linux"
        or platform.machine() != "x86_64"
        or not Path("/.dockerenv").exists()
    ):
        raise SystemExit("Run this script inside the Linux x86-64 compiler container.")
    os.umask(0o022)
    for name in sys.argv[1:]:
        check(name)
