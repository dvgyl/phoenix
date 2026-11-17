import json
import socket
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, TextIO

from phoenix.llm import select_provider
from phoenix.llm.ledger import Budget, BudgetExceeded, Ledger, LedgerSummary
from phoenix.llm.provider import (
    Completion,
    Provider,
    ProviderError,
    Request,
    RetryLater,
    Usage,
)


class LedgerChannel(Ledger):
    def __init__(self, run: Path, budget: Budget, channel: TextIO) -> None:
        super().__init__(run, budget)
        self.channel = channel

    def _exchange(self, request: object) -> dict[str, Any]:
        self.channel.write(json.dumps(request) + "\n")
        self.channel.flush()
        line = self.channel.readline()
        if not line:
            raise ProviderError("The evaluator model connection closed.")
        result: dict[str, Any] = json.loads(line)
        if result.get("error") == "retry":
            raise RetryLater(str(result["message"]), int(str(result["delay"])))
        if result.get("error") == "budget":
            raise BudgetExceeded(str(result["message"]))
        if "error" in result:
            raise ProviderError(str(result["message"]))
        return result

    def call(
        self, binary: str, request: Request, provider: Provider, *, replay: bool = False
    ) -> Completion:
        if replay:
            raise ProviderError("Replay requires a recorded ledger.")
        result = self._exchange(asdict(request))
        result["usage"] = Usage(**result["usage"])
        if (original := result["original_usage"]) is not None:
            result["original_usage"] = Usage(**original)
        return Completion(**result)

    def summary(self, binary: str) -> LedgerSummary:
        result = self._exchange(None)
        result["usage"] = Usage(**result["usage"])
        return LedgerSummary(**result)


def serve(channel: TextIO, ledger: Ledger, key: str, provider: Provider) -> None:
    while line := channel.readline(1_000_000):
        if not line.endswith("\n"):
            raise ValueError("The model request exceeds the connection limit.")
        raw = json.loads(line)
        try:
            result = (
                asdict(ledger.summary(key))
                if raw is None
                else asdict(ledger.call(key, Request(**raw), provider))
            )
        except RetryLater as error:
            result = {
                "error": "retry",
                "message": str(error),
                "delay": error.delay_seconds,
            }
        except BudgetExceeded as error:
            result = {"error": "budget", "message": str(error)}
        except ProviderError as error:
            result = {"error": "provider", "message": str(error)}
        channel.write(json.dumps(result) + "\n")
        channel.flush()


def main() -> None:
    workspace, run, key, binary_sha256, cap, total, cache, fd = sys.argv[1:]
    directory = Path(run) / key
    provider = select_provider(
        Path(workspace),
        directory,
        binary_sha256=binary_sha256,
        cache_root=Path(cache) if cache else None,
    )
    budget = Budget(int(cap), int(total))
    with (
        socket.socket(fileno=int(fd)) as connection,
        connection.makefile("rw", encoding="utf-8") as channel,
    ):
        serve(channel, Ledger(Path(run), budget), key, provider)


if __name__ == "__main__":
    main()
