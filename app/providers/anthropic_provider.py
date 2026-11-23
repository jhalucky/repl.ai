from __future__ import annotations

import logging

import anthropic

from app.providers.base import Classification, EmailInput, TokenUsage
from app.providers.http_retry import TransientHttpError, call_with_retry, is_transient_status
from app.providers.parsing import classify_with_json_retry
from app.providers.prompt import SYSTEM_PROMPT, user_prompt

logger = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: anthropic.Anthropic | None = None,
        timeout: float = 30.0,
        max_tokens: int = 300,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._backoff_seconds = backoff_seconds
        self._client = client or anthropic.Anthropic(api_key=api_key or "missing", timeout=timeout)

    def classify(self, email: EmailInput) -> Classification:
        def complete() -> tuple[str, TokenUsage]:
            return self._complete(email)

        return classify_with_json_retry(complete)

    def _complete(self, email: EmailInput) -> tuple[str, TokenUsage]:
        def send() -> anthropic.types.Message:
            try:
                return self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt(email.sender, email.subject, email.body),
                        }
                    ],
                    extra_body={"temperature": 0},
                )
            except anthropic.APIStatusError as exc:
                status = getattr(exc, "status_code", 0) or 0
                if is_transient_status(status):
                    raise TransientHttpError(status) from exc
                logger.error("LLM HTTP %s", status)
                raise

        message = call_with_retry(send, backoff_seconds=self._backoff_seconds)
        text_parts: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if getattr(block, "type", None) == "text" and isinstance(text, str):
                text_parts.append(text)
        usage_obj = getattr(message, "usage", None)
        usage = TokenUsage(
            prompt_tokens=int(getattr(usage_obj, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage_obj, "output_tokens", 0) or 0),
        )
        return "\n".join(text_parts), usage
