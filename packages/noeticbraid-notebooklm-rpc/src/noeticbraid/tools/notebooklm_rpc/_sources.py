from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import notebooklm
from notebooklm import SourceStatus, SourceType

from ._errors import NotebookLMSourceError

# --- 1. Frozen mappings ---

SOURCE_TYPE_TO_TAG: dict[SourceType, str] = {
    # frozen contract — tests assert exact dict literal
    SourceType.GOOGLE_DOCS:          "noeticbraid/notebooklm/source/google-docs",
    SourceType.GOOGLE_SLIDES:        "noeticbraid/notebooklm/source/google-slides",
    SourceType.GOOGLE_SPREADSHEET:   "noeticbraid/notebooklm/source/google-spreadsheet",
    SourceType.PDF:                  "noeticbraid/notebooklm/source/pdf",
    SourceType.PASTED_TEXT:          "noeticbraid/notebooklm/source/pasted-text",
    SourceType.WEB_PAGE:             "noeticbraid/notebooklm/source/web-page",
    SourceType.GOOGLE_DRIVE_AUDIO:   "noeticbraid/notebooklm/source/google-drive-audio",
    SourceType.GOOGLE_DRIVE_VIDEO:   "noeticbraid/notebooklm/source/google-drive-video",
    SourceType.YOUTUBE:              "noeticbraid/notebooklm/source/youtube",
    SourceType.MARKDOWN:             "noeticbraid/notebooklm/source/markdown",
    SourceType.DOCX:                 "noeticbraid/notebooklm/source/docx",
    SourceType.CSV:                  "noeticbraid/notebooklm/source/csv",
    SourceType.EPUB:                 "noeticbraid/notebooklm/source/epub",
    SourceType.IMAGE:                "noeticbraid/notebooklm/source/image",
    SourceType.MEDIA:                "noeticbraid/notebooklm/source/media",
    SourceType.UNKNOWN:              "noeticbraid/notebooklm/source/unknown",
}


SOURCE_TYPE_TO_RECORD_TYPE: dict[SourceType, str] = {
    # frozen NB-kind → SourceRecord 1.0.0 source_type enum value
    # NORMATIVE rationale:
    #   - "paper":    long-form authored documents (PDF, EPUB)
    #   - "web_page": URL-hosted resources (WEB_PAGE, YOUTUBE)
    #   - "user_note": user-pasted/uploaded structured content (everything else)
    SourceType.GOOGLE_DOCS:          "user_note",
    SourceType.GOOGLE_SLIDES:        "user_note",
    SourceType.GOOGLE_SPREADSHEET:   "user_note",
    SourceType.PDF:                  "paper",
    SourceType.PASTED_TEXT:          "user_note",
    SourceType.WEB_PAGE:             "web_page",
    SourceType.GOOGLE_DRIVE_AUDIO:   "user_note",
    SourceType.GOOGLE_DRIVE_VIDEO:   "user_note",
    SourceType.YOUTUBE:              "web_page",
    SourceType.MARKDOWN:             "user_note",
    SourceType.DOCX:                 "user_note",
    SourceType.CSV:                  "user_note",
    SourceType.EPUB:                 "paper",
    SourceType.IMAGE:                "user_note",
    SourceType.MEDIA:                "user_note",
    SourceType.UNKNOWN:              "user_note",
}


# Schema-pinned validation regexes (mirror source_record_note.schema.json):
_SOURCE_REF_ID_BODY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9_]+$")
_SOURCE_REF_ID_PREFIX = "source_notebooklm_source_"
_SOURCE_REF_ID_MAXLEN = 128


# --- 2. Serializer ---

