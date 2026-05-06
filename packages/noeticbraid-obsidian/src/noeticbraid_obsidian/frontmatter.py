# SPDX-License-Identifier: Apache-2.0
"""Small YAML-frontmatter reader/writer for the SP-D portable Markdown subset."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    text = str(value)
    if text == "" or text.strip() != text or any(ch in text for ch in [":", "#", "[", "]", "{", "}", "\n"]):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def dump_frontmatter(frontmatter: Mapping[str, Any]) -> str:
    """Serialize a deterministic, conservative YAML frontmatter subset."""

    lines: list[str] = []
    for key, value in frontmatter.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_dump_scalar(item)}")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    return "\n".join(lines)


def render_markdown(frontmatter: Mapping[str, Any], body: str) -> str:
    """Render frontmatter plus Markdown body."""

    return f"---\n{dump_frontmatter(frontmatter)}\n---\n\n{body.strip()}\n"


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "None"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse a Markdown note with optional YAML frontmatter.

    This parser intentionally supports only the subset emitted by this package:
    scalar values and one-level lists.
    """

    if not text.startswith("---\n"):
        return {}, text.strip()
    try:
        end = text.index("\n---", 4)
    except ValueError:
        return {}, text.strip()
    block = text[4:end]
    body = text[end + len("\n---") :].lstrip("\r\n").rstrip()
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            data.setdefault(current_key, [])
            if not isinstance(data[current_key], list):
                raise ValueError(f"frontmatter key {current_key} mixes scalar and list")
            data[current_key].append(_parse_scalar(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        parsed = _parse_scalar(raw_value)
        data[key] = [] if parsed is None and raw_value.strip() == "" else parsed
        current_key = key if raw_value.strip() == "" else None
    return data, body
