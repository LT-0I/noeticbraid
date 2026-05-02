# SPDX-License-Identifier: Apache-2.0
"""Account-pool route integration for sanitized quota summaries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.settings import Settings

NOW = datetime(2026, 5, 2, 20, 0, tzinfo=timezone.utc)


def _settings(tmp_path: Path) -> Settings:
    return Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)


def _client_and_store(settings: Settings) -> tuple[TestClient, TokenStore]:
    app = create_app(settings)
    token_store = TokenStore(settings.state_dir)
    app.state.token_store = token_store
    return TestClient(app), token_store


def _seed_quota_summary(settings: Settings) -> None:
    settings.account_quota_dir.mkdir(parents=True, exist_ok=True)
    (settings.account_quota_dir / "accounts.private.json").write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "alias": "chatgpt_6fox",
                        "provider": "chatgpt_web",
                        "enabled": True,
                        "priority": 10,
                        "capabilities": ["web_ui", "file_upload"],
                        "browser_profile_label": "Profile 21",
                        "notes": "synthetic private note",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (settings.account_quota_dir / "quota_state.json").write_text(
        json.dumps(
            {
                "chatgpt_6fox": {
                    "status": "available",
                    "remaining_estimate": "medium",
                    "last_used_at": NOW.isoformat(),
                    "usage_count": 2,
                    "usage_window_started_at": (NOW - timedelta(hours=1)).isoformat(),
                    "usage_limit_estimate": 5,
                }
            }
        ),
        encoding="utf-8",
    )


def _private_marker_names() -> tuple[str, ...]:
    parts = (
        ("raw", "token"),
        ("token", "hash"),
        ("dpapi", "blob"),
        ("credential", "path"),
        ("profile", "path"),
        ("profile", "dir"),
        ("account", "id"),
        ("quota", "window"),
    )
    return tuple(f"{left}_{right}" for left, right in parts)


def test_account_pool_requires_bearer_for_unauthorized_and_malformed_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client, _token_store = _client_and_store(settings)

    assert client.get("/api/account/pool").status_code == 401
    assert client.get("/api/account/pool", headers={"Authorization": "Bearer"}).status_code == 401
    assert client.get("/api/account/pool", headers={"Authorization": "Basic synthetic"}).status_code == 401


def test_account_pool_rejects_revoked_and_expired_bearers(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client, token_store = _client_and_store(settings)

    revoked_presented = token_store.create_token("route-test", ttl_minutes=30)
    revoked_record = token_store.verify_token(revoked_presented)
    assert revoked_record is not None
    assert token_store.revoke_token(revoked_record.token_id) is True
    assert client.get("/api/account/pool", headers={"Authorization": f"Bearer {revoked_presented}"}).status_code == 401

    expired_presented = token_store.create_token("route-test", ttl_minutes=30)
    expired_record = token_store.verify_token(expired_presented)
    assert expired_record is not None
    expired_at = (NOW - timedelta(minutes=1)).isoformat()
    with token_store.connect() as conn:
        conn.execute("UPDATE tokens SET expires_at = ? WHERE token_id = ?", (expired_at, expired_record.token_id))
        conn.commit()
    assert client.get("/api/account/pool", headers={"Authorization": f"Bearer {expired_presented}"}).status_code == 401


def test_account_pool_returns_sanitized_profiles_only_after_authorization(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_quota_summary(settings)
    client, token_store = _client_and_store(settings)
    presented = token_store.create_token("route-test", ttl_minutes=30)

    response = client.get("/api/account/pool", headers={"Authorization": f"Bearer {presented}"})

    assert response.status_code == 200
    body = response.json()
    assert tuple(body.keys()) == ("profiles",)
    assert len(body["profiles"]) == 1
    profile = body["profiles"][0]
    assert profile["alias"] == "chatgpt_6fox"
    assert profile["provider"] == "chatgpt_web"
    assert profile["status"] == "available"
    assert profile["remaining_estimate"] == "medium"
    assert profile["cooldown_until"] is None
    assert profile["capabilities"] == ["web_ui", "file_upload"]
    assert profile["last_used_at"] in {NOW.isoformat(), NOW.isoformat().replace("+00:00", "Z")}
    assert "browser_profile_label" not in profile
    assert "notes" not in profile
    assert "usage_count" not in profile
    assert "usage_window_started_at" not in profile
    assert "usage_limit_estimate" not in profile
    rendered = json.dumps(body, sort_keys=True)
    for marker in _private_marker_names():
        assert marker not in rendered
    assert "Profile 21" not in rendered


def test_account_pool_missing_registry_returns_empty_profiles(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client, token_store = _client_and_store(settings)
    presented = token_store.create_token("route-test", ttl_minutes=30)

    response = client.get("/api/account/pool", headers={"Authorization": f"Bearer {presented}"})

    assert response.status_code == 200
    assert response.json() == {"profiles": []}


def test_runtime_openapi_keeps_bearer_metadata_private(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    schema = app.openapi()
    operation = schema["paths"]["/api/account/pool"]["get"]

    assert "securitySchemes" not in schema.get("components", {})
    assert "security" not in operation
    for parameter in operation.get("parameters", []):
        assert parameter.get("name") != "Authorization"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AccountPoolDraft"
    }
