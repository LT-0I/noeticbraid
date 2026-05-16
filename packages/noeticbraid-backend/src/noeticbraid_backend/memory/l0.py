# SPDX-License-Identifier: Apache-2.0
"""Idempotent L0 raw-event capture model ported from TencentDB-Agent-Memory."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Literal, Mapping, Sequence

Role = Literal["user", "assistant"]
_CONTEXT_BLOCK_RE = re.compile(r"<relevant-memories>[\s\S]*?</relevant-memories>")
_PERSONA_BLOCK_RE = re.compile(r"<user-persona>[\s\S]*?</user-persona>")
_SCENES_BLOCK_RE = re.compile(r"<relevant-scenes>[\s\S]*?</relevant-scenes>")
_SCENE_NAV_RE = re.compile(r"<scene-navigation>[\s\S]*?</scene-navigation>")
_CURRENT_TASK_RE = re.compile(r"<current_task_context>[\s\S]*?</current_task_context>")
_HISTORY_TASK_RE = re.compile(r"<history_task_context[\s\S]*?</history_task_context>")
_INBOUND_METADATA_RE = re.compile(
    r"(?:Conversation info|Sender|Thread starter|Replied message|Forwarded message context|"
    r"Chat history since last reply)\s*\(untrusted[\s\S]*?\):\s*```json\s*[\s\S]*?```"
)
_LEGACY_SESSION_JSON_RE = re.compile(r"```json\s*\{[\s\S]*?\"session[\s\S]*?\}\s*```")
_REPLY_DIRECTIVE_RE = re.compile(r"\[\[reply_to[^\]]*\]\]\s*")
_SKILL_WRAPPER_RE = re.compile(r"¥¥\[[\s\S]*?\]¥¥")
_LEADING_TIMESTAMP_RE = re.compile(r"^\[[\w\d\-:+ ]+\]\s*", re.M)
_MEDIA_ATTACHMENT_RE = re.compile(r"\[media attached:[^\]]*\]\s*")
_IMAGE_REPLY_RE = re.compile(
    r"To send an image back,[\s\S]*?(?:Keep caption in the text body\.)\s*"
)
_SYSTEM_EXEC_RE = re.compile(r"^System:\s*\[[\s\S]*?$", re.M)
_IMAGE_DATA_RE = re.compile(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+", re.I)
_CODE_BLOCK_RE = re.compile(r"```[^\n]*\n[\s\S]*?```")


@dataclass(frozen=True)
class ConversationMessage:
    """Sanitized user/assistant message eligible for L0 capture."""

    id: str
    role: Role
    content: str
    timestamp: int


@dataclass(frozen=True)
class L0MessageRecord:
    """Flat JSONL-compatible L0 record; persistence is wired later."""

    session_key: str
    session_id: str
    recorded_at: str
    id: str
    role: Role
    content: str
    timestamp: int

    def to_json_dict(self) -> dict[str, str | int]:
        return {
            "sessionKey": self.session_key,
            "sessionId": self.session_id,
            "recordedAt": self.recorded_at,
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class L0CaptureBatch:
    """Result of preparing an idempotent L0 capture batch."""

    records: tuple[L0MessageRecord, ...]
    messages: tuple[ConversationMessage, ...]
    max_timestamp: int | None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _message_id(role: str, content: str, timestamp: int, index: int) -> str:
    digest = hashlib.sha256(f"{role}\0{timestamp}\0{index}\0{content}".encode()).hexdigest()
    return f"msg_{timestamp}_{digest[:12]}"


def _text_from_content(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
        parts: list[str] = []
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return None


def extract_user_assistant_messages(
    messages: Iterable[Mapping[str, Any]],
    *,
    now_ms: int | None = None,
) -> tuple[ConversationMessage, ...]:
    """Extract raw user/assistant content from host message objects."""

    fallback_now = _now_ms() if now_ms is None else now_ms
    result: list[ConversationMessage] = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _text_from_content(message.get("content"))
        if content and _IMAGE_DATA_RE.search(content):
            content = _IMAGE_DATA_RE.sub("[image]", content)
        if not content or not content.strip():
            continue
        timestamp_raw = message.get("timestamp")
        timestamp = timestamp_raw if isinstance(timestamp_raw, int | float) else fallback_now
        msg_id = message.get("id")
        content = content.strip()
        result.append(
            ConversationMessage(
                id=msg_id if isinstance(msg_id, str) and msg_id else _message_id(
                    str(role),
                    content,
                    int(timestamp),
                    index,
                ),
                role=role,
                content=content,
                timestamp=int(timestamp),
            )
        )
    return tuple(result)


def sanitize_text(text: str) -> str:
    """Remove injected context, metadata, media, and framework noise."""

    cleaned = text
    for pattern in (
        _CONTEXT_BLOCK_RE,
        _PERSONA_BLOCK_RE,
        _SCENES_BLOCK_RE,
        _SCENE_NAV_RE,
        _CURRENT_TASK_RE,
        _HISTORY_TASK_RE,
        _INBOUND_METADATA_RE,
        _LEGACY_SESSION_JSON_RE,
        _REPLY_DIRECTIVE_RE,
        _SKILL_WRAPPER_RE,
        _LEADING_TIMESTAMP_RE,
        _MEDIA_ATTACHMENT_RE,
        _IMAGE_REPLY_RE,
        _SYSTEM_EXEC_RE,
        _IMAGE_DATA_RE,
    ):
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned.replace("\0", "")).strip()


def strip_code_blocks(text: str) -> str:
    """Strip fenced code blocks from assistant replies."""

    return re.sub(r"\n{3,}", "\n\n", _CODE_BLOCK_RE.sub("", text)).strip()


def is_framework_noise(text: str) -> bool:
    """Detect framework-injected messages that should never be captured."""

    value = text.strip()
    if value == "(session bootstrap)":
        return True
    if value.startswith("A new session was started via"):
        return True
    if re.match(r"^✅\s*New session started", value):
        return True
    if value.startswith("Pre-compaction memory flush"):
        return True
    return re.match(r"^NO_REPLY\s*$", value) is not None


def should_capture_l0(text: str) -> bool:
    """Permissive L0 capture filter from the upstream recorder."""

    if not text or not text.strip():
        return False
    if is_framework_noise(text):
        return False
    return not text.startswith("/")


def prepare_l0_capture(
    *,
    session_key: str,
    raw_messages: Sequence[Mapping[str, Any]],
    session_id: str = "",
    original_user_text: str | None = None,
    after_timestamp: int | None = None,
    original_user_message_count: int | None = None,
    recorded_at: datetime | None = None,
    seen_ids: set[str] | frozenset[str] | None = None,
    now_ms: int | None = None,
) -> L0CaptureBatch:
    """Prepare sanitized L0 records without writing them.

    Idempotence is provided by the strict timestamp cursor, optional position
    slice, deterministic generated IDs, and optional `seen_ids` filtering.
    """

    use_position_slice = (
        original_user_message_count is not None
        and original_user_message_count > 0
        and original_user_message_count <= len(raw_messages)
    )
    sliced = raw_messages[original_user_message_count:] if use_position_slice else raw_messages
    extracted = list(extract_user_assistant_messages(sliced, now_ms=now_ms))
    cursor = after_timestamp or 0
    if cursor:
        extracted = [message for message in extracted if message.timestamp > cursor]

    if original_user_text:
        target_raw: Mapping[str, Any] | None = None
        if use_position_slice and sliced:
            target_raw = sliced[0]
        elif (
            original_user_message_count is not None
            and 0 <= original_user_message_count < len(raw_messages)
        ):
            target_raw = raw_messages[original_user_message_count]
        target_ts = target_raw.get("timestamp") if target_raw else None
        if isinstance(target_ts, int | float):
            for index, message in enumerate(extracted):
                if message.role == "user" and message.timestamp == int(target_ts):
                    extracted[index] = ConversationMessage(
                        id=message.id,
                        role=message.role,
                        content=original_user_text,
                        timestamp=message.timestamp,
                    )
                    break

    filtered: list[ConversationMessage] = []
    seen = seen_ids or frozenset()
    for message in extracted:
        content = sanitize_text(message.content)
        if message.role == "assistant":
            content = strip_code_blocks(content)
        if not should_capture_l0(content) or message.id in seen:
            continue
        filtered.append(
            ConversationMessage(
                id=message.id,
                role=message.role,
                content=content,
                timestamp=message.timestamp,
            )
        )

    recorded = recorded_at or datetime.now(UTC)
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    recorded_iso = recorded.astimezone(UTC).isoformat().replace("+00:00", "Z")
    records = tuple(
        L0MessageRecord(
            session_key=session_key,
            session_id=session_id,
            recorded_at=recorded_iso,
            id=message.id,
            role=message.role,
            content=message.content,
            timestamp=message.timestamp,
        )
        for message in filtered
    )
    max_timestamp = max((message.timestamp for message in filtered), default=None)
    return L0CaptureBatch(records=records, messages=tuple(filtered), max_timestamp=max_timestamp)


__all__ = [
    "ConversationMessage",
    "L0CaptureBatch",
    "L0MessageRecord",
    "Role",
    "extract_user_assistant_messages",
    "is_framework_noise",
    "prepare_l0_capture",
    "sanitize_text",
    "should_capture_l0",
    "strip_code_blocks",
]
