from datetime import UTC, datetime, timedelta

from app.gmail.cli import format_table, format_waiting
from app.gmail.client import ThreadView


def _view(*, from_me: bool, subject: str = "Hello there", hours: float = 5) -> ThreadView:
    now = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    return ThreadView(
        thread_id="t1",
        subject=subject,
        last_sender="ada@newco.example",
        last_message_at=now - timedelta(hours=hours),
        last_message_from_me=from_me,
        snippet="should-not-appear SECRET_BODY",
        headers={},
        body="SECRET_BODY_SHOULD_NOT_PRINT",
    )


def test_cli_table_has_no_bodies_or_tokens() -> None:
    now = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    text = format_table(
        [
            _view(from_me=False, subject="Pricing for a 10-seat plan?"),
            _view(from_me=True, subject="Re: intro", hours=1),
        ],
        now=now,
    )
    assert "LAST SENDER" in text
    assert "ada@newco.example" in text
    assert "Pricing for a 10-seat plan?" in text
    assert "yes" in text
    assert "no" in text
    assert "5h" in text
    assert "-" in text
    assert "SECRET_BODY" not in text
    assert "refresh" not in text.lower()
    assert "snippet" not in text.lower() or "should-not-appear" not in text


def test_waiting_dash_when_i_replied() -> None:
    view = _view(from_me=True)
    assert format_waiting(view) == "-"
