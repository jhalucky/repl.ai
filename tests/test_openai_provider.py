import json

import httpx
import pytest

from app.providers.base import EmailInput
from app.providers.http_retry import TransientHttpError
from app.providers.openai_compatible import OpenAICompatibleProvider

VALID_CONTENT = json.dumps(
    {
        "needs_reply": True,
        "urgency": 5,
        "category": "investor",
        "deadline": "Friday",
        "reason": "Term sheet waiting on a decision.",
        "summary": "Investor wants a Friday decision.",
    }
)


def _ok_body(content: str = VALID_CONTENT) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
    }


def _provider(
    handler,
    *,
    json_mode: bool = True,
    disable_thinking: bool = False,
    timeout: float = 30.0,
    max_tokens: int = 300,
) -> OpenAICompatibleProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, timeout=timeout)
    return OpenAICompatibleProvider(
        api_key="test-key",
        model="gpt-test",
        base_url="https://api.groq.com/openai/v1",
        json_mode=json_mode,
        disable_thinking=disable_thinking,
        timeout=timeout,
        max_tokens=max_tokens,
        client=client,
        backoff_seconds=0,
    )


def test_request_shape_and_usage() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    email = EmailInput(sender="ivy@fund.example", subject="Term sheet", body="Please confirm.")
    result = _provider(handler).classify(email)

    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert body["model"] == "gpt-test"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 300
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert "Please confirm." in body["messages"][1]["content"]
    assert "/no_think" not in body["messages"][1]["content"]
    assert result.needs_reply is True
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7


def test_no_think_appended_only_when_enabled() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello")
    _provider(handler, disable_thinking=True).classify(email)
    user_content = captured["body"]["messages"][1]["content"]
    assert user_content.endswith("/no_think")

    captured.clear()
    _provider(handler, disable_thinking=False).classify(email)
    user_content = captured["body"]["messages"][1]["content"]
    assert "/no_think" not in user_content


def test_max_tokens_and_timeout_passed_through() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["timeout"] = request.extensions.get("timeout")
        return httpx.Response(200, json=_ok_body())

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello")
    _provider(handler, max_tokens=512, timeout=120.0).classify(email)
    assert captured["body"]["max_tokens"] == 512
    timeout = captured["timeout"]
    assert timeout is not None
    if isinstance(timeout, dict):
        read_timeout = timeout.get("read")
    else:
        read_timeout = getattr(timeout, "read", None)
    assert read_timeout == 120.0


def test_json_mode_false_omits_response_format() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello")
    _provider(handler, json_mode=False).classify(email)
    assert "response_format" not in captured["body"]


def test_retries_once_on_429() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(200, json=_ok_body())

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello?")
    result = _provider(handler).classify(email)
    assert calls["n"] == 2
    assert result.needs_reply is True


def test_retries_once_on_502_then_gives_up() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(502, json={"error": "upstream"})

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello?")
    with pytest.raises(TransientHttpError) as exc:
        _provider(handler).classify(email)
    assert exc.value.status_code == 502
    assert calls["n"] == 2


def test_invalid_json_retry_then_fallback() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_ok_body("not-json"))

    email = EmailInput(sender="a@b.com", subject="Hi", body="Hello?")
    result = _provider(handler).classify(email)
    assert calls["n"] == 2
    assert result.needs_reply is None
