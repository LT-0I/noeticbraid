from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import notebooklm
from notebooklm import Note

from ._errors import NotebookLMNoteError
from ._lifecycle import NOTEBOOK_TAG

# --- 1. Frozen constants ---

NOTE_TAG: str = "noeticbraid/notebooklm/note"

_NOTE_REF_ID_BODY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9_]+$")
_SOURCE_REF_ID_PREFIX = "source_notebooklm_note_"
_SOURCE_REF_ID_MAXLEN = 128


# --- 2. Serializer ---

def note_to_source_record(
    note: Note,
    *,
    captured_at: datetime,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Map a NotebookLM Note (+ optional local saved path) to SourceRecord 1.0.0 dict."""
    if not isinstance(note.id, str) or not _NOTE_REF_ID_BODY_RE.fullmatch(note.id):
        raise NotebookLMNoteError(
            error_class="invalid_note_id",
            detail=f"note.id must match {_NOTE_REF_ID_BODY_RE.pattern}: {note.id!r}",
        )

    source_ref_id = f"{_SOURCE_REF_ID_PREFIX}{note.id}"
    if len(source_ref_id) > _SOURCE_REF_ID_MAXLEN:
        raise NotebookLMNoteError(
            error_class="invalid_note_id",
            detail=f"source_ref_id too long: {len(source_ref_id)} > {_SOURCE_REF_ID_MAXLEN}",
        )

    resolved_title = title_override if title_override is not None else note.title
    if not isinstance(resolved_title, str) or resolved_title.strip() == "":
        raise NotebookLMNoteError(
            error_class="title_empty",
            detail="title must not be empty",
        )

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise NotebookLMNoteError(
            error_class="naive_captured_at",
            detail="captured_at must be timezone-aware",
        )

    if local_path is not None and (not isinstance(local_path, Path) or not local_path.exists()):
        raise NotebookLMNoteError(
            error_class="local_path_missing",
            detail=f"local_path must be an existing pathlib.Path: {local_path!r}",
        )

    if content_hash is not None and not _CONTENT_HASH_RE.fullmatch(content_hash):
        raise NotebookLMNoteError(
            error_class="invalid_content_hash",
            detail=f"content_hash must match {_CONTENT_HASH_RE.pattern}: {content_hash!r}",
        )

    if retrieved_by_run_id is not None and not _RUN_ID_RE.fullmatch(retrieved_by_run_id):
        raise NotebookLMNoteError(
            error_class="invalid_run_id",
            detail=f"retrieved_by_run_id must match {_RUN_ID_RE.pattern}: {retrieved_by_run_id!r}",
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
        "tags": [NOTE_TAG, f"{NOTEBOOK_TAG}/{note.notebook_id}"],
        "source_fingerprint": f"notebooklm_note:{note.id}",
    }
    if local_path is not None:
        record["local_path"] = str(local_path)
    if content_hash is not None:
        record["content_hash"] = content_hash
    if retrieved_by_run_id is not None:
        record["retrieved_by_run_id"] = retrieved_by_run_id
    return record


# --- 3. Composite helpers ---

async def create_note_and_serialize(
    client: notebooklm.NotebookLMClient,
    notebook_id: str,
    *,
    title: str,
    content: str,
    captured_at: datetime,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> tuple[Note, dict[str, Any]]:
    """Composite: client.notes.create(...) -> serialize -> (Note, dict)."""
    if not notebook_id:
        raise NotebookLMNoteError(
            error_class="empty_notebook_id",
            detail="notebook_id must not be empty",
        )

    note = await client.notes.create(notebook_id, title=title, content=content)
    record = note_to_source_record(
        note,
        captured_at=captured_at,
        title_override=title_override,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return note, record


async def update_note_and_serialize(
    client: notebooklm.NotebookLMClient,
    notebook_id: str,
    note_id: str,
    *,
    content: str,
    title: str,
    captured_at: datetime,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> tuple[Note, dict[str, Any]]:
    """Composite: client.notes.update(...) + client.notes.get(...) -> serialize -> (Note, dict)."""
    if not notebook_id:
        raise NotebookLMNoteError(
            error_class="empty_notebook_id",
            detail="notebook_id must not be empty",
        )
    if not note_id:
        raise NotebookLMNoteError(
            error_class="empty_note_id",
            detail="note_id must not be empty",
        )

    await client.notes.update(notebook_id, note_id, content=content, title=title)
    note = await client.notes.get(notebook_id, note_id)
    if note is None:
        raise NotebookLMNoteError(
            error_class="note_not_found",
            detail=f"note not found after update: {note_id!r}",
        )

    record = note_to_source_record(
        note,
        captured_at=captured_at,
        title_override=title_override,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return note, record
