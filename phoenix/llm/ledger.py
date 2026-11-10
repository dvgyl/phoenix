import fcntl
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO
from uuid import uuid4

from phoenix.llm.provider import (
    Completion,
    Model,
    Provider,
    ProviderError,
    Request,
    RetryLater,
    Usage,
    cost_nanodollars,
)

NANODOLLARS = 1_000_000_000


@dataclass(frozen=True)
class Budget:
    per_binary: int = 5 * NANODOLLARS
    per_run: int = 200 * NANODOLLARS

    def __post_init__(self) -> None:
        if not 0 < self.per_binary <= self.per_run:
            raise ValueError("The model budgets must be positive and ordered.")


class BudgetExceeded(ProviderError):
    pass


class ReplayMissing(ProviderError):
    pass


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    calls: int
    usage: Usage
    cost_nanodollars: int
    unknown_cost_reservations: int


def _append(stream: TextIO, event: dict[str, object]) -> None:
    stream.seek(0, os.SEEK_END)
    stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _cached_completion(event: dict[str, Any]) -> Completion:
    try:
        body = event["request"]
        request = Request(
            body["prompt"], Model(body["model"]), body["max_output_tokens"]
        )
        if (
            not isinstance(body["prompt"], str)
            or type(body["max_output_tokens"]) is not int
        ):
            raise ValueError
        result = event["completion"]
        counts = result["usage"]
        if set(counts) != {"input_tokens", "cached_input_tokens", "output_tokens"}:
            raise ValueError
        if any(type(value) is not int for value in counts.values()):
            raise ValueError
        usage = Usage(**counts)
        expected_key = hashlib.sha256(
            json.dumps(
                (event["binary"], event["provider"], asdict(request)), sort_keys=True
            ).encode("ascii")
        ).hexdigest()
        if (
            not isinstance(event["binary"], str)
            or not isinstance(event["provider"], str)
            or body != asdict(request)
            or event["key"] != expected_key
            or event["service_tier"] != "standard"
            or result["model"] != request.model
            or result["service_tier"] != "standard"
            or not isinstance(result["text"], str)
            or type(event["cost_nanodollars"]) is not int
            or event["cost_nanodollars"] != cost_nanodollars(request.model, usage)
        ):
            raise ValueError
        return Completion(result["text"], usage, result["model"], "standard")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProviderError(
            "The cached model completion is malformed or inconsistent."
        ) from None


class Ledger:
    def __init__(self, run_directory: Path, budget: Budget = Budget()) -> None:
        self.path = run_directory / "llm.jsonl"
        self.budget = budget

    def summary(self, binary: str) -> LedgerSummary:
        if not self.path.is_file():
            return LedgerSummary(0, Usage(0, 0, 0), 0, 0)
        latest = {}
        with self.path.open(encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            for line in stream:
                event = json.loads(line)
                if event["binary"] == binary:
                    latest[event["attempt"]] = event
        measured = [event for event in latest.values() if "completion" in event]
        usage = Usage(
            sum(event["completion"]["usage"]["input_tokens"] for event in measured),
            sum(
                event["completion"]["usage"]["cached_input_tokens"]
                for event in measured
            ),
            sum(event["completion"]["usage"]["output_tokens"] for event in measured),
        )
        return LedgerSummary(
            calls=len(measured),
            usage=usage,
            cost_nanodollars=sum(event["cost_nanodollars"] for event in measured),
            unknown_cost_reservations=sum(
                event["cost_nanodollars"]
                for event in latest.values()
                if "completion" not in event
            ),
        )

    def call(
        self,
        binary: str,
        request: Request,
        provider: Provider,
        *,
        replay: bool = False,
    ) -> Completion:
        body = asdict(request)
        key = hashlib.sha256(
            json.dumps((binary, provider.name, body), sort_keys=True).encode("ascii")
        ).hexdigest()
        if replay and not self.path.is_file():
            raise ReplayMissing("The run has no recorded model responses.")
        if not replay:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_RDONLY if replay else os.O_RDWR | os.O_CREAT
        descriptor = os.open(self.path, flags | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "r" if replay else "r+", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH if replay else fcntl.LOCK_EX)
            latest: dict[str, dict[str, Any]] = {}
            cached = None
            try:
                for line in stream:
                    event = json.loads(line)
                    previous = latest.get(event["attempt"])
                    if event["state"] == "completed":
                        result = _cached_completion(event)
                        if previous is not None and any(
                            previous[name] != event[name]
                            for name in (
                                "key",
                                "binary",
                                "provider",
                                "service_tier",
                                "request",
                            )
                        ):
                            raise ValueError
                        if event["key"] == key:
                            cached = result
                    latest[event["attempt"]] = event
            except (KeyError, TypeError, ValueError):
                raise ProviderError(
                    "The cached model ledger is malformed or inconsistent."
                ) from None
            if cached is not None:
                return cached
            if replay:
                raise ReplayMissing(
                    "The run has no recorded response for this request."
                )
            used = sum(event["cost_nanodollars"] for event in latest.values())
            binary_used = sum(
                event["cost_nanodollars"]
                for event in latest.values()
                if event["binary"] == binary
            )
            reserved = cost_nanodollars(request.model, provider.maximum_usage(request))
            if (
                used + reserved > self.budget.per_run
                or binary_used + reserved > self.budget.per_binary
            ):
                raise BudgetExceeded(
                    "The request would exceed the remaining model budget."
                )

            attempt: dict[str, object] = {
                "attempt": uuid4().hex,
                "key": key,
                "binary": binary,
                "provider": provider.name,
                "service_tier": "standard",
                "request": body,
                "cost_nanodollars": reserved,
                "state": "started",
            }
            _append(stream, attempt)
            started = time.monotonic()
            try:
                completion = provider.complete(request)
            except RetryLater as error:
                _append(
                    stream,
                    {
                        **attempt,
                        "state": "retry",
                        "cost_nanodollars": reserved if error.cost_unknown else 0,
                        "error": type(error).__name__,
                    },
                )
                raise
            except Exception as error:
                _append(
                    stream,
                    {**attempt, "state": "failed", "error": type(error).__name__},
                )
                raise
            cost = cost_nanodollars(request.model, completion.usage)
            status = "completed" if cost <= reserved else "limit-exceeded"
            _append(
                stream,
                {
                    **attempt,
                    "state": status,
                    "cost_nanodollars": cost,
                    "completion": asdict(completion),
                    "seconds": time.monotonic() - started,
                },
            )
            if status == "limit-exceeded":
                raise BudgetExceeded(
                    "The model response exceeded its token reservation."
                )
            return completion
