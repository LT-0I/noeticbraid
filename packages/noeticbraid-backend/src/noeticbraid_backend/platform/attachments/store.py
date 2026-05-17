# SPDX-License-Identifier: Apache-2.0
"""Account-confined task attachment persistence for the platform panel."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.tasks.models import validate_task_id
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

MAX_UPLOAD_BYTES = compat.UPLOAD_FILE_MAX_BYTES
MAX_ATTACHMENTS_PER_TASK = 20
LOCAL_TEXT_PER_ATTACHMENT_CHARS = 8 * 1024
LOCAL_TEXT_AGGREGATE_CHARS = 24 * 1024
SCHEMA_VERSION = 1

_ATTACHMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_EXTENSIONS_BY_MIME: dict[str, frozenset[str]] = {
    "image/png": frozenset({"png"}),
    "image/jpeg": frozenset({"jpg", "jpeg"}),
    "image/webp": frozenset({"webp"}),
    "image/gif": frozenset({"gif"}),
    "video/mp4": frozenset({"mp4"}),
    "video/webm": frozenset({"webm"}),
    "video/quicktime": frozenset({"mov", "qt"}),
    "application/pdf": frozenset({"pdf"}),
    "text/plain": frozenset({"txt", "text"}),
    "text/markdown": frozenset({"md", "markdown"}),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": frozenset({"docx"}),
    "application/msword": frozenset({"doc"}),
    "text/csv": frozenset({"csv"}),
    "application/json": frozenset({"json"}),
    "audio/wav": frozenset({"wav"}),
    "audio/mpeg": frozenset({"mp3", "mpeg"}),
    "audio/mp4": frozenset({"m4a", "mp4"}),
    "audio/ogg": frozenset({"ogg"}),
}
_LOCAL_TEXT_CONTENT_TYPES = frozenset({"text/plain", "text/markdown", "text/csv", "application/json"})
_PUBLIC_KEYS = ("attachment_id", "display_name", "content_type", "bytes", "uploaded_ts")
_INDEX_KEYS = frozenset({"schema_version", "task_id", "attachments"})
_ATTACHMENT_KEYS = frozenset(
    {"attachment_id", "display_name", "stored_ext", "content_type", "bytes", "sha256", "uploaded_ts"}
)


class AttachmentStoreError(Exception):
    """Base attachment store exception."""


class AttachmentNotFound(AttachmentStoreError):
    """Raised when an attachment id is absent or malformed."""


class AttachmentTooLarge(AttachmentStoreError):
    """Raised when an attachment exceeds the locked upload cap."""


class AttachmentLimitExceeded(AttachmentStoreError):
    """Raised when a task already has the maximum attachment count."""


class UnsupportedAttachmentType(AttachmentStoreError):
    """Raised when MIME type and extension do not satisfy the allowlist."""


class InvalidAttachmentName(AttachmentStoreError):
    """Raised when an uploaded filename cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class AttachmentRecord:
    """Private attachment sidecar record."""

    attachment_id: str
    display_name: str
    stored_ext: str
    content_type: str
    bytes: int
    sha256: str
    uploaded_ts: str

    def to_index_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "display_name": self.display_name,
            "stored_ext": self.stored_ext,
            "content_type": self.content_type,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "uploaded_ts": self.uploaded_ts,
        }


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    """A verified attachment path for download."""

    record: AttachmentRecord
    path: Path



def persist_uploaded_attachment(
    account: str,
    task_id: str,
    *,
    display_name: str,
    content_type: str,
    body: bytes,
) -> AttachmentRecord:
    """Persist one uploaded attachment blob and private sidecar metadata."""

    task_key = validate_task_id(task_id)
    name = _validate_display_name(display_name)
    mime = _normalize_content_type(content_type)
    stored_ext = _stored_ext_from_display_name(name)
    _validate_content_type_and_extension(mime, stored_ext)
    if len(body) > MAX_UPLOAD_BYTES:
        raise AttachmentTooLarge("attachment exceeds upload cap")

    records = list(list_attachments(account, task_key))
    if len(records) >= MAX_ATTACHMENTS_PER_TASK:
        raise AttachmentLimitExceeded("attachment limit reached")

    attachment_id = _new_attachment_id(records)
    digest = hashlib.sha256(body).hexdigest()
    record = AttachmentRecord(
        attachment_id=attachment_id,
        display_name=name,
        stored_ext=stored_ext,
        content_type=mime,
        bytes=len(body),
        sha256=digest,
        uploaded_ts=_now_ts(),
    )
    target = attachment_path_for(account, task_key, record)
    try:
        _atomic_write_blob(target, body)
        _write_index(account, task_key, [*records, record])
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return record


