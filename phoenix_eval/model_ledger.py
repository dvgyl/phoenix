import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from phoenix_eval.submission import write_report


class LedgerIdentity(TypedDict):
    schema: int
    pipeline_run: str
    sha256: str | None


def _open_ledger(path: Path) -> int | None:
    try:
        physical = path.resolve() == path
    except (OSError, RuntimeError):
        physical = False
    if not physical:
        raise ValueError("The model ledger path is invalid or contains symbolic links.")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ValueError("Cannot open the model ledger.") from error
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("The model ledger must be a regular file.")
    return descriptor


def ledger_digest(path: Path) -> str | None:
    descriptor = _open_ledger(path)
    if descriptor is None:
        return None
    with os.fdopen(descriptor, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_identity(path: Path) -> LedgerIdentity:
    try:
        descriptor = _open_ledger(path)
        if descriptor is None:
            raise ValueError
        with os.fdopen(descriptor, "rb") as stream:
            content = stream.read(4097)
            if len(content) > 4096:
                raise ValueError
            data = json.loads(content)
        if (
            not isinstance(data, dict)
            or set(data) != {"schema", "pipeline_run", "sha256"}
            or type(data["schema"]) is not int
            or data["schema"] != 1
            or not isinstance(data["pipeline_run"], str)
            or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,71}", data["pipeline_run"]
            )
            or (
                data["sha256"] is not None
                and (
                    not isinstance(data["sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
                )
            )
        ):
            raise ValueError
        return cast(LedgerIdentity, data)
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValueError(
            "The model ledger identity record is invalid or missing."
        ) from None


def verify_identity(workspace: Path, identity: LedgerIdentity) -> None:
    path = workspace / "runs" / identity["pipeline_run"] / "llm.jsonl"
    if ledger_digest(path) != identity["sha256"]:
        raise ValueError("The model ledger changed after submission.")


def freeze_identity(
    workspace: Path,
    run: Path,
    pipeline_run: str,
    *,
    expected: LedgerIdentity | None = None,
) -> LedgerIdentity:
    identity = LedgerIdentity(
        schema=1,
        pipeline_run=pipeline_run,
        sha256=ledger_digest(workspace / "runs" / pipeline_run / "llm.jsonl"),
    )
    if expected is not None and identity != expected:
        raise ValueError("The original model ledger changed before replay freeze.")
    record = run / "model-ledger.json"
    if record.exists() or record.is_symlink():
        if read_identity(record) != identity:
            raise ValueError("The model ledger changed after submission.")
    else:
        write_report(record, identity)
    return identity


def require_no_replay_ledger(workspace: Path, pipeline_run: str) -> None:
    directory = workspace / "runs" / pipeline_run
    try:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return
    except OSError as error:
        raise ValueError("The replay model ledger directory is invalid.") from error
    try:
        os.stat("llm.jsonl", dir_fd=descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    finally:
        os.close(descriptor)
    raise ValueError("Replay must not create a fresh model ledger.")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ModelSummary:
    calls: int
    usage: TokenUsage
    cost_nanodollars: int
    unknown_cost_reservations: int


@dataclass(frozen=True)
class ModelEvent:
    attempt: str
    key: str
    binary: str
    provider: str
    request: dict[str, object]
    state: str
    cost_nanodollars: int
    usage: TokenUsage | None
    text: str | None


def _integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("The model ledger contains an invalid count.")
    return value


def completion_charge(model: str, usage: TokenUsage) -> int:
    for count in (usage.input_tokens, usage.cached_input_tokens, usage.output_tokens):
        _integer(count)
    if usage.cached_input_tokens > usage.input_tokens:
        raise ValueError("The model returned invalid token counts.")
    rates = {"gpt-6.1-sol": (2000, 100, 10000), "gpt-6-astra": (10000, 500, 50000)}
    input_rate, cache_rate, output_rate = rates[model]
    if usage.input_tokens > 272_000:
        input_rate *= 2
        cache_rate *= 2
        output_rate = output_rate * 3 // 2
    return (
        (usage.input_tokens - usage.cached_input_tokens) * input_rate
        + usage.cached_input_tokens * cache_rate
        + usage.output_tokens * output_rate
    )


def parse_event(data: object) -> ModelEvent:
    try:
        if not isinstance(data, dict):
            raise ValueError
        for name in ("attempt", "key", "binary", "provider"):
            if not isinstance(data[name], str) or not data[name]:
                raise ValueError
        request = data["request"]
        if not isinstance(request, dict) or set(request) != {
            "prompt",
            "model",
            "max_output_tokens",
        }:
            raise ValueError
        if (
            not isinstance(request["prompt"], str)
            or not 1 <= len(request["prompt"].encode("utf-8")) <= 64_000
            or request["model"] not in ("gpt-6.1-sol", "gpt-6-astra")
            or not 1 <= _integer(request["max_output_tokens"]) <= 128_000
        ):
            raise ValueError
        key = hashlib.sha256(
            json.dumps(
                (data["binary"], data["provider"], request), sort_keys=True
            ).encode("ascii")
        ).hexdigest()
        if data["key"] != key or data["service_tier"] != "standard":
            raise ValueError
        state = data["state"]
        if state not in ("started", "retry", "failed", "completed", "limit-exceeded"):
            raise ValueError
        cost = _integer(data["cost_nanodollars"])
        usage = None
        text = None
        if state in ("completed", "limit-exceeded"):
            result = data["completion"]
            counts = result["usage"]
            if set(counts) != {"input_tokens", "cached_input_tokens", "output_tokens"}:
                raise ValueError
            usage = TokenUsage(
                **{name: _integer(value) for name, value in counts.items()}
            )
            text = result["text"]
            if (
                usage.cached_input_tokens > usage.input_tokens
                or result["model"] != request["model"]
                or result["service_tier"] != "standard"
                or not isinstance(text, str)
                or cost != completion_charge(result["model"], usage)
            ):
                raise ValueError
        elif "completion" in data:
            raise ValueError
        return ModelEvent(
            data["attempt"],
            key,
            data["binary"],
            data["provider"],
            request,
            state,
            cost,
            usage,
            text,
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("The model ledger is malformed or inconsistent.") from None


def read_events(lines: Iterable[str]) -> tuple[ModelEvent, ...]:
    attempts: dict[str, ModelEvent] = {}
    try:
        for line in lines:
            event = parse_event(json.loads(line))
            previous = attempts.get(event.attempt)
            if previous is None:
                if event.state != "started":
                    raise ValueError
            else:
                if (
                    previous.state != "started"
                    or event.state == "started"
                    or (event.key, event.binary, event.provider, event.request)
                    != (
                        previous.key,
                        previous.binary,
                        previous.provider,
                        previous.request,
                    )
                ):
                    raise ValueError
                reserved = previous.cost_nanodollars
                if (
                    (event.state == "failed" and event.cost_nanodollars != reserved)
                    or (
                        event.state == "retry"
                        and event.cost_nanodollars not in (0, reserved)
                    )
                    or (
                        event.state == "completed" and event.cost_nanodollars > reserved
                    )
                    or (
                        event.state == "limit-exceeded"
                        and event.cost_nanodollars <= reserved
                    )
                ):
                    raise ValueError
            attempts[event.attempt] = event
    except (TypeError, ValueError):
        raise ValueError("The model ledger is malformed or inconsistent.") from None
    return tuple(attempts.values())


def summarize(events: Iterable[ModelEvent], binary: str) -> ModelSummary:
    selected = [event for event in events if event.binary == binary]
    measured = [event for event in selected if event.usage is not None]
    usage = TokenUsage(
        *(
            sum(getattr(event.usage, name) for event in measured)
            for name in ("input_tokens", "cached_input_tokens", "output_tokens")
        )
    )
    return ModelSummary(
        len(measured),
        usage,
        sum(event.cost_nanodollars for event in measured),
        sum(event.cost_nanodollars for event in selected if event.usage is None),
    )


def bound_summary(
    workspace: Path, run: Path, binary: str, identity: LedgerIdentity | None = None
) -> ModelSummary:
    if identity is None:
        identity = read_identity(run / "model-ledger.json")
    return summarize(_bound_events(workspace, identity), binary)


def bound_summaries(
    workspace: Path, keys: tuple[str, ...], identity: LedgerIdentity
) -> dict[str, ModelSummary]:
    events = _bound_events(workspace, identity)
    if len(keys) != len(set(keys)) or any(event.binary not in keys for event in events):
        raise ValueError("The model ledger task keys do not match the fixed roster.")
    return {key: summarize(events, key) for key in keys}


def _bound_events(workspace: Path, identity: LedgerIdentity) -> tuple[ModelEvent, ...]:
    path = workspace / "runs" / identity["pipeline_run"] / "llm.jsonl"
    descriptor = _open_ledger(path)
    if descriptor is None:
        if identity["sha256"] is None:
            return ()
        raise ValueError("The model ledger changed after submission.")
    with os.fdopen(descriptor, "rb") as stream:
        content = stream.read()
    if hashlib.sha256(content).hexdigest() != identity["sha256"]:
        raise ValueError("The model ledger changed after submission.")
    return read_events(content.decode("utf-8").splitlines())
