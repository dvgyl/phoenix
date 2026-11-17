import os
from pathlib import Path

from phoenix.cache import default_root
from phoenix.llm.cache import CachedProvider
from phoenix.llm.codex import CodexProvider
from phoenix.llm.provider import Provider
from phoenix.llm.responses import ResponsesProvider
from phoenix_eval.provenance import pipeline_source_digest


def select_provider(
    workspace: Path,
    scratch: Path,
    *,
    binary_sha256: str,
    cache_root: Path | None = None,
    pipeline_version: str | None = None,
) -> Provider:
    key = os.environ.get("OPENAI_API_KEY")
    provider = ResponsesProvider(key) if key else CodexProvider(workspace, scratch)
    return CachedProvider(
        provider,
        cache_root if cache_root is not None else default_root(),
        pipeline_version if pipeline_version is not None else pipeline_source_digest(),
        binary_sha256=binary_sha256,
    )
