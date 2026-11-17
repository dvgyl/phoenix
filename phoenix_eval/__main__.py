import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from phoenix_eval.docker import WorkerError
from phoenix_eval.m0 import SEED, Mode
from phoenix_eval.protection import probe


def main() -> int:
    parser = argparse.ArgumentParser(prog="phoenix-eval")
    parser.add_argument("--replay", dest="replay_run", metavar="RUN_ID")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("probe", help="Check the protection profiles.")
    m0 = commands.add_parser("m0", help="Run the public M0 behavior checks.")
    m0.add_argument("--mode", type=Mode, choices=list(Mode), required=True)
    m0.add_argument("--corpus", type=Path, default=Path("corpus_public"))
    m0.add_argument("--runs", type=Path, required=True)
    m0.add_argument("--seed", type=int, default=SEED)
    run = commands.add_parser("run", help="Evaluate accepted development binaries.")
    run.add_argument("--corpus", choices=("corpus_dev",), default="corpus_dev")
    run.add_argument("--tier", default="D0,D1")
    run.add_argument("--opt", default="O0,O2,Os")
    run.add_argument("--quick", action="store_true")
    run.add_argument("--probe", action="store_true")
    run.add_argument("--llm-cache", choices=("on", "off"), default="on")
    run.add_argument("--run-id")
    run.add_argument("--resume", metavar="RUN_ID")
    args = parser.parse_args()
    if args.command == "m0" and not args.replay_run:
        from phoenix_eval.m0 import evaluate as evaluate_m0

        report, passed = evaluate_m0(args.corpus, args.runs, args.mode, args.seed)
        print(report)
        return 0 if passed else 1
    if args.command not in ("probe", "run") and not (
        args.command is None and args.replay_run
    ):
        parser.error("Select an evaluation command or a run to replay.")
    workspace = Path(os.environ["PHOENIX_ROOT"]).resolve()
    if args.command == "probe":
        return 0 if probe(workspace, Path(__file__).resolve().parents[1]) else 1
    from phoenix_eval.run import evaluate
    from phoenix_eval.run_records import RunPlan, Selection, directory

    run_id = (
        getattr(args, "resume", None)
        or getattr(args, "run_id", None)
        or f"dev-{uuid4().hex}"
    )
    try:
        selection = Selection()
        if args.command == "run":
            selection = Selection(
                args.corpus,
                tuple(args.tier.split(",")),
                tuple(args.opt.split(",")),
                args.quick,
                args.probe,
            )
        if getattr(args, "resume", None):
            selection = RunPlan.load(
                directory(workspace, run_id) / "plan.json"
            ).selection
        document = evaluate(
            workspace,
            run_id,
            selection,
            getattr(args, "llm_cache", "on") == "on",
            resume=bool(getattr(args, "resume", None)),
            replay_id=args.replay_run,
            metadata={"loop": "replay" if args.replay_run else "probe"},
        )
    except (OSError, ValueError, WorkerError, subprocess.SubprocessError) as error:
        print(f"Run {run_id} stopped. {error}", file=sys.stderr)
        return 2
    print(workspace / "runs" / run_id / "scoreboard.json")
    if document.get("reproduced") is False:
        return 1
    return 0 if document["run_state"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
