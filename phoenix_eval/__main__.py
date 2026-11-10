import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from phoenix_eval.docker import WorkerError
from phoenix_eval.m0 import SEED, Mode, evaluate
from phoenix_eval.m1 import evaluate_t0
from phoenix_eval.submission import EvaluationPending


def main() -> int:
    parser = argparse.ArgumentParser(prog="phoenix-eval")
    parser.add_argument("--replay", dest="replay_run", metavar="RUN_ID")
    commands = parser.add_subparsers(dest="command")
    m0 = commands.add_parser("m0", help="Run the public M0 behavior checks.")
    m0.add_argument("--mode", type=Mode, choices=list(Mode), required=True)
    m0.add_argument("--corpus", type=Path, default=Path("corpus_public"))
    m0.add_argument("--runs", type=Path, required=True)
    m0.add_argument("--seed", type=int, default=SEED)
    m1 = commands.add_parser("m1", help="Evaluate the sealed T0 -O0 variants.")
    m1.add_argument("--run-id")
    m1.add_argument("--replay", metavar="RUN_ID")
    args = parser.parse_args()
    if args.command == "m0" and not args.replay_run:
        report, passed = evaluate(args.corpus, args.runs, args.mode, args.seed)
    elif (args.command == "m1" and not args.replay_run) or (
        args.command is None and args.replay_run
    ):
        workspace = os.environ.get("PHOENIX_ROOT")
        if not workspace:
            parser.error("Source the Phoenix workspace environment.")
        run_id = getattr(args, "run_id", None) or f"m1-{uuid4().hex}"
        replay = args.replay_run or getattr(args, "replay", None)
        try:
            report, passed = evaluate_t0(Path(workspace), run_id, replay)
        except EvaluationPending as error:
            print(f"Run {run_id} is pending. {error}", file=sys.stderr)
            return 75
        except (OSError, ValueError, WorkerError, subprocess.SubprocessError) as error:
            print(f"Run {run_id} stopped. {error}", file=sys.stderr)
            return 2
    else:
        parser.error("Select an evaluation command or a run to replay.")
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
