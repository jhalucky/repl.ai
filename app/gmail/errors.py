class InvalidOAuthState(ValueError):
    pass


class HistoryExpiredError(RuntimeError):
    pass


class NeedsReconnectError(RuntimeError):
    def __init__(self, account_id: int | None = None) -> None:
        self.account_id = account_id
        super().__init__(
            "Gmail access was revoked or expired. Reconnect at /auth/google/start"
        )
