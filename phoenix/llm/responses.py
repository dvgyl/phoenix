import json
from urllib.error import HTTPError, URLError
from urllib.request import Request as HttpRequest
from urllib.request import urlopen

from phoenix.llm.provider import Completion, ProviderError, Request, RetryLater, Usage

_ENDPOINT = "https://api.openai.com/v1/responses"


class ResponsesProvider:
    name = "openai-responses"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def maximum_usage(self, request: Request) -> Usage:
        return Usage(
            len(request.prompt.encode("utf-8")) + 1024, 0, request.max_output_tokens
        )

    def complete(self, request: Request) -> Completion:
        body = {
            "model": request.model,
            "input": request.prompt,
            "max_output_tokens": request.max_output_tokens,
            "service_tier": "default",
            "store": False,
            "tools": [],
        }
        message = HttpRequest(
            _ENDPOINT,
            json.dumps(body).encode("utf-8"),
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(message, timeout=600) as response:
                data = json.loads(response.read(8 * 1024 * 1024))
        except HTTPError as error:
            if error.code == 429 or 500 <= error.code < 600:
                delay = error.headers.get("Retry-After", "")
                raise RetryLater(
                    "The Responses API is temporarily unavailable.",
                    min(int(delay), 3600) if delay.isdecimal() else 60,
                    cost_unknown=error.code != 429,
                ) from None
            raise ProviderError(
                f"The Responses API returned HTTP {error.code}."
            ) from None
        except URLError:
            raise RetryLater(
                "The Responses API could not be reached.", cost_unknown=True
            ) from None

        if data.get("service_tier") != "default":
            raise ProviderError("The Responses API did not confirm Standard service.")
        if data.get("status") != "completed":
            raise ProviderError("The Responses API returned an incomplete response.")
        content = [
            part["text"]
            for item in data["output"]
            if item["type"] == "message"
            for part in item["content"]
            if part["type"] == "output_text"
        ]
        if not content:
            raise ProviderError("The Responses API returned no output text.")
        usage = data["usage"]
        return Completion(
            "\n".join(content),
            Usage(
                usage["input_tokens"],
                usage["input_tokens_details"].get("cached_tokens", 0),
                usage["output_tokens"],
            ),
            data["model"],
        )
