import fcntl
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from phoenix.llm.provider import (
    Completion,
    Provider,
    ProviderError,
    Request,
    RetryLater,
    Usage,
)
from phoenix_eval.model_ledger import (
    ModelEvent,
    TokenUsage,
    completion_charge,
    parse_event,
    read_events,
    summarize,
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


def _completion(event: ModelEvent) -> Completion:
    assert event.usage is not None and event.text is not None
    return Completion(
        event.text, Usage(**asdict(event.usage)), str(event.request["model"])
    )


def _read_events(stream: TextIO) -> tuple[ModelEvent, ...]:
    try:
        return read_events(stream)
    except ValueError as error:
        raise ProviderError(str(error)) from None


class Ledger:
    def __init__(self, run_directory: Path, budget: Budget = Budget()) -> None:
        self.path = run_directory / "llm.jsonl"
        self.budget = budget

    def summary(self, binary: str) -> LedgerSummary:
        if not self.path.is_file():
            return LedgerSummary(0, Usage(0, 0, 0), 0, 0)
        with self.path.open(encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            summary = summarize(_read_events(stream), binary)
        return LedgerSummary(
            summary.calls,
            Usage(**asdict(summary.usage)),
            summary.cost_nanodollars,
            summary.unknown_cost_reservations,
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
            events = _read_events(stream)
            for event in events:
                if event.state == "completed" and event.key == key:
                    return _completion(event)
            if replay:
                raise ReplayMissing(
                    "The run has no recorded response for this request."
                )
            used = sum(event.cost_nanodollars for event in events)
            binary_used = sum(
                event.cost_nanodollars for event in events if event.binary == binary
            )
            reserved = completion_charge(
                request.model, TokenUsage(**asdict(provider.maximum_usage(request)))
            )
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
            try:
                parse_event(attempt)
            except ValueError as error:
                raise ProviderError(str(error)) from None
            _append(stream, attempt)
            started = time.monotonic()
            try:
                completion = provider.complete(request)
                try:
                    cost = completion_charge(
                        request.model, TokenUsage(**asdict(completion.usage))
                    )
                    terminal = {
                        **attempt,
                        "state": "completed" if cost <= reserved else "limit-exceeded",
                        "cost_nanodollars": cost,
                        "completion": asdict(completion),
                        "seconds": time.monotonic() - started,
                    }
                    validated = parse_event(terminal)
                except (ValueError, TypeError, AttributeError, KeyError):
                    raise ProviderError(
                        "The model completion is malformed or inconsistent."
                    ) from None
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
            _append(stream, terminal)
            if validated.state == "limit-exceeded":
                raise BudgetExceeded(
                    "The model response exceeded its token reservation."
                )
            return _completion(validated)
