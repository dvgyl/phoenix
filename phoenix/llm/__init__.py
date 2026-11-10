import os
from pathlib import Path

from phoenix.llm.codex import CodexProvider
from phoenix.llm.provider import Provider
from phoenix.llm.responses import ResponsesProvider


def select_provider(workspace: Path, scratch: Path) -> Provider:
    key = os.environ.get("OPENAI_API_KEY")
    return ResponsesProvider(key) if key else CodexProvider(workspace, scratch)
