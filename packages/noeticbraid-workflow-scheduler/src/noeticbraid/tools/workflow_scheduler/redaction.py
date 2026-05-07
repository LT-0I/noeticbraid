"""Redaction helpers shared by ledger, executor, and notifier outputs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_QUERY_KEYS = frozenset(
    {
        "token",
        "access_token",
        "api_key",
        "apikey",
        "key",
        "secret",
        "signature",
        "authorization",
        "password",
        "credential",
        "auth",
        "session",
        "webhook",
        "bot_token",
    }
)
SENSITIVE_KEYS = frozenset(
    {
        "raw_token",
        "token_hash",
        "dpapi_blob",
        "bot_token",
        "webhook_url",
        "cookie",
        "authorization",
        "bearer",
        "password",
        "secret",
        "api_key",
        "apikey",
        "credential",
        "session",
        "token",
    }
)
_TOKEN_LIKE_RE = re.compile(r"\b\d{5,}:[A-Za-z0-9_-]{20,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|raw_token|token_hash|dpapi_blob|cookie|authorization|bearer|password|secret|api_key|apikey|credential|session|webhook_url|bot_token)\s*[:=]\s*[^\s,;]+"
)
_PRIVATE_SEGMENT_RE = re.compile(r"(?i)(^|[\/\s])(private|credentials?|cookies?|token_store|dpapi)([\/][^\s,;]+)?")
_PROFILE_HINT_RE = re.compile(r"(?i)\b(browser[_ -]?profile|profile[_ -]?path|user data directory)\s*[:=]\s*[^\s,;]+")
_PATH_HINT_RE = re.compile(r"(?i)([A-Za-z]:\\Users\\[^\s,;]+|/(?:Users|home)/[^\s,;]+)")
_URL_RE = re.compile(r'https?://[^\s)>"]+')
_WHITESPACE_RE = re.compile(r"\s+")


def redact_url(url: str) -> str:
    """Redact sensitive query values from a URL string."""

    try:
        parts = urlsplit(url)
    except ValueError:
        return "[REDACTED_INVALID_URL]"
    if not parts.query:
        return url
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    safe = [(key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_KEYS else value) for key, value in pairs]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe, doseq=True), parts.fragment))


def redact_text(text: str, limit: int | None = 4096) -> str:
    """Redact token-like strings, secret assignments, and private path hints."""

    value = str(text)
    value = _URL_RE.sub(lambda match: redact_url(match.group(0)), value)
    value = _TOKEN_LIKE_RE.sub("[REDACTED_TOKEN]", value)
    value = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    value = _PRIVATE_SEGMENT_RE.sub(" [REDACTED_PRIVATE_PATH]", value)
    value = _PROFILE_HINT_RE.sub("[REDACTED_PROFILE_PATH]", value)
    value = _PATH_HINT_RE.sub("[REDACTED_LOCAL_PATH]", value)
    value = _WHITESPACE_RE.sub(" ", value).strip()
    if limit is not None and len(value) > limit:
        value = value[: max(0, limit - 16)].rstrip() + " [TRUNCATED]"
    return value


def redact_value(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact JSON-like values; sensitive keys are replaced entirely."""

    if key is not None and key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value, limit=None)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(item_key): redact_value(item, key=str(item_key)) for item_key, item in value.items()}
    return value
