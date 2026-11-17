"""Create the velocalc cases with seed 852002."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from generate_cases import generate  # noqa: E402

if __name__ == "__main__":
    generate("velocalc", 852002)
