from dataclasses import dataclass
from typing import Protocol

from phoenix.config import M1_EFFORT, M1_SCHEMA, ROLE_MODELS
from phoenix_eval.model_ledger import TokenUsage, completion_charge


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if (
            any(
                type(count) is not int
                for count in (
                    self.input_tokens,
                    self.cached_input_tokens,
                    self.output_tokens,
                )
            )
            or not 0 <= self.cached_input_tokens <= self.input_tokens
            or self.output_tokens < 0
        ):
            raise ValueError("The model returned invalid token counts.")


@dataclass(frozen=True)
class Request:
    prompt: str
    model: str = ROLE_MODELS["runtime"]
    max_output_tokens: int = 16_384
    effort: str = M1_EFFORT
    schema: str = M1_SCHEMA

    def __post_init__(self) -> None:
        if self.effort not in ("low", "medium", "high", "xhigh") or not self.schema:
            raise ValueError(
                "Use an explicit model effort and response schema identity."
            )
        if not self.prompt or len(self.prompt.encode("utf-8")) > 64_000:
            raise ValueError("The prompt must contain 1 to 64,000 UTF-8 bytes.")
        if not 1 <= self.max_output_tokens <= 128_000:
            raise ValueError(
                "The requested output token limit is outside the model range."
            )


@dataclass(frozen=True)
class Completion:
    text: str
    usage: Usage
    model: str
    service_tier: str = "standard"
    cache_hit: bool = False
    cache_key: str | None = None
    original_usage: Usage | None = None

    def __post_init__(self) -> None:
        if self.service_tier != "standard":
            raise ValueError("The model response did not use Standard service.")


class ProviderError(RuntimeError):
    pass


class RetryLater(ProviderError):
    def __init__(
        self, message: str, delay_seconds: int = 60, *, cost_unknown: bool = False
    ) -> None:
        super().__init__(message)
        self.delay_seconds = delay_seconds
        self.cost_unknown = cost_unknown


class Provider(Protocol):
    name: str

    def maximum_usage(self, request: Request) -> Usage: ...

    def complete(self, request: Request) -> Completion: ...


def cost_nanodollars(model: str, usage: Usage) -> int:
    return completion_charge(
        model,
        TokenUsage(usage.input_tokens, usage.cached_input_tokens, usage.output_tokens),
    )
