# SPDX-License-Identifier: Apache-2.0
"""Authenticated platform task attachment endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.attachments import store as attachment_store
from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.local_ai import sanitize_error_msg
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import account_ref_for

_UPLOAD_OP = "webai_chatgpt_upload_and_query"
_DEFAULT_HUB_PROMPT = "Analyze this attachment for the task."
_FORBIDDEN_PUBLIC_REASON_TOKENS = (
    "sha256",
    "conversation_url",
    "chat_url",
    "ledger",
    "dispatch",
    "critique",
    "internal_reason",
    "internal-reason",
    "orchestration",
    "workflow",
)


@dataclass(frozen=True, slots=True)
class _UploadedAttachment:
    filename: str
    content_type: str
    body: bytes


def register_platform_attachment_routes(platform_app: FastAPI) -> None:
    """Register additive task attachment routes on the mounted platform app."""

    @platform_app.post("/tasks/{task_id}/attachments", summary="Upload a platform task attachment")
    async def platform_upload_attachment(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        _load_owned_task(account, task_id)
        _enforce_content_length(request)
        upload = await _read_attachment_part(request)
        try:
            record = attachment_store.persist_uploaded_attachment(
                account,
                task_id,
                display_name=upload.filename,
                content_type=upload.content_type,
                body=upload.body,
            )
        except attachment_store.AttachmentTooLarge as exc:
            raise HTTPException(status_code=413, detail="upload_too_large") from exc
        except attachment_store.UnsupportedAttachmentType as exc:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_attachment_type") from exc
        except attachment_store.AttachmentLimitExceeded as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="attachment_limit") from exc
        except attachment_store.InvalidAttachmentName as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_attachment_name") from exc
        except Exception as exc:
            raise _not_found() from exc
        return {"attachment": attachment_store.public_projection(record)}

    @platform_app.get("/tasks/{task_id}/attachments", summary="List platform task attachments")
    async def platform_list_attachments(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            records = attachment_store.list_attachments(account, task_id)
        except Exception as exc:
            raise _not_found() from exc
        return {"attachments": [attachment_store.public_projection(record) for record in records]}

    @platform_app.get("/tasks/{task_id}/attachments/{attachment_id}", summary="Download a platform task attachment")
    async def platform_download_attachment(request: Request, task_id: str, attachment_id: str) -> FileResponse:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            resolved = attachment_store.resolve_attachment_for_download(account, task_id, attachment_id)
        except Exception as exc:
            raise _not_found() from exc
        return FileResponse(
            resolved.path,
            media_type=resolved.record.content_type,
            filename=resolved.record.display_name,
            content_disposition_type="attachment",
        )

    @platform_app.delete("/tasks/{task_id}/attachments/{attachment_id}", summary="Delete a platform task attachment")
    async def platform_delete_attachment(request: Request, task_id: str, attachment_id: str) -> dict[str, bool]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            attachment_store.delete_attachment(account, task_id, attachment_id)
        except Exception as exc:
            raise _not_found() from exc
        return {"deleted": True}

    @platform_app.post(
        "/tasks/{task_id}/attachments/{attachment_id}/send-to-hub",
        summary="Send a platform task attachment through the gated web-AI hub",
    )
    async def platform_send_attachment_to_hub(request: Request, task_id: str, attachment_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            task = _load_owned_task(account, task_id)
            payload = await _json_body_optional(request)
            attachment_ids = _attachment_ids_for_hub(attachment_id, payload)
            if len(attachment_ids) > compat.UPLOAD_FILE_MAX_COUNT_DEFAULT:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="hub_attachment_count")
            records = [attachment_store.get_attachment(account, task.task_id, item) for item in attachment_ids]
            files = [str(attachment_store.attachment_path_for(account, task.task_id, record)) for record in records]
            result = hub_adapter.dispatch(
                _UPLOAD_OP,
                {
                    "profile": _hub_profile(payload),
                    "query": _hub_prompt(payload),
                    "files": files,
                    "reuse_conversation": False,
                },
                account=account,
                task_id=task.task_id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise _not_found() from exc

        if result.get("outcome") != "ok":
            return {"status": "unavailable", "reason": _public_reason(result)}

        hub_payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        analysis_text = _hub_analysis_text(hub_payload)
        if analysis_text:
            model.append_conversation_row(account, task.task_id, role="assistant", kind="message", text=analysis_text)
        return {"status": str(result.get("status") or hub_payload.get("status") or "ok"), "available": True}


def _load_owned_task(account: str, task_id: str):
    try:
        task = task_store.load_task(account, task_id)
        if task.account_id_ref != account_ref_for(account):
            raise ValueError("task/account binding mismatch")
        return task
    except Exception as exc:
        raise _not_found() from exc


def _enforce_content_length(request: Request) -> None:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        return
    try:
        content_length = int(raw_length)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_content_length") from exc
    if content_length > attachment_store.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload_too_large")


async def _read_attachment_part(request: Request) -> _UploadedAttachment:
    content_type = request.headers.get("content-type", "")
    if not _is_multipart(content_type):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multipart_required")

    body = await request.body()
    if len(body) > attachment_store.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload_too_large")

    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multipart_required")

    first_file: _UploadedAttachment | None = None
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition != "form-data" or filename is None:
            continue
        upload = _UploadedAttachment(
            filename=filename,
            content_type=part.get_content_type().lower(),
            body=part.get_payload(decode=True) or b"",
        )
        if part.get_param("name", header="content-disposition") in {"attachment", "file"}:
            return upload
        if first_file is None:
            first_file = upload

    if first_file is not None:
        return first_file
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="attachment_part_required")


def _is_multipart(content_type: str) -> bool:
    message = Message()
    message["content-type"] = content_type
    return message.get_content_type().lower() == "multipart/form-data" and bool(
        message.get_param("boundary", header="content-type")
    )


async def _json_body_optional(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="json_object_required")
    return payload


def _attachment_ids_for_hub(attachment_id: str, payload: dict[str, Any]) -> list[str]:
    ids = [str(attachment_id)]
    raw_ids = payload.get("attachment_ids")
    if raw_ids is None:
        return ids
    if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="attachment_ids_required")
    for item in raw_ids:
        if item not in ids:
            ids.append(item)
    return ids


def _hub_profile(payload: dict[str, Any]) -> str:
    profile = str(payload.get("profile") or "default").strip().lower()
    return profile or "default"


def _hub_prompt(payload: dict[str, Any]) -> str:
    prompt = str(payload.get("prompt") or payload.get("query") or _DEFAULT_HUB_PROMPT).strip()
    return prompt or _DEFAULT_HUB_PROMPT


def _hub_analysis_text(payload: dict[str, Any]) -> str:
    for key in ("response_text", "message", "summary"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[: compat.RESPONSE_TEXT_MAX_CHARS]
    return ""


def _public_reason(result: dict[str, Any]) -> str:
    reason = sanitize_error_msg(
        str(result.get("reason") or result.get("status") or "hub dispatch blocked"),
        max_chars=512,
    )
    lowered = reason.lower()
    for token in _FORBIDDEN_PUBLIC_REASON_TOKENS:
        if token in lowered:
            reason = _replace_case_insensitive(reason, token, "[redacted]")
            lowered = reason.lower()
    return reason or "hub dispatch blocked"


def _replace_case_insensitive(value: str, needle: str, replacement: str) -> str:
    current = value
    start = current.lower().find(needle.lower())
    while start != -1:
        current = current[:start] + replacement + current[start + len(needle) :]
        start = current.lower().find(needle.lower())
    return current


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["register_platform_attachment_routes"]
