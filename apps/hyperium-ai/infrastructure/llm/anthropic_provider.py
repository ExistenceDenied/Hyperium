from __future__ import annotations

from core.interfaces.llm_provider import LLMProvider

# Opus 4.8 is the current, most capable Opus-tier model. It is the default so
# that switching Hyperium onto the API is a quality step up, not a lateral move;
# a cheaper tier (e.g. claude-haiku-4-5) can be set per role via settings.
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider(LLMProvider):
    """
    LLM provider backed by the Anthropic (Claude) API.

    A drop-in alternative to `OllamaProvider` for the text `generate` port, so
    Hyperium's triage, reviewers, critic and email drafting can run on a
    frontier model without any caller changing. Ollama stays the default; this
    is opt-in through settings (`HYPERIUM_LLM_PROVIDER=anthropic`).

    Two deliberate choices keep it honest as a skeleton:

    - The SDK is imported lazily and declared as an optional dependency, so a
      machine that only runs Ollama never needs `anthropic` installed. Anthropic
      code lives in the infrastructure layer, so this does not breach the rule
      that core and application never import a provider.
    - A `client` can be injected, which is how the tests exercise every path
      with a fake — no API key, no network.

    Thinking is off by default. These calls are short (a JSON verdict, an email
    body), and Opus 4.8 with the `thinking` field omitted runs without it: the
    cheaper, faster path, which matters for a system watched on cost. Turn it on
    with `HYPERIUM_ANTHROPIC_THINKING=1` for harder judgement.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout_seconds: float = 300.0,
        system: str | None = None,
        thinking: bool = False,
        client=None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._system = system
        self._thinking = thinking

        if client is not None:
            self._client = client
        else:
            # Lazy: optional dependency, and infrastructure-only by design.
            import anthropic

            # api_key=None lets the SDK resolve ANTHROPIC_API_KEY (or a profile),
            # so a plain `HYPERIUM_LLM_PROVIDER=anthropic` + ANTHROPIC_API_KEY
            # works without threading the secret through Hyperium's own config.
            self._client = anthropic.Anthropic(
                api_key=api_key, timeout=timeout_seconds
            )

    def generate(self, prompt: str) -> str:
        request = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self._system:
            request["system"] = self._system
        if self._thinking:
            request["thinking"] = {"type": "adaptive"}

        message = self._client.messages.create(**request)

        # The response is a list of content blocks; only text blocks carry the
        # answer. A refusal or a thinking-only turn yields no text — returning
        # "" lets the ResilientProvider wrapper treat it as an empty result and
        # retry, exactly as it does for Ollama.
        return "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", None) == "text"
        ).strip()
