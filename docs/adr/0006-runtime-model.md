# Use Standard service for reconstruction requests

Use the OpenAI Responses API if `OPENAI_API_KEY` is present. Use the
signed-in Codex command if the key is absent. Send prompts with tool
access disabled. In the macOS backend, the operating system also blocks
access to the sealed corpus and held-out directories.

Use GPT-6.1 Sol by default. Record the model, service tier, prompt,
response, and token counts in the private run log. Estimate the API
equivalent cost of signed-in Codex requests from published Standard
rates. Keep estimates distinct from account charges.

Before each call, reserve the upper cost of that call from the binary
and run budgets. The Codex command cannot impose the Responses API's
per-call output limit. Reserve the full model output allowance and
the configured input context for a Codex call. A request that exceeds
its reservation fails the budget check after the usage is recorded.

Source references are the [GPT-6.1 Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
the [GPT-6 Astra model page](https://developers.openai.com/api/docs/models/gpt-6-astra),
and the [Codex non-interactive guide](https://learn.chatgpt.com/docs/non-interactive-mode).
