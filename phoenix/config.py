"""Prices use nanodollars per input, cached input and output token, in that order."""

ROLE_MODELS: dict[str, str] = {
    "runtime": "gpt-6.1-sol",
    "strongest": "gpt-6-astra",
}

PRICES: dict[str, tuple[int, int, int]] = {
    ROLE_MODELS["runtime"]: (2000, 100, 10000),
    ROLE_MODELS["strongest"]: (10000, 500, 50000),
}