def source_to_source_record(
    source: "notebooklm.Source",
    *,
    captured_at: datetime,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Map a NotebookLM Source (+ optional local download path) → SourceRecord 1.0.0 dict."""
    if not isinstance(source.id, str) or not _SOURCE_REF_ID_BODY_RE.fullmatch(source.id):
        raise NotebookLMSourceError(
            error_class="invalid_source_id",
            detail=f"source.id must match {_SOURCE_REF_ID_BODY_RE.pattern}: {source.id!r}",
        )

    source_ref_id = f"{_SOURCE_REF_ID_PREFIX}{source.id}"
    if len(source_ref_id) > _SOURCE_REF_ID_MAXLEN:
        raise NotebookLMSourceError(
            error_class="invalid_source_id",
            detail=f"source_ref_id too long: {len(source_ref_id)} > {_SOURCE_REF_ID_MAXLEN}",
        )

    resolved_title = title_override if title_override is not None else source.title
    if not isinstance(resolved_title, str) or resolved_title.strip() == "":
        raise NotebookLMSourceError(
            error_class="title_empty",
            detail="title must not be empty",
        )

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise NotebookLMSourceError(
            error_class="naive_captured_at",
            detail="captured_at must be timezone-aware",
        )

    if local_path is not None and (not isinstance(local_path, Path) or not local_path.exists()):
        raise NotebookLMSourceError(
            error_class="local_path_missing",
            detail=f"local_path must be an existing pathlib.Path: {local_path!r}",
        )

    if content_hash is not None and not _CONTENT_HASH_RE.fullmatch(content_hash):
        raise NotebookLMSourceError(
            error_class="invalid_content_hash",
            detail=f"content_hash must match {_CONTENT_HASH_RE.pattern}: {content_hash!r}",
        )

    if retrieved_by_run_id is not None and not _RUN_ID_RE.fullmatch(retrieved_by_run_id):
        raise NotebookLMSourceError(
            error_class="invalid_run_id",
            detail=f"retrieved_by_run_id must match {_RUN_ID_RE.pattern}: {retrieved_by_run_id!r}",
        )

    source_type = source.kind
    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": source_ref_id,
        "source_type": SOURCE_TYPE_TO_RECORD_TYPE[source_type],
        "title": resolved_title[:512],
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": [SOURCE_TYPE_TO_TAG[source_type]],
        "source_fingerprint": f"notebooklm_source:{source.id}",
    }
    if local_path is not None:
        record["local_path"] = str(local_path)
    if content_hash is not None:
        record["content_hash"] = content_hash
    if retrieved_by_run_id is not None:
        record["retrieved_by_run_id"] = retrieved_by_run_id
    if source.url:
        record["canonical_url"] = source.url
        record["external_url"] = source.url
    return record


# --- 3. Composite helpers (add + wait + serialize) ---

def _ensure_ready(source: "notebooklm.Source") -> None:
    if source.status != SourceStatus.READY:
        raise NotebookLMSourceError(
            error_class="source_not_ready",
            detail=f"source {source.id}: status={source.status}",
        )


async def add_file_and_serialize(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    file_path: "str | Path",
    *,
    captured_at: datetime,
    mime_type: Optional[str] = None,
    wait_timeout: float = 120.0,
    title_override: Optional[str] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
    local_path: Optional[Path] = None,
) -> "tuple[notebooklm.Source, dict[str, Any]]":
    """add → wait → serialize. Returns (Source, SourceRecord dict)."""
    kwargs: dict[str, Any] = {"wait": True, "wait_timeout": wait_timeout}
    if mime_type is not None:
        kwargs["mime_type"] = mime_type
    source = await client.sources.add_file(notebook_id, file_path, **kwargs)
    _ensure_ready(source)
    record = source_to_source_record(
        source,
        captured_at=captured_at,
        title_override=title_override,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return source, record


async def add_url_and_serialize(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    url: str,
    *,
    captured_at: datetime,
    wait_timeout: float = 120.0,
    title_override: Optional[str] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> "tuple[notebooklm.Source, dict[str, Any]]":
    """add_url → wait → serialize. Returns (Source, SourceRecord dict)."""
    source = await client.sources.add_url(notebook_id, url, wait=True, wait_timeout=wait_timeout)
    _ensure_ready(source)
    record = source_to_source_record(
        source,
        captured_at=captured_at,
        title_override=title_override,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return source, record


async def add_drive_and_serialize(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    file_id: str,
    title: str,
    *,
    captured_at: datetime,
    mime_type: str = "application/vnd.google-apps.document",
    wait_timeout: float = 120.0,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> "tuple[notebooklm.Source, dict[str, Any]]":
    """add_drive → wait → serialize. Returns (Source, SourceRecord dict)."""
    source = await client.sources.add_drive(
        notebook_id,
        file_id,
        title,
        mime_type=mime_type,
        wait=True,
        wait_timeout=wait_timeout,
    )
    _ensure_ready(source)
    record = source_to_source_record(
        source,
        captured_at=captured_at,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return source, record


async def add_text_and_serialize(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    title: str,
    content: str,
    *,
    captured_at: datetime,
    wait_timeout: float = 120.0,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> "tuple[notebooklm.Source, dict[str, Any]]":
    """add_text → wait → serialize. Returns (Source, SourceRecord dict)."""
    source = await client.sources.add_text(
        notebook_id,
        title,
        content,
        wait=True,
        wait_timeout=wait_timeout,
    )
    _ensure_ready(source)
    record = source_to_source_record(
        source,
        captured_at=captured_at,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return source, record
