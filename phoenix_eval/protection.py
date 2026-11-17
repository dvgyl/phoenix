import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

GUARD_ENV = "PHOENIX_PIPELINE_GUARD"
GUARD_PROBE = "pipeline-sandbox-probe"


@dataclass(frozen=True)
class Profile:
    denied: frozenset[str]


PROFILES: dict[str, Profile] = {
    "pipeline": Profile(frozenset({"sealed", "records", "development"})),
    "engineer": Profile(frozenset({"sealed", "records"})),
    "dev-author": Profile(frozenset({"sealed", "records", "prompts"})),
    "corpus-author": Profile(
        frozenset({"records", "prompts", "corpus", "development"})
    ),
    "evaluator": Profile(frozenset()),
}


@dataclass(frozen=True)
class ProtectedPath:
    category: str
    checkout: Path
    path: Path
    pattern: str


def _regex(pattern: str) -> str:
    quoted = pattern.replace('"', r"\x22")
    return f'(regex #"{quoted}")'


def _checkouts(workspace: Path, repo: Path) -> tuple[Path, ...]:
    checkouts = {repo.resolve(), (workspace / "phoenix").resolve()}
    result = subprocess.run(
        ("git", "-C", str(repo), "worktree", "list", "--porcelain", "-z"),
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read the registered worktrees.")
    for field in os.fsdecode(result.stdout).split("\0"):
        if field.startswith("worktree "):
            path = Path(field.removeprefix("worktree ")).resolve()
            if path == workspace / "phoenix" or path.is_relative_to(
                workspace / "worktrees"
            ):
                checkouts.add(path)
    return tuple(sorted(checkouts))


def protected_paths(workspace: Path, repo: Path) -> tuple[ProtectedPath, ...]:
    paths: list[ProtectedPath] = []

    def add(category: str, checkout: Path, relative: str) -> None:
        path = checkout / relative
        pattern = re.escape(str(path)).replace(r"\*", "[^/]*")
        paths.append(ProtectedPath(category, checkout, path, f"^{pattern}(/|$)"))

    names = (
        "sealed",
        "holdout",
        *(
            f"{kind}_{letter}"
            for letter in "bcdefghijklmnopqrstuvwxyz"
            for kind in ("sealed", "holdout")
        ),
    )
    for name in names:
        add("sealed", workspace, name)
    add("records", workspace, "sealed_runs")
    add("records", workspace, "runs/m1-t0-*")
    add("development", workspace, "dev_bin/*/*/*.twin")
    for checkout in _checkouts(workspace, repo):
        for name in ("src", "holdout", "tasks"):
            add("development", checkout, f"corpus_dev/*/{name}")
        add("corpus", checkout, "corpus_dev")
        for relative in (
            "phoenix/analyze",
            "phoenix/devset",
            "phoenix/generate/prompts",
        ):
            add("prompts", checkout, relative)
    return tuple(paths)


def guarded_command(
    workspace: Path,
    repo: Path,
    command: tuple[str, ...],
    profile: str,
    allow: tuple[Path, ...] = (),
) -> tuple[str, ...]:
    if profile not in PROFILES:
        raise ValueError("Unknown protection profile.")
    workspace = workspace.resolve()
    exceptions = []
    for path in allow:
        path = path.resolve()
        relative = path.relative_to(workspace / "sealed_runs")
        if (
            profile != "pipeline"
            or len(relative.parts) < 2
            or not re.fullmatch(r"[a-f0-9]{64}", relative.parts[1])
        ):
            raise ValueError("Allow only the pipeline binary's sealed run directory.")
        exceptions.append(f"(require-not (subpath {json.dumps(str(path))}))")
    policy = "(version 1)(allow default)"
    for item in protected_paths(workspace, repo):
        match = _regex(item.pattern)
        if item.category in PROFILES[profile].denied:
            condition = (
                f"(require-all {match} {''.join(exceptions)})" if exceptions else match
            )
            policy += f"(deny file-read* file-write* {condition})"
        elif item.category == "sealed" and profile == "evaluator":
            policy += f"(deny file-write* {match})"
    if profile == "pipeline":
        pattern = f"^{re.escape(str(workspace))}/(runs|sealed_runs)/.*/{GUARD_PROBE}$"
        policy += f"(deny file-read* file-write* {_regex(pattern)})"
    return "/usr/bin/sandbox-exec", "-p", policy, *command


def inherited_guard(workspace: Path) -> bool:
    location = os.environ.get(GUARD_ENV)
    if not location:
        return False
    probe = Path(location).resolve()
    if probe.name != GUARD_PROBE or not any(
        probe.is_relative_to(workspace / root) for root in ("runs", "sealed_runs")
    ):
        raise ValueError("The inherited file guard has an invalid probe path.")
    try:
        with probe.open("rb"):
            pass
    except PermissionError:
        return True
    except OSError:
        raise ValueError(
            "The inherited file guard has no readable probe status."
        ) from None
    raise ValueError("The inherited file guard did not deny access to its probe.")


def probe(workspace: Path, repo: Path) -> bool:
    passed = True
    script = (
        "import os,sys\n"
        "try:\n fd=os.open(sys.argv[1],os.O_RDONLY)\n"
        "except PermissionError:\n sys.exit(0)\n"
        "except OSError:\n sys.exit(2)\n"
        "else:\n os.close(fd);sys.exit(1)\n"
    )
    for profile, definition in PROFILES.items():
        for item in protected_paths(workspace, repo):
            if item.category not in definition.denied:
                continue
            relative = str(item.path.relative_to(item.checkout))
            candidates = (
                item.checkout.glob(relative) if "*" in relative else (item.path,)
            )
            for path in candidates:
                if not path.exists():
                    continue
                command = guarded_command(
                    workspace, repo, (sys.executable, "-c", script, str(path)), profile
                )
                result = subprocess.run(command, capture_output=True, check=False)
                denied = result.returncode == 0
                print(
                    f"{profile} {item.category} {item.checkout} "
                    f"denied={str(denied).lower()}"
                )
                passed = passed and denied
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("launch",))
    parser.add_argument("profile", choices=tuple(PROFILES))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("Give a command after --.")
    workspace = Path(os.environ["PHOENIX_ROOT"]).resolve()
    repo = Path(__file__).resolve().parents[1]
    if args.profile != "pipeline":
        return subprocess.run(
            guarded_command(workspace, repo, tuple(command), args.profile), check=False
        ).returncode
    with TemporaryDirectory(prefix=".guard-", dir=workspace / "runs") as directory:
        marker = Path(directory) / GUARD_PROBE
        marker.write_text("Synthetic file guard witness.\n")
        return subprocess.run(
            guarded_command(workspace, repo, tuple(command), "pipeline"),
            env={**os.environ, GUARD_ENV: str(marker)},
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