def list_attachments(account: str, task_id: str) -> tuple[AttachmentRecord, ...]:
    """Return private attachment records for a task."""

    task_key = validate_task_id(task_id)
    path = index_path_for(account, task_key)
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _records_from_index_payload(payload, task_key)


def get_attachment(account: str, task_id: str, attachment_id: str) -> AttachmentRecord:
    """Return one private attachment record or raise AttachmentNotFound."""

    safe_id = _validate_attachment_id(attachment_id)
    for record in list_attachments(account, task_id):
        if record.attachment_id == safe_id:
            return record
    raise AttachmentNotFound("attachment not found")


def delete_attachment(account: str, task_id: str, attachment_id: str) -> None:
    """Remove one attachment record and its blob."""

    task_key = validate_task_id(task_id)
    record = get_attachment(account, task_key, attachment_id)
    remaining = [item for item in list_attachments(account, task_key) if item.attachment_id != record.attachment_id]
    _write_index(account, task_key, remaining)
    try:
        attachment_path_for(account, task_key, record).unlink(missing_ok=True)
    except OSError:
        pass


def resolve_attachment_for_download(account: str, task_id: str, attachment_id: str) -> ResolvedAttachment:
    """Resolve and integrity-check an attachment before serving it."""

    task_key = validate_task_id(task_id)
    record = get_attachment(account, task_key, attachment_id)
    path = attachment_path_for(account, task_key, record)
    body = _read_blob_bounded(path, max_bytes=MAX_UPLOAD_BYTES)
    if len(body) != record.bytes or hashlib.sha256(body).hexdigest() != record.sha256:
        raise AttachmentNotFound("attachment integrity mismatch")
    return ResolvedAttachment(record=record, path=path)


def attachment_path_for(account: str, task_id: str, record: AttachmentRecord) -> Path:
    """Return the account-confined absolute attachment path without reading the blob."""

    task_key = validate_task_id(task_id)
    safe_id = _validate_attachment_id(record.attachment_id)
    safe_ext = _extension_for_rel_path(record.stored_ext)
    return resolve_user_path(account, f"tasks/{task_key}/attachments/{safe_id}.{safe_ext}")


def index_path_for(account: str, task_id: str) -> Path:
    """Return the account-confined private sidecar path."""

    task_key = validate_task_id(task_id)
    return resolve_user_path(account, f"tasks/{task_key}/attachments/_index.json")


def public_projection(record: AttachmentRecord) -> dict[str, str | int]:
    """Return the exact public five-field attachment projection."""

    payload = {
        "attachment_id": record.attachment_id,
        "display_name": record.display_name,
        "content_type": record.content_type,
        "bytes": record.bytes,
        "uploaded_ts": record.uploaded_ts,
    }
    if tuple(payload) != _PUBLIC_KEYS:
        raise ValueError("attachment public projection drift")
    return payload


def attachment_context_for_local_ai(account: str, task_id: str) -> list[dict[str, Any]]:
    """Build bounded, honest attachment context for local model stdin."""

    context: list[dict[str, Any]] = []
    remaining = LOCAL_TEXT_AGGREGATE_CHARS
    for record in list_attachments(account, task_id):
        item: dict[str, Any] = public_projection(record)
        if record.content_type in _LOCAL_TEXT_CONTENT_TYPES:
            text = ""
            if remaining > 0:
                try:
                    data = _read_blob_bounded(
                        attachment_path_for(account, task_id, record),
                        max_bytes=min(LOCAL_TEXT_PER_ATTACHMENT_CHARS, remaining),
                    )
                    text = data.decode("utf-8", errors="replace")[: min(LOCAL_TEXT_PER_ATTACHMENT_CHARS, remaining)]
                except Exception:
                    text = ""
            item["local_analysis"] = "text_extracted"
            item["extracted_text"] = text
            remaining = max(0, remaining - len(text))
        else:
            item["local_analysis"] = "pending_local_unavailable"
        context.append(item)
    return context


def _records_from_index_payload(payload: object, task_id: str) -> tuple[AttachmentRecord, ...]:
    if not isinstance(payload, dict) or set(payload) != _INDEX_KEYS:
        raise ValueError("attachment index schema drift")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("task_id") != task_id:
        raise ValueError("attachment index identity mismatch")
    raw_records = payload.get("attachments")
    if not isinstance(raw_records, list) or len(raw_records) > MAX_ATTACHMENTS_PER_TASK:
        raise ValueError("attachment index count invalid")

    records: list[AttachmentRecord] = []
    seen: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict) or set(raw) != _ATTACHMENT_KEYS:
            raise ValueError("attachment record schema drift")
        record = AttachmentRecord(
            attachment_id=_validate_attachment_id(str(raw["attachment_id"])),
            display_name=_validate_display_name(str(raw["display_name"])),
            stored_ext=_extension_for_rel_path(str(raw["stored_ext"])),
            content_type=_normalize_content_type(str(raw["content_type"])),
            bytes=_validate_byte_count(raw["bytes"]),
            sha256=_validate_sha256(str(raw["sha256"])),
            uploaded_ts=str(raw["uploaded_ts"]),
        )
        _validate_content_type_and_extension(record.content_type, record.stored_ext)
        if record.attachment_id in seen:
            raise ValueError("duplicate attachment id")
        seen.add(record.attachment_id)
        records.append(record)
    return tuple(records)


