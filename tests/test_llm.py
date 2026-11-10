import json
from pathlib import Path

import pytest

from phoenix.llm.codex import parse_codex_events
from phoenix.llm.ledger import Budget, BudgetExceeded, Ledger, ReplayMissing
from phoenix.llm.provider import (
    Completion,
    Model,
    ProviderError,
    Request,
    RetryLater,
    Usage,
)


class PublicProvider:
    name = "public-test"

    def __init__(self) -> None:
        self.calls = 0
        self.retry = False

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(10, 0, 10)

    def complete(self, request: Request) -> Completion:
        self.calls += 1
        if self.retry:
            raise RetryLater("The account limit prevents the request.")
        return Completion("answer", Usage(5, 2, 3), request.model)


def test_ledger_records_and_replays_standard_calls(tmp_path: Path) -> None:
    provider = PublicProvider()
    ledger = Ledger(tmp_path)
    request = Request("Public test prompt.")
    with pytest.raises(ReplayMissing):
        ledger.call("original", request, provider, replay=True)
    first = ledger.call("original", request, provider)
    assert ledger.call("original", request, provider) == first
    assert ledger.call("original", request, provider, replay=True) == first
    assert provider.calls == 1
    start, completed = (
        json.loads(line) for line in ledger.path.read_text().splitlines()
    )
    assert start["request"]["prompt"] == request.prompt
    assert completed["completion"]["text"] == "answer"
    assert completed["service_tier"] == "standard"
    assert completed["cost_nanodollars"] == 36_200


def test_ledger_rejects_reservations_before_starting_a_call(tmp_path: Path) -> None:
    provider = PublicProvider()
    ledger = Ledger(tmp_path, Budget(130_000, 170_000))
    ledger.call("first", Request("first"), provider)
    with pytest.raises(BudgetExceeded):
        ledger.call("first", Request("second"), provider)
    assert provider.calls == 1
    ledger.call("second", Request("first"), provider)
    with pytest.raises(BudgetExceeded):
        ledger.call("third", Request("first"), provider)
    assert provider.calls == 2


def test_account_limit_keeps_the_request_retryable(tmp_path: Path) -> None:
    provider = PublicProvider()
    provider.retry = True
    ledger = Ledger(tmp_path, Budget(120_000, 120_000))
    request = Request("Public retry test.")
    with pytest.raises(RetryLater):
        ledger.call("original", request, provider)
    provider.retry = False
    assert ledger.call("original", request, provider).text == "answer"


def test_codex_events_preserve_text_and_usage() -> None:
    events = "\n".join(
        json.dumps(event)
        for event in (
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "answer"},
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 12,
                    "cached_input_tokens": 3,
                    "output_tokens": 4,
                },
            },
        )
    )
    assert parse_codex_events(events, 0, Request("prompt")) == Completion(
        "answer", Usage(12, 3, 4), Model.SOL
    )
    with pytest.raises(ProviderError, match="did not return"):
        parse_codex_events(events, 1, Request("prompt"))


def test_codex_rejects_tool_use_and_identifies_account_limits() -> None:
    with pytest.raises(ProviderError, match="attempted to use a tool"):
        parse_codex_events(
            '{"type":"item.completed","item":{"type":"command_execution"}}',
            0,
            Request("prompt"),
        )
    with pytest.raises(RetryLater):
        parse_codex_events(
            '{"type":"error","message":"Usage limit reached"}', 1, Request("prompt")
        )


def test_responses_request_uses_standard_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from io import BytesIO
    from urllib.request import Request as HttpRequest

    from phoenix.llm import responses

    def respond(message: HttpRequest, *, timeout: int) -> BytesIO:
        body = message.data
        assert isinstance(body, bytes)
        sent = json.loads(body)
        assert sent["service_tier"] == "default"
        assert sent["tools"] == [] and sent["store"] is False
        assert sent["max_output_tokens"] == 128
        return BytesIO(
            json.dumps(
                {
                    "status": "completed",
                    "service_tier": "default",
                    "model": "gpt-6.1-sol",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "answer"}],
                        }
                    ],
                    "usage": {
                        "input_tokens": 12,
                        "input_tokens_details": {"cached_tokens": 3},
                        "output_tokens": 4,
                    },
                }
            ).encode()
        )

    monkeypatch.setattr(responses, "urlopen", respond)
    provider = responses.ResponsesProvider("public-test-key")
    assert provider.complete(
        Request("Public test prompt.", max_output_tokens=128)
    ) == Completion("answer", Usage(12, 3, 4), Model.SOL)
