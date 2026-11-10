import json
import os
import platform
from pathlib import Path

GUARD_ENV = "PHOENIX_PIPELINE_GUARD"
GUARD_PROBE = "pipeline-sandbox-probe"


def guarded_command(
    workspace: Path,
    command: tuple[str, ...],
    *,
    release: bool = False,
    probe: Path | None = None,
) -> tuple[str, ...]:
    if platform.system() != "Darwin":
        raise ValueError("The corpus file guard requires macOS.")
    sealed = json.dumps(str(workspace / "sealed"))
    heldout = json.dumps(str(workspace / "holdout"))
    policy = (
        "(version 1)(allow default)"
        f"(deny file-read* file-write* (subpath {heldout}))"
        f"(deny file-write* (subpath {sealed}))"
    )
    if release:
        public = json.dumps(str(workspace / "sealed/release"))
        policy += (
            f"(deny file-read* (require-all (subpath {sealed})"
            f"(require-not (subpath {public}))))"
        )
    else:
        policy += f"(deny file-read* (subpath {sealed}))"
    if probe is not None:
        quoted = json.dumps(str(probe))
        policy += f"(deny file-read* file-write* (literal {quoted}))"
    return "/usr/bin/sandbox-exec", "-p", policy, *command


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
