"""Prices use nanodollars per input, cached input and output token, in that order."""

ROLE_MODELS: dict[str, str] = {
    "runtime": "gpt-6.2-sol",
    "strongest": "gpt-6.2-astra",
}

PRICES: dict[str, tuple[int, int, int]] = {
    ROLE_MODELS["runtime"]: (2000, 100, 10000),
    ROLE_MODELS["strongest"]: (8000, 400, 40000),
}

M1_EFFORT = "medium"
M1_SCHEMA = "m1-candidate-v1"
LLM_RETRY_ATTEMPTS = 5
LLM_RETRY_BASE_DELAY = 30
