import json
import os
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from phoenix.cache import CacheError, identity_hash, publish_entry, read_entry
from phoenix.jobs import file_lock
from phoenix.llm.provider import (
    Completion,
    Provider,
    ProviderError,
    Request,
    Usage,
    cost_nanodollars,
)


class CachedProvider:
    def __init__(
        self, provider: Provider, root: Path, version: str, *, binary_sha256: str
    ) -> None:
        self.provider = provider
        self.name = provider.name
        self.root = root.resolve() / "llm"
        self.version = version
        self.binary_sha256 = binary_sha256
        self._prepared: dict[str, str | None] = {}

    def _identity(self, request: Request) -> dict[str, object]:
        return {
            "binary_sha256": self.binary_sha256,
            "request": asdict(request),
            "provider": self.name,
            "pipeline_version": self.version,
            "service_tier": "standard",
        }

    def _read(self, request: Request) -> tuple[Completion, str] | None:
        identity = self._identity(request)
        key = identity_hash(identity)
        directory = self.root / key
        if not directory.exists():
            return None
        try:
            data = read_entry(directory, "completion.json", identity)
            record = json.loads(data)
            usage = Usage(**record["usage"])
            original = Completion(
                record["text"], usage, record["model"], record["service_tier"]
            )
            if (
                original.model != request.model
                or not isinstance(original.text, str)
                or record.get("cache_hit") is not False
                or record != asdict(original)
            ):
                raise ValueError
            cost_nanodollars(original.model, usage)
            return Completion(
                original.text,
                Usage(0, 0, 0),
                original.model,
                cache_hit=True,
                cache_key=key,
                original_usage=usage,
            ), sha256(data).hexdigest()
        except (
            CacheError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
            RecursionError,
        ):
            raise ProviderError(
                f"The response cache entry is corrupt at {directory}."
            ) from None

    def maximum_usage(self, request: Request) -> Usage:
        key = identity_hash(self._identity(request))
        if os.environ.get("PHOENIX_LLM_CACHE") == "off":
            usage = self.provider.maximum_usage(request)
            self._prepared[key] = "off"
            return usage
        with file_lock(self.root / f"{key}.lock"):
            hit = self._read(request)
        usage = (
            Usage(0, 0, 0) if hit is not None else self.provider.maximum_usage(request)
        )
        self._prepared[key] = hit[1] if hit is not None else None
        return usage

    def complete(self, request: Request) -> Completion:
        identity = self._identity(request)
        key = identity_hash(identity)
        if key not in self._prepared:
            raise ProviderError("The response cache request has no token reservation.")
        prepared = self._prepared.pop(key)
        if prepared == "off":
            return self.provider.complete(request)
        with file_lock(self.root / f"{key}.lock"):
            hit = self._read(request)
            if prepared is not None and (hit is None or hit[1] != prepared):
                raise ProviderError(
                    "The prepared response cache entry changed or is missing."
                )
            if hit is not None:
                return hit[0]
            completion = self.provider.complete(request)
            if (
                completion.model != request.model
                or not isinstance(completion.text, str)
                or completion.cache_hit
                or completion.cache_key is not None
                or completion.original_usage is not None
            ):
                raise ProviderError("The model returned an inconsistent completion.")
            cost_nanodollars(completion.model, completion.usage)
            publish_entry(
                self.root / key,
                "completion.json",
                identity,
                json.dumps(asdict(completion), sort_keys=True).encode("utf-8"),
            )
            return completion
