from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class TransientHttpError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


TransientLLMError = TransientHttpError


def is_transient_status(status_code: int) -> bool:
    return status_code in TRANSIENT_STATUS or status_code >= 500


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    retries: int = 1,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except TransientHttpError as exc:
            last_error = exc
            if attempt >= retries:
                break
            logger.warning("HTTP %s, retrying", exc.status_code)
            sleep(backoff_seconds * (attempt + 1))
    assert last_error is not None
    raise last_error
