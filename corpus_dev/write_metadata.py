"""Record source counts and declared corpus features."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
D0 = {
    "niblace": "encoder",
    "weighbit": "checksum",
    "runepack": "encoder",
    "pairfold": "checksum",
    "driftstat": "statistics",
    "spanrank": "statistics",
    "wordweft": "encoder",
    "tilehash": "checksum",
    "gapmeter": "statistics",
    "tokenlace": "encoder",
}
D1 = {
    "knotconf": (
        "configuration transformer",
        "structs switch_8 recursion getopt directory_tree static_locals qsort",
    ),
    "prismcsv": (
        "CSV transformer",
        "structs function_pointer_tables switch_8 getopt floating_point_output",
    ),
    "velocalc": (
        "calculator",
        "structs function_pointer_tables switch_8 recursion getopt "
        "floating_point_output static_locals",
    ),
    "lumaquilt": (
        "image filter",
        "structs function_pointer_tables switch_8 recursion getopt "
        "floating_point_output directory_tree static_locals qsort",
    ),
    "branchmark": (
        "directory configuration transformer",
        "structs function_pointer_tables switch_8 recursion getopt "
        "floating_point_output directory_tree static_locals qsort",
    ),
    "skeinwire": ("codec", "structs switch_8 getopt"),
    "patchpanel": (
        "CSV calculator",
        "structs switch_8 getopt floating_point_output qsort",
    ),
    "tariffgrid": ("calculator", "structs getopt qsort"),
    "fernconf": (
        "configuration transformer",
        "structs switch_8 recursion getopt floating_point_output directory_tree",
    ),
    "unitforge": (
        "calculator",
        "structs function_pointer_tables switch_8 getopt "
        "floating_point_output static_locals qsort",
    ),
    "chromapath": (
        "image filter",
        "structs function_pointer_tables getopt "
        "floating_point_output static_locals qsort",
    ),
    "recordloom": (
        "record codec",
        "structs function_pointer_tables switch_8 getopt "
        "floating_point_output directory_tree static_locals qsort",
    ),
}


def main():
    for name in sorted(D0.keys() | D1.keys()):
        program = ROOT / name
        files = sorted(str(p.relative_to(program)) for p in (program / "src").iterdir())
        lines = sum(
            sum(
                bool(line.strip()) for line in (program / path).read_text().splitlines()
            )
            for path in files
        )
        category = D0[name] if name in D0 else D1[name][0]
        features = [] if name in D0 else D1[name][1].split()
        seed = int(
            re.search(
                r'generate\("[a-z]+", (\d+)\)', (program / "holdout/gen.py").read_text()
            )[1]
        )
        count = len((program / "holdout/cases.jsonl").read_text().splitlines())
        metadata = {
            "name": name,
            "tier": "D0" if name in D0 else "D1",
            "lines": lines,
            "files": files,
            "category": category,
            "features": features,
            "heldout_cases": count,
            "heldout_seed": seed,
        }
        (program / "meta.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
