import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from phoenix_eval.provenance import revision

GUARD_ENV = "PHOENIX_PIPELINE_GUARD"
GUARD_PROBE = "pipeline-sandbox-probe"
REVISION_ENV = "PHOENIX_PIPELINE_REVISION"
MODEL_FD_ENV = "PHOENIX_MODEL_FD"
MODEL_PROVIDER_ENV = "PHOENIX_MODEL_PROVIDER"
REPLAY_ENV = "PHOENIX_PIPELINE_REPLAY"


@dataclass(frozen=True)
class Profile:
    denied: frozenset[str]


PROFILES: dict[str, Profile] = {
    "pipeline": Profile(
        frozenset(
            {
                "sealed",
                "records",
                "development",
                "corpus",
                "git",
                "runs",
                "binaries",
                "llm-cache",
                "stage-cache",
            }
        )
    ),
    "engineer": Profile(frozenset({"sealed", "records"})),
    "dev-author": Profile(frozenset({"sealed", "records", "prompts", "runs"})),
    "corpus-author": Profile(
        frozenset({"records", "prompts", "corpus", "development", "runs"})
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
    add("records", workspace, "sealed_work")
    add("records", workspace, "runs/m1-t0-*")
    add("prompts", workspace, "cache/phoenix")
    add("llm-cache", workspace, "cache/phoenix/llm")
    for stage in ("lift", "devset"):
        add("stage-cache", workspace, f"cache/phoenix/{stage}")
    add("runs", workspace, "runs")
    add("binaries", workspace, "dev_bin")
    add("development", workspace, "dev_bin/*/*/*.twin")
    add("development", workspace, "adequacy_runs")
    for checkout in _checkouts(workspace, repo):
        for name in ("src", "holdout", "tasks"):
            add("development", checkout, f"corpus_dev/*/{name}")
        add("corpus", checkout, "corpus_dev")
        add("git", checkout, ".git")
        for relative in (
            "phoenix/analyze",
            "phoenix/devset",
            "phoenix/generate/prompts",
        ):
            add("prompts", checkout, relative)
    git = ("git", "-C", str(repo), "rev-parse", "--path-format=absolute")
    common = subprocess.check_output((*git, "--git-common-dir"), text=True).rstrip("\n")
    git_directory = Path(common).resolve(strict=True)
    if git_directory not in {path.path for path in paths if path.category == "git"}:
        add("git", repo, str(git_directory))
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
    exceptions: dict[str, list[str]] = {"runs": [], "stage-cache": []}
    metadata: set[Path] = set()
    runs = workspace / "runs"
    cache = workspace / "cache/phoenix"
    for path in allow:
        if (
            profile != "pipeline"
            or path.resolve() != path
            or not path.is_relative_to(workspace)
        ):
            raise ValueError("Use a physical path in the pipeline workspace.")
        parts = path.relative_to(workspace).parts
        if len(parts) >= 3 and parts[0] == "runs" and not parts[1].startswith("m1-t0-"):
            category = "runs"
        elif path.parent in (cache / "lift", cache / "devset") and re.fullmatch(
            r"[a-f0-9]{64}", path.name
        ):
            category = "stage-cache"
        else:
            raise ValueError("Allow only paths of the current pipeline run.")
        exceptions[category].append(f"(require-not (subpath {json.dumps(str(path))}))")
        metadata.update(
            parent
            for parent in path.parents
            if parent.is_relative_to(runs) or parent.parent == cache
        )
    policy = "(version 1)(allow default)"
    read_only = "sealed" if profile == "evaluator" else "binaries"
    for item in protected_paths(workspace, repo):
        match = _regex(item.pattern)
        if item.category in PROFILES[profile].denied:
            allowed = exceptions.get(item.category)
            condition = (
                f"(require-all {match} {''.join(allowed)})" if allowed else match
            )
            policy += f"(deny file-read* file-write* {condition})"
        elif item.category == read_only:
            policy += f"(deny file-write* {match})"
    if profile == "pipeline":
        for parent in sorted(metadata):
            policy += f"(allow file-read-metadata (literal {json.dumps(str(parent))}))"
        pattern = f"^{re.escape(str(runs))}/.*/{GUARD_PROBE}$"
        policy += f"(deny file-read* file-write* {_regex(pattern)})"
        replay = _regex(rf"^{re.escape(str(runs))}/[^/]+/[^/]+/\.replay-[^/]+(/|$)")
        policy += f"(deny file-write* {replay})"
    environment = ("/usr/bin/env", f"{REVISION_ENV}={revision(repo)}") if allow else ()
    return "/usr/bin/sandbox-exec", "-p", policy, *environment, *command


def inherited_guard(workspace: Path) -> bool:
    location = os.environ.get(GUARD_ENV)
    if not location:
        return False
    probe = Path(location).resolve()
    if probe.name != GUARD_PROBE or not probe.is_relative_to(workspace / "runs"):
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
    paths = protected_paths(workspace, repo)
    for profile, definition in PROFILES.items():
        command = guarded_command(
            workspace, repo, (sys.executable, "-c", script), profile
        )
        for item in paths:
            if item.category not in definition.denied:
                continue
            candidates = (
                item.checkout.glob(str(item.path.relative_to(item.checkout)))
                if "*" in str(item.path)
                else (item.path,)
            )
            for path in candidates:
                if not path.exists():
                    continue
                result = subprocess.run(
                    (*command, str(path)), capture_output=True, check=False
                )
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
