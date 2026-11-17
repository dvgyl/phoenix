"""Compare repeated source outcomes within one container architecture."""

import base64
import hashlib
import json
import os
import platform
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from check_direct import ROOT, WORK, outcome, run


def digest(result):
    code, stdout, stderr, entries = result
    data = [
        code,
        base64.b64encode(stdout).decode(),
        base64.b64encode(stderr).decode(),
        [
            [
                path,
                mode,
                base64.b64encode(content).decode() if content is not None else None,
            ]
            for path, mode, content in entries
        ],
    ]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def validate(name):
    program = ROOT / name
    build = WORK / f"portable-{name}"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    sources = sorted(
        p for p in (program / "src").glob("*.c") if not p.name.startswith(".")
    )
    cases = [
        json.loads(line)
        for line in (program / "holdout/cases.jsonl").read_text().splitlines()
    ]
    expected = None
    variants = [("gcc", []), ("clang", [])]
    if platform.machine() == "aarch64":
        variants.append(
            ("gcc", ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"])
        )
    for index, (compiler, flags) in enumerate(variants):
        binary = build / f"variant-{index}"
        run(
            [
                compiler,
                "-std=c11",
                "-O2",
                "-ffp-contract=off",
                "-fno-strict-aliasing",
                "-fwrapv",
                "-fsigned-char",
                "-fstack-protector-all",
                "-Wl,-z,relro,-z,now",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                *flags,
                "-o",
                str(binary),
                *map(str, sources),
                "-lm",
            ]
        )
        for repeat in range(3):
            hashes = []
            for case_index, case in enumerate(cases):
                observed = outcome(binary, case, build / "sandbox")
                hashes.append(digest(observed))
                if expected is not None and hashes[-1] != expected[case_index]:
                    raise RuntimeError(
                        f"{name} {compiler} {flags} repeat={repeat} "
                        f"case={case_index}: {observed[:3]!r}"
                    )
            if expected is None:
                expected = hashes
    record = {
        "program": name,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((program / "src").iterdir())
            if not p.name.startswith(".")
        },
        "cases_sha256": hashlib.sha256(
            (program / "holdout/cases.jsonl").read_bytes()
        ).hexdigest(),
        "architecture": platform.machine(),
        "cases": len(cases),
        "repetitions": 3,
        "variants": variants,
        "outcome_hashes": expected,
        "official_acceptance": False,
    }
    print("PORTABLE " + json.dumps(record), flush=True)


if __name__ == "__main__":
    if sys.platform != "linux" or not Path("/.dockerenv").exists():
        raise SystemExit("Run this script inside a Linux compiler container.")
    os.umask(0o022)

    def checked(name):
        try:
            validate(name)
        except (RuntimeError, OSError, ValueError) as error:
            print(
                "PORTABLE_ERROR " + json.dumps({"program": name, "error": str(error)}),
                flush=True,
            )
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(checked, sys.argv[1:]))
    if not all(results):
        raise SystemExit(1)
