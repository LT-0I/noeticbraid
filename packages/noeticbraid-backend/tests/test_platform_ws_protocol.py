# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 WebSocket protocol validation tests."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.platform.ws.protocol import (
    AuthClientFrame,
    ProtocolError,
    UserMessageClientFrame,
    parse_client_frame,
    validate_server_frame,
)


def test_parse_client_auth_and_user_message_frames() -> None:
    auth = parse_client_frame('{"type":"auth","token":"opaque-token"}')
    user = parse_client_frame('{"type":"user_message","task_id":"task_alpha","text":"hello"}')

    assert isinstance(auth, AuthClientFrame)
    assert auth.token == "opaque-token"
    assert isinstance(user, UserMessageClientFrame)
    assert user.task_id == "task_alpha"
    assert user.text == "hello"


@pytest.mark.parametrize(
    "raw",
    [
        '{"type":"other"}',
        '{"type":"auth","token":"x","extra":1}',
        '{"type":"user_message","task_id":"bad-task","text":"hello"}',
        '[]',
        '{',
    ],
)
def test_parse_client_frame_rejects_unknown_or_invalid_shapes(raw: str) -> None:
    with pytest.raises(ProtocolError):
        parse_client_frame(raw)


def test_validate_server_frame_strict_shapes_and_aliases() -> None:
    artifact = validate_server_frame(
        {
            "type": "artifact",
            "task_id": "task_alpha",
            "modality": "text",
            "rel_path": "tasks/task_alpha/artifacts/01-text.md",
            "sha256": "a" * 64,
            "bytes": 12,
        }
    )
    assert artifact["bytes"] == 12

    with pytest.raises(ProtocolError):
        validate_server_frame({"type": "progress", "task_id": "task_alpha", "message": "ok", "extra": True})
