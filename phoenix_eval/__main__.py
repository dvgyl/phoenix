import argparse
from pathlib import Path

from phoenix_eval.m0 import SEED, Mode, evaluate


def main() -> int:
    parser = argparse.ArgumentParser(prog="phoenix-eval")
    commands = parser.add_subparsers(required=True)
    m0 = commands.add_parser("m0", help="Run the public M0 behavior checks.")
    m0.add_argument("--mode", type=Mode, choices=list(Mode), required=True)
    m0.add_argument("--corpus", type=Path, default=Path("corpus_public"))
    m0.add_argument("--runs", type=Path, required=True)
    m0.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    report, passed = evaluate(args.corpus, args.runs, args.mode, args.seed)
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
