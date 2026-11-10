import json
import platform
import subprocess
from pathlib import Path
from typing import cast

from phoenix.llm.provider import Completion, ProviderError, Request, RetryLater, Usage

_CONTEXT_LIMIT = 64_000
_MODEL_OUTPUT_LIMIT = 128_000
_DISABLED_FEATURES = (
    "apps",
    "fast_mode",
    "ultrafast_mode",
    "multi_agent",
    "multi_agent_v2",
    "shell_tool",
    "unified_exec",
)


class CodexProvider:
    name = "codex-exec"

    def __init__(self, workspace: Path, scratch: Path) -> None:
        self.workspace = workspace.resolve()
        self.scratch = scratch.resolve()
        if not self.scratch.is_relative_to(self.workspace):
            raise ValueError(
                "The Codex working directory must be in the Phoenix workspace."
            )
        protected = (self.workspace / "sealed", self.workspace / "holdout")
        if any(self.scratch.is_relative_to(path) for path in protected):
            raise ValueError(
                "The Codex working directory cannot contain protected data."
            )

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(_CONTEXT_LIMIT, 0, _MODEL_OUTPUT_LIMIT)

    def _command(self, request: Request) -> tuple[str, ...]:
        rules = "".join(
            "(deny file-read* file-write* (subpath "
            f"{json.dumps(str(self.workspace / name))}))"
            for name in ("sealed", "holdout")
        )
        features = tuple(
            argument
            for feature in _DISABLED_FEATURES
            for argument in ("--disable", feature)
        )
        return (
            "/usr/bin/sandbox-exec",
            "-p",
            f"(version 1)(allow default){rules}",
            "codex",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--json",
            "--color",
            "never",
            "-m",
            request.model,
            "-c",
            'service_tier="default"',
            "-c",
            'approval_policy="never"',
            "-c",
            'web_search="disabled"',
            "-c",
            f"model_context_window={_CONTEXT_LIMIT}",
            *features,
            "-",
        )

    def complete(self, request: Request) -> Completion:
        if platform.system() != "Darwin":
            raise ProviderError("Live Codex requests require the macOS file sandbox.")
        completed = subprocess.run(
            self._command(request),
            cwd=self.scratch,
            input=request.prompt,
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
        return parse_codex_events(completed.stdout, completed.returncode, request)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProviderError("Codex returned an invalid JSON event.")
    return cast(dict[str, object], value)


def _integer(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if type(value) is not int:
        raise ProviderError(f"Codex did not report an integer {key}.")
    return value


def parse_codex_events(events: str, return_code: int, request: Request) -> Completion:
    text = None
    usage = None
    for line in events.splitlines():
        event = _object(json.loads(line))
        match event.get("type"):
            case "item.completed":
                item = _object(event.get("item"))
                kind = item.get("type")
                if kind == "agent_message" and isinstance(
                    message := item.get("text"), str
                ):
                    text = message
                elif kind in (
                    "command_execution",
                    "file_change",
                    "mcp_tool_call",
                    "web_search",
                    "collab_tool_call",
                ):
                    raise ProviderError(
                        "Codex attempted to use a tool during a reconstruction request."
                    )
            case "turn.completed":
                counts = _object(event.get("usage"))
                usage = Usage(
                    _integer(counts, "input_tokens"),
                    _integer(counts, "cached_input_tokens"),
                    _integer(counts, "output_tokens"),
                )
            case "turn.failed" | "error":
                message = json.dumps(event).lower()
                if any(
                    word in message
                    for word in ("rate limit", "usage limit", "429", "quota")
                ):
                    raise RetryLater("The Codex account reached a usage limit.")
    if return_code or text is None or usage is None:
        raise ProviderError(
            "Codex did not return a completed response with token counts."
        )
    return Completion(text, usage, request.model)
