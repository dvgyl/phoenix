"""Create the lumaquilt cases with seed 852003."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from generate_cases import generate  # noqa: E402

if __name__ == "__main__":
    generate("lumaquilt", 852003)
