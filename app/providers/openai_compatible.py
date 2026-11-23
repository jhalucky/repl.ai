from __future__ import annotations

import logging
from typing import Any

import httpx

from app.providers.base import Classification, EmailInput, TokenUsage
from app.providers.http_retry import TransientHttpError, call_with_retry, is_transient_status
from app.providers.parsing import classify_with_json_retry
from app.providers.prompt import SYSTEM_PROMPT, user_prompt

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        json_mode: bool = True,
        disable_thinking: bool = False,
        reasoning_effort: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        max_tokens: int = 300,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._json_mode = json_mode
        self._disable_thinking = disable_thinking
        self._reasoning_effort = (reasoning_effort or "").strip() or None
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._backoff_seconds = backoff_seconds
        self._client = client or httpx.Client(timeout=timeout)

    def classify(self, email: EmailInput) -> Classification:
        def complete() -> tuple[str, TokenUsage]:
            return self._complete(email)

        return classify_with_json_retry(complete)

    def _complete(self, email: EmailInput) -> tuple[str, TokenUsage]:
        user_content = user_prompt(email.sender, email.subject, email.body)
        if self._disable_thinking:
            user_content = user_content.rstrip() + "\n/no_think"

        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"

        def send() -> httpx.Response:
            response = self._client.post(
                url, headers=headers, json=payload, timeout=self._timeout
            )
            if is_transient_status(response.status_code):
                raise TransientHttpError(response.status_code)
            if response.status_code >= 400:
                logger.error("LLM HTTP %s", response.status_code)
                response.raise_for_status()
            return response

        response = call_with_retry(send, backoff_seconds=self._backoff_seconds)
        data = response.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""
        usage_raw = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
        )
        return content, usage