def _write_index(account: str, task_id: str, records: list[AttachmentRecord]) -> None:
    path = index_path_for(account, task_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": validate_task_id(task_id),
        "attachments": [record.to_index_dict() for record in records],
    }
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        parsed = json.loads(temp_path.read_text(encoding="utf-8"))
        _records_from_index_payload(parsed, task_id)
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def _atomic_write_blob(path: Path, body: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def _read_blob_bounded(path: Path, *, max_bytes: int) -> bytes:
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise AttachmentNotFound("attachment blob missing") from exc
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise AttachmentNotFound("attachment blob invalid")
    if path_stat.st_size > MAX_UPLOAD_BYTES:
        raise AttachmentTooLarge("attachment exceeds upload cap")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AttachmentNotFound("attachment blob invalid") from exc
    try:
        opened_stat = os.fstat(descriptor)
        if stat.S_ISLNK(opened_stat.st_mode) or not stat.S_ISREG(opened_stat.st_mode):
            raise AttachmentNotFound("attachment blob invalid")
        if opened_stat.st_size > MAX_UPLOAD_BYTES:
            raise AttachmentTooLarge("attachment exceeds upload cap")
        return os.read(descriptor, max_bytes + 1)[:max_bytes]
    finally:
        os.close(descriptor)


def _new_attachment_id(records: list[AttachmentRecord]) -> str:
    existing = {record.attachment_id for record in records}
    for _attempt in range(100):
        candidate = secrets.token_hex(8)
        if _ATTACHMENT_ID_RE.fullmatch(candidate) is not None and candidate not in existing:
            return candidate
    raise RuntimeError("could not allocate attachment id")


def _validate_attachment_id(value: str) -> str:
    if not isinstance(value, str) or _ATTACHMENT_ID_RE.fullmatch(value) is None:
        raise AttachmentNotFound("attachment not found")
    return value


def _validate_display_name(value: str) -> str:
    name = str(value or "").strip()
    lowered = name.lower()
    if (
        not name
        or "\x00" in name
        or "/" in name
        or "\\" in name
        or "%2f" in lowered
        or "%5c" in lowered
    ):
        raise InvalidAttachmentName("invalid attachment filename")
    return name


def _stored_ext_from_display_name(display_name: str) -> str:
    suffix = Path(display_name).suffix.lower().lstrip(".")
    return _extension_for_rel_path(suffix)


def _extension_for_rel_path(extension: str) -> str:
    safe = str(extension or "bin").lower().lstrip(".")
    if not safe or not safe.isalnum() or len(safe) > 16:
        return "bin"
    return safe


def _normalize_content_type(content_type: str) -> str:
    return str(content_type or "").split(";", 1)[0].strip().lower()


def _validate_content_type_and_extension(content_type: str, stored_ext: str) -> None:
    allowed_exts = _ALLOWED_EXTENSIONS_BY_MIME.get(content_type)
    if allowed_exts is None or stored_ext not in allowed_exts:
        raise UnsupportedAttachmentType("unsupported attachment type")


def _validate_byte_count(value: object) -> int:
    if not isinstance(value, int) or value < 0 or value > MAX_UPLOAD_BYTES:
        raise ValueError("attachment byte count invalid")
    return value


def _validate_sha256(value: str) -> str:
    digest = str(value or "").lower()
    if _HEX_SHA256_RE.fullmatch(digest) is None:
        raise ValueError("attachment digest invalid")
    return digest


def _now_ts() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "AttachmentLimitExceeded",
    "AttachmentNotFound",
    "AttachmentRecord",
    "AttachmentStoreError",
    "AttachmentTooLarge",
    "InvalidAttachmentName",
    "MAX_ATTACHMENTS_PER_TASK",
    "MAX_UPLOAD_BYTES",
    "ResolvedAttachment",
    "UnsupportedAttachmentType",
    "attachment_context_for_local_ai",
    "attachment_path_for",
    "delete_attachment",
    "get_attachment",
    "index_path_for",
    "list_attachments",
    "persist_uploaded_attachment",
    "public_projection",
    "resolve_attachment_for_download",
]
