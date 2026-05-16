# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Read-only account status route and observer checks."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.api.routes import account as account_route
from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.settings import Settings
from noeticbraid_core.account import status_observer
from noeticbraid_core.account.status_observer import AccountStatusRecord, observe_status

NOW = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
STATUS_PATH = "/api/account/status"
ACCOUNT_STATUS_KEYS = (
    "capability_id",
    "display_name",
    "provider",
    "end_type",
    "login_state",
    "health",
    "checked_at",
    "snapshot_state",
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)


def _client_and_store(settings: Settings) -> tuple[TestClient, TokenStore]:
    app = create_app(settings)
    token_store = TokenStore(settings.state_dir)
    app.state.token_store = token_store
    return TestClient(app), token_store


def _authorized_headers(token_store: TokenStore) -> dict[str, str]:
    presented = token_store.create_token("route-test", ttl_minutes=30)
    return {"Authorization": f"Bearer {presented}"}


def _first_batch_capabilities() -> tuple[dict[str, Any], ...]:
    return (
        {
            "capability_id": "cap_claude_code_cli",
            "display_name": "Claude Code CLI",
            "provider": "anthropic",
            "end_type": "cli",
            "command": "claude",
        },
        {
            "capability_id": "cap_codex_cli",
            "display_name": "Codex CLI",
            "provider": "openai",
            "end_type": "cli",
            "command": "codex",
        },
        {
            "capability_id": "cap_gemini_cli",
            "display_name": "Gemini CLI",
            "provider": "google",
            "end_type": "cli",
            "command": "gemini",
        },
        {
            "capability_id": "cap_gemini_web",
            "display_name": "Gemini Web",
            "provider": "google",
            "end_type": "web",
            "command": None,
        },
        {
            "capability_id": "cap_chatgpt_web",
            "display_name": "ChatGPT Web",
            "provider": "openai",
            "end_type": "web",
            "command": None,
        },
    )


def _route_records() -> list[AccountStatusRecord]:
    return [
        AccountStatusRecord(
            capability_id="cap_claude_code_cli",
            display_name="Claude Code CLI",
            provider="anthropic",
            end_type="cli",
            login_state="unknown",
            health="ok",
            checked_at=NOW,
            snapshot_state="ok",
        ),
        AccountStatusRecord(
            capability_id="cap_codex_cli",
            display_name="Codex CLI",
            provider="openai",
            end_type="cli",
            login_state="unknown",
            health="fail",
            checked_at=NOW,
            snapshot_state="ok",
        ),
        AccountStatusRecord(
            capability_id="cap_gemini_cli",
            display_name="Gemini CLI",
            provider="google",
            end_type="cli",
            login_state="logged_in",
            health="ok",
            checked_at=NOW,
            snapshot_state="ok",
        ),
        AccountStatusRecord(
            capability_id="cap_gemini_web",
            display_name="Gemini Web",
            provider="google",
            end_type="web",
            login_state="unknown",
            health="unknown",
            checked_at=NOW,
            snapshot_state="ok",
        ),
    ]


def test_account_status_requires_bearer_for_unauthorized_and_malformed_paths(tmp_path: Path) -> None:
    client, _token_store = _client_and_store(_settings(tmp_path))

    assert client.get(STATUS_PATH).status_code == 401
    assert client.get(STATUS_PATH, headers={"Authorization": "Bearer"}).status_code == 401
    assert client.get(STATUS_PATH, headers={"Authorization": "Basic synthetic"}).status_code == 401


def test_account_status_rejects_revoked_and_expired_bearers(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client, token_store = _client_and_store(settings)

    revoked_presented = token_store.create_token("route-test", ttl_minutes=30)
    revoked_record = token_store.verify_token(revoked_presented)
    assert revoked_record is not None
    assert token_store.revoke_token(revoked_record.token_id) is True
    assert client.get(STATUS_PATH, headers={"Authorization": f"Bearer {revoked_presented}"}).status_code == 401

    expired_presented = token_store.create_token("route-test", ttl_minutes=30)
    expired_record = token_store.verify_token(expired_presented)
    assert expired_record is not None
    expired_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(token_store.path) as conn:
        conn.execute("UPDATE tokens SET expires_at = ? WHERE token_id = ?", (expired_at, expired_record.token_id))
        conn.commit()
    assert client.get(STATUS_PATH, headers={"Authorization": f"Bearer {expired_presented}"}).status_code == 401


def test_account_status_returns_only_sanitized_allowlisted_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(account_route, "observe_status", lambda *_args, **_kwargs: _route_records())
    client, token_store = _client_and_store(_settings(tmp_path))

    response = client.get(STATUS_PATH, headers=_authorized_headers(token_store))

    assert response.status_code == 200
    body = response.json()
    assert tuple(body.keys()) == ("accounts",)
    assert len(body["accounts"]) == 4
    for item in body["accounts"]:
        assert tuple(item.keys()) == ACCOUNT_STATUS_KEYS
    assert {item["capability_id"] for item in body["accounts"]} == {
        "cap_claude_code_cli",
        "cap_codex_cli",
        "cap_gemini_cli",
        "cap_gemini_web",
    }
    rendered = json.dumps(body, sort_keys=True)
    for forbidden in (
        "email",
        "storage_state_path",
        "oauth",
        ".gemini",
        "cookie",
        "token",
        "browser_profile_label",
        "profile-label",
        "Profile ",
        "usage_count",
        "usage_window",
        "usage_limit_estimate",
        "quota",
    ):
        assert forbidden not in rendered
    assert "/home/" not in rendered
    assert ":\\" not in rendered


def test_account_status_empty_observation_returns_empty_accounts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(account_route, "observe_status", lambda *_args, **_kwargs: [])
    client, token_store = _client_and_store(_settings(tmp_path))

    response = client.get(STATUS_PATH, headers=_authorized_headers(token_store))

    assert response.status_code == 200
    assert response.json() == {"accounts": []}


def test_runtime_openapi_pins_account_status_shape_and_keeps_bearer_private(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    schema = app.openapi()
    operation = schema["paths"][STATUS_PATH]["get"]

    assert "securitySchemes" not in schema.get("components", {})
    assert "security" not in operation
    for parameter in operation.get("parameters", []):
        assert parameter.get("name") != "Authorization"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AccountStatusDetail"
    }
    component = schema["components"]["schemas"]["AccountStatusDetail"]
    assert tuple(component["properties"].keys()) == ("accounts",)


def test_observe_status_reports_first_batch_only_without_writing_artifacts(tmp_path: Path) -> None:
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "google_accounts.json").write_text(
        json.dumps({"active": "synthetic@example.invalid"}),
        encoding="utf-8",
    )
    calls: list[tuple[str, int]] = []

    def fake_version(command: str, timeout_seconds: int) -> SimpleNamespace:
        calls.append((command, timeout_seconds))
        return SimpleNamespace(returncode=0, stdout=f"{command} 1.0\n", stderr="")

    records = observe_status(
        _first_batch_capabilities(),
        now_fn=lambda: NOW,
        home_path=tmp_path,
        version_runner=fake_version,
        gemini_web_probe=lambda: {"loginLikeState": "healthy"},
    )

    by_id = {record.capability_id: record for record in records}
    assert tuple(by_id) == (
        "cap_claude_code_cli",
        "cap_codex_cli",
        "cap_gemini_cli",
        "cap_gemini_web",
    )
    assert calls == [("claude", 5), ("codex", 5), ("gemini", 5)]
    assert by_id["cap_claude_code_cli"].login_state == "unknown"
    assert by_id["cap_codex_cli"].login_state == "unknown"
    assert by_id["cap_gemini_cli"].login_state == "logged_in"
    assert by_id["cap_gemini_cli"].snapshot_state == "ok"
    assert by_id["cap_gemini_web"].login_state == "logged_in"
    assert by_id["cap_gemini_web"].health == "ok"
    assert not (tmp_path / ".omx").exists()


