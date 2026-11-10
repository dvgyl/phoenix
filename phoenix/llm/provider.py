from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Model(StrEnum):
    SOL = "gpt-6.1-sol"
    ASTRA = "gpt-6-astra"


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if (
            not 0 <= self.cached_input_tokens <= self.input_tokens
            or self.output_tokens < 0
        ):
            raise ValueError("The model returned invalid token counts.")


@dataclass(frozen=True)
class Request:
    prompt: str
    model: Model = Model.SOL
    max_output_tokens: int = 16_384

    def __post_init__(self) -> None:
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


def cost_nanodollars(model: Model, usage: Usage) -> int:
    input_rate, cache_rate, output_rate = (
        (2_000, 100, 10_000) if model is Model.SOL else (10_000, 500, 50_000)
    )
    if usage.input_tokens > 272_000:
        input_rate *= 2
        cache_rate *= 2
        output_rate = output_rate * 3 // 2
    return (
        (usage.input_tokens - usage.cached_input_tokens) * input_rate
        + usage.cached_input_tokens * cache_rate
        + usage.output_tokens * output_rate
    )
