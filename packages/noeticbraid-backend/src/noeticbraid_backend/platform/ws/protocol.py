# SPDX-License-Identifier: Apache-2.0
"""Strict JSON envelope protocol for platform task WebSockets."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.tasks.models import validate_task_id

CLIENT_CLOSE_POLICY_VIOLATION = 1008
CLIENT_CLOSE_UNSUPPORTED = 1003


class ProtocolError(ValueError):
    """Raised for malformed WebSocket frames without echoing raw frame content."""

    def __init__(self, reason: str, *, close_code: int = CLIENT_CLOSE_POLICY_VIOLATION) -> None:
        super().__init__(reason)
        self.reason = reason
        self.close_code = close_code


class AuthClientFrame(BaseModel):
    """First client frame carrying the bearer material out-of-band from the URL."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["auth"]
    token: str = Field(..., min_length=1, max_length=512)


class UserMessageClientFrame(BaseModel):
    """Client chat message for one persisted task."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["user_message"]
    task_id: str
    text: str = Field(..., min_length=1, max_length=compat.PROMPT_MAX_CHARS)

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> "UserMessageClientFrame":  # type: ignore[override]
        value = super().model_validate(obj, *args, **kwargs)
        validate_task_id(value.task_id)
        return value


ClientFrame = AuthClientFrame | UserMessageClientFrame


class BaseServerFrame(BaseModel):
    """Common server frame fields."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    type: str
    task_id: str

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> "BaseServerFrame":  # type: ignore[override]
        value = super().model_validate(obj, *args, **kwargs)
        validate_task_id(value.task_id)
        return value


class AiDeltaServerFrame(BaseServerFrame):
    type: Literal["ai_delta"]
    payload: dict[str, Any]


class ProgressServerFrame(BaseServerFrame):
    type: Literal["progress"]
    message: str = Field(..., min_length=1, max_length=512)
    step: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)


class LedgerServerFrame(BaseServerFrame):
    type: Literal["ledger"]
    event: dict[str, Any]


class ArtifactServerFrame(BaseServerFrame):
    type: Literal["artifact"]
    modality: str = Field(..., min_length=1, max_length=64)
    rel_path: str = Field(..., min_length=1, max_length=4096)
    sha256: str = Field(..., min_length=64, max_length=64)
    bytes_count: int = Field(..., alias="bytes", ge=0)


class ErrorServerFrame(BaseServerFrame):
    type: Literal["error"]
    code: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=512)


class BlockedServerFrame(BaseServerFrame):
    type: Literal["blocked"]
    modality: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=1, max_length=512)


ServerFrame = (
    AiDeltaServerFrame
    | ProgressServerFrame
    | LedgerServerFrame
    | ArtifactServerFrame
    | ErrorServerFrame
    | BlockedServerFrame
)
_SERVER_MODELS: dict[str, type[ServerFrame]] = {
    "ai_delta": AiDeltaServerFrame,
    "progress": ProgressServerFrame,
    "ledger": LedgerServerFrame,
    "artifact": ArtifactServerFrame,
    "error": ErrorServerFrame,
    "blocked": BlockedServerFrame,
}


def parse_client_frame(raw: str | bytes) -> ClientFrame:
    """Parse and strictly validate one client JSON frame."""

    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise ProtocolError("invalid json") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("frame must be an object")
    frame_type = payload.get("type")
    try:
        if frame_type == "auth":
            return AuthClientFrame.model_validate(payload)
        if frame_type == "user_message":
            return UserMessageClientFrame.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise ProtocolError("invalid frame") from exc
    raise ProtocolError("unknown frame type", close_code=CLIENT_CLOSE_UNSUPPORTED)


def validate_server_frame(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a JSON-compatible server frame dict."""

    if not isinstance(payload, dict):
        raise ProtocolError("server frame must be an object")
    frame_type = payload.get("type")
    model = _SERVER_MODELS.get(str(frame_type))
    if model is None:
        raise ProtocolError("unknown server frame type")
    try:
        frame = model.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise ProtocolError("invalid server frame") from exc
    rendered = frame.model_dump(mode="json", by_alias=True, exclude_none=True)
    json.dumps(rendered, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return rendered


__all__ = [
    "AiDeltaServerFrame",
    "ArtifactServerFrame",
    "AuthClientFrame",
    "BlockedServerFrame",
    "CLIENT_CLOSE_POLICY_VIOLATION",
    "CLIENT_CLOSE_UNSUPPORTED",
    "ClientFrame",
    "ErrorServerFrame",
    "LedgerServerFrame",
    "ProgressServerFrame",
    "ProtocolError",
    "ServerFrame",
    "UserMessageClientFrame",
    "parse_client_frame",
    "validate_server_frame",
]