def test_observe_status_gemini_snapshot_missing_valid_and_malformed(tmp_path: Path) -> None:
    def fake_version(_command: str, _timeout_seconds: int) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="gemini 1.0\n", stderr="")

    capabilities = (_first_batch_capabilities()[2],)
    missing = observe_status(capabilities, home_path=tmp_path, version_runner=fake_version)[0]
    assert missing.login_state == "logged_out"
    assert missing.snapshot_state == "ok"

    accounts_path = tmp_path / ".gemini" / "google_accounts.json"
    accounts_path.parent.mkdir()
    accounts_path.write_text(json.dumps({"active": "synthetic@example.invalid"}), encoding="utf-8")
    valid = observe_status(capabilities, home_path=tmp_path, version_runner=fake_version)[0]
    assert valid.login_state == "logged_in"
    assert valid.snapshot_state == "ok"

    accounts_path.write_text("{not-json", encoding="utf-8")
    malformed = observe_status(capabilities, home_path=tmp_path, version_runner=fake_version)[0]
    assert malformed.login_state == "unknown"
    assert malformed.snapshot_state == "racing"


def test_observe_status_gemini_snapshot_stat_mismatch_soft_fails(tmp_path: Path, monkeypatch) -> None:
    def fake_version(_command: str, _timeout_seconds: int) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="gemini 1.0\n", stderr="")

    accounts_path = tmp_path / ".gemini" / "google_accounts.json"
    accounts_path.parent.mkdir()
    accounts_path.write_text(json.dumps({"active": "synthetic@example.invalid"}), encoding="utf-8")
    real_stat = Path.stat
    stat_calls = 0

    def flaky_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal stat_calls
        result = real_stat(self, *args, **kwargs)
        if self == accounts_path:
            stat_calls += 1
            if stat_calls in {2, 4}:
                return SimpleNamespace(
                    st_ino=result.st_ino + stat_calls,
                    st_size=result.st_size,
                    st_mtime_ns=result.st_mtime_ns,
                )
        return result

    monkeypatch.setattr(status_observer.Path, "stat", flaky_stat)

    record = observe_status((_first_batch_capabilities()[2],), home_path=tmp_path, version_runner=fake_version)[0]

    assert record.login_state == "unknown"
    assert record.snapshot_state == "racing"


def test_observe_status_reads_only_gemini_google_accounts_snapshot(tmp_path: Path, monkeypatch) -> None:
    def fake_version(_command: str, _timeout_seconds: int) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="gemini 1.0\n", stderr="")

    gemini_dir = tmp_path / ".gemini"
    gemini_dir.mkdir()
    (gemini_dir / "google_accounts.json").write_text(
        json.dumps({"active": "synthetic@example.invalid"}),
        encoding="utf-8",
    )
    (gemini_dir / "oauth_creds.json").write_text("must-not-open", encoding="utf-8")
    (gemini_dir / "accounts").mkdir()
    (gemini_dir / "accounts" / "synthetic.json").write_text("must-not-open", encoding="utf-8")
    opened: list[Path] = []
    real_open = Path.open

    def tracking_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        opened.append(self)
        if self.name == "oauth_creds.json" or self.parent.name == "accounts":
            raise AssertionError(f"opened forbidden Gemini path: {self}")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(status_observer.Path, "open", tracking_open)

    record = observe_status((_first_batch_capabilities()[2],), home_path=tmp_path, version_runner=fake_version)[0]

    assert record.login_state == "logged_in"
    assert opened == [gemini_dir / "google_accounts.json"]
