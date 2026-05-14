from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class NotebookLMPoolError(Exception):
    """Base for noeticbraid pool-layer errors. Distinct from upstream notebooklm.NotebookLMError."""


class NotebookLMQuotaExceededError(NotebookLMPoolError):
    def __init__(
        self,
        account_id: str,
        used_today: int,
        daily_quota: int,
        *,
        reset_at: "datetime | None" = None,
    ):
        self.account_id = account_id
        self.used_today = used_today
        self.daily_quota = daily_quota
        self.reset_at = reset_at
        super().__init__(
            f"Account {account_id!r} exhausted daily quota ({used_today}/{daily_quota}); resets at {reset_at}"
        )


class NotebookLMAccountUnavailableError(NotebookLMPoolError):
    def __init__(self, *, tried: tuple[str, ...], reason: str):
        self.tried = tried
        self.reason = reason
        super().__init__(f"No eligible NotebookLM account in pool. Tried: {tried}. Reason: {reason}")


class NotebookLMPoolStateError(NotebookLMPoolError):
    """Raised when pool.json or pool-state.json fails JSON Schema validation or file IO."""
