from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

import notebooklm
from notebooklm import SharePermission, ShareViewLevel

from ._errors import NotebookLMLifecycleError

# --- 1. NB-internal tag constant ---

NOTEBOOK_TAG: str = "noeticbraid/notebooklm/notebook"


# --- 2. Serializer ---

# Schema-pinned validation regexes (mirror source_record_note.schema.json):
_NOTEBOOK_REF_ID_BODY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_CONTENT_HASH_RE         = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_ID_RE               = re.compile(r"^run_[A-Za-z0-9_]+$")
_EMAIL_RE                = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SOURCE_REF_ID_PREFIX    = "source_notebooklm_notebook_"
_SOURCE_REF_ID_MAXLEN    = 128


def notebook_to_source_record(
    notebook: "notebooklm.Notebook",
    *,
    captured_at: datetime,
    title_override: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> dict[str, Any]:
    """Map a NotebookLM Notebook → SourceRecord 1.0.0 dict."""
    if not isinstance(notebook.id, str) or not _NOTEBOOK_REF_ID_BODY_RE.fullmatch(notebook.id):
        raise NotebookLMLifecycleError(
            error_class="invalid_notebook_id",
            detail=f"notebook.id must match {_NOTEBOOK_REF_ID_BODY_RE.pattern}: {notebook.id!r}",
        )

    source_ref_id = f"{_SOURCE_REF_ID_PREFIX}{notebook.id}"
    if len(source_ref_id) > _SOURCE_REF_ID_MAXLEN:
        raise NotebookLMLifecycleError(
            error_class="invalid_notebook_id",
            detail=f"source_ref_id too long: {len(source_ref_id)} > {_SOURCE_REF_ID_MAXLEN}",
        )

    resolved_title = title_override if title_override is not None else notebook.title
    if resolved_title.strip() == "":
        raise NotebookLMLifecycleError(
            error_class="title_empty",
            detail="title must not be empty",
        )

    if captured_at.tzinfo is None:
        raise NotebookLMLifecycleError(
            error_class="naive_captured_at",
            detail="captured_at must be timezone-aware",
        )

    if retrieved_by_run_id is not None and not _RUN_ID_RE.fullmatch(retrieved_by_run_id):
        raise NotebookLMLifecycleError(
            error_class="invalid_run_id",
            detail=f"retrieved_by_run_id must match {_RUN_ID_RE.pattern}: {retrieved_by_run_id!r}",
        )

    if content_hash is not None and not _CONTENT_HASH_RE.fullmatch(content_hash):
        raise NotebookLMLifecycleError(
            error_class="invalid_content_hash",
            detail=f"content_hash must match {_CONTENT_HASH_RE.pattern}: {content_hash!r}",
        )

    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": source_ref_id,
        "source_type": "user_note",
        "title": resolved_title[:512],
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": [NOTEBOOK_TAG],
        "source_fingerprint": f"notebooklm_notebook:{notebook.id}",
    }
    if retrieved_by_run_id is not None:
        record["retrieved_by_run_id"] = retrieved_by_run_id
    if content_hash is not None:
        record["content_hash"] = content_hash
    return record


# --- 3. Composite helpers (sharing — bundle multi-RPC patterns) ---

async def share_notebook_with_user(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    email: str,
    *,
    permission: "notebooklm.SharePermission" = SharePermission.VIEWER,
    view_level: Optional["notebooklm.ShareViewLevel"] = None,
    notify: bool = True,
    welcome_message: str = "",
) -> "notebooklm.ShareStatus":
    """Share a notebook with a single external user."""
    if not notebook_id:
        raise NotebookLMLifecycleError(
            error_class="empty_notebook_id",
            detail="notebook_id must not be empty",
        )

    if not _EMAIL_RE.fullmatch(email):
        raise NotebookLMLifecycleError(
            error_class="invalid_email",
            detail=f"email must match {_EMAIL_RE.pattern}: {email!r}",
        )

    status = await client.sharing.add_user(
        notebook_id,
        email,
        permission=permission,
        notify=notify,
        welcome_message=welcome_message,
    )
    if view_level is not None:
        status = await client.sharing.set_view_level(notebook_id, view_level)
    return status


async def set_notebook_public_with_view_level(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    *,
    public: bool,
    view_level: "notebooklm.ShareViewLevel" = ShareViewLevel.FULL_NOTEBOOK,
) -> "notebooklm.ShareStatus":
    """Toggle public link sharing AND set the public view level — 2 upstream sharing API calls."""
    if not notebook_id:
        raise NotebookLMLifecycleError(
            error_class="empty_notebook_id",
            detail="notebook_id must not be empty",
        )

    status = await client.sharing.set_public(notebook_id, public)
    status = await client.sharing.set_view_level(notebook_id, view_level)
    return status
