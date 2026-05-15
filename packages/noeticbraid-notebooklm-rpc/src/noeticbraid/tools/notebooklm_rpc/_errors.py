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


# === D5-05 addition (append-only) ===

class NotebookLMNoteError(NotebookLMPoolError):
    """Note serializer / composite errors.

    error_class enum (9 values):
    - invalid_note_id        (id does not match ^[A-Za-z0-9_]+$ or length exceeds 128)
    - empty_notebook_id      (composite input is empty)
    - empty_note_id          (update composite input is empty)
    - note_not_found         (get returns None after update)
    - title_empty            (override fallback remains empty)
    - naive_captured_at      (captured_at has no tzinfo)
    - local_path_missing     (local_path does not exist)
    - invalid_content_hash   (does not match ^sha256:[0-9a-f]{64}$)
    - invalid_run_id         (does not match ^run_[A-Za-z0-9_]+$)
    """
    def __init__(self, *, error_class: str, detail: str = "") -> None:
        super().__init__(detail or error_class)
        self.error_class = error_class
        self.detail = detail


class NotebookLMChatError(NotebookLMPoolError):
    """Chat composite errors (composite-level only; upstream chat.ask errors are transparent).

    error_class enum (3 values):
    - empty_notebook_id      (composite input is empty)
    - empty_question         (composite input is empty)
    - empty_ask_answer       (upstream AskResult.answer is empty)
    """
    def __init__(self, *, error_class: str, detail: str = "") -> None:
        super().__init__(detail or error_class)
        self.error_class = error_class
        self.detail = detail


class NotebookLMArtifactLifecycleError(NotebookLMPoolError):
    """Artifact-lifecycle composite errors (composite-level only; upstream
    revise_slide / wait_for_completion / get / artifact_to_source_record errors are transparent).

    error_class enum (4 values):
    - empty_notebook_id                 (composite input is empty)
    - empty_artifact_id                 (composite input is empty)
    - revision_failed                   (wait_for_completion returned is_failed status)
    - artifact_not_found_after_revision (get after revision returned None)
    """
    def __init__(self, *, error_class: str, detail: str = "") -> None:
        super().__init__(detail or error_class)
        self.error_class = error_class
        self.detail = detail
