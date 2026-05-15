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


# === D5-02 addition (append-only) ===

class NotebookLMSerializationError(NotebookLMPoolError):
    """Raised when artifact_to_source_record() validation fails OR when a
    composite helper's caller misuse / upstream-drift assertion fails.

    Attributes:
        error_class: one of (frozen enumeration; tests assert exact set):
            "invalid_artifact_id"
            "invalid_kind"
            "naive_captured_at"
            "local_path_missing"
            "invalid_content_hash"
            "invalid_run_id"
            "title_empty"
            "wait_not_completed"
            "forbidden_download_kwarg_override"
            "upstream_mind_map_shape_mismatch"
            "mind_map_no_note_id"
        detail: human-readable explanation
    """

    def __init__(self, *, error_class: str, detail: str):
        self.error_class = error_class
        self.detail = detail
        super().__init__(f"{error_class}: {detail}")


# === D5-03 addition (append-only) ===

class NotebookLMLifecycleError(NotebookLMPoolError):
    """Raised when notebook lifecycle / sharing composite helper validates fails
    OR notebook_to_source_record() serializer validation fails.

    Attributes:
        error_class: one of (frozen enumeration; tests assert exact set):
            "invalid_notebook_id"
            "title_empty"
            "naive_captured_at"
            "invalid_run_id"
            "invalid_content_hash"
            "invalid_email"
            "empty_notebook_id"
        detail: human-readable explanation
    """
    def __init__(self, *, error_class: str, detail: str):
        self.error_class = error_class
        self.detail = detail
        super().__init__(f"{error_class}: {detail}")


# === D5-04 addition (append-only) ===

class NotebookLMSourceError(NotebookLMPoolError):
    """Raised when source serializer validation fails OR when source composite
    helper detects upstream/runtime drift.

    Attributes:
        error_class: one of (frozen enumeration; tests assert exact set):
            "invalid_source_id"
            "title_empty"
            "naive_captured_at"
            "local_path_missing"
            "invalid_content_hash"
            "invalid_run_id"
            "source_not_ready"
        detail: human-readable explanation
    """
    def __init__(self, *, error_class: str, detail: str):
        self.error_class = error_class
        self.detail = detail
        super().__init__(f"{error_class}: {detail}")
