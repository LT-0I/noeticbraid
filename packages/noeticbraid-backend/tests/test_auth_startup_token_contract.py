# SPDX-License-Identifier: Apache-2.0
"""Startup-token endpoint contract invariants."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from noeticbraid_backend.api.routes import auth as auth_route
from noeticbraid_backend.api.routes.auth import BEARER_TOKEN_RESPONSE_HEADER
from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.dpapi import DpapiBlob
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.auth.vault import CredentialVault
from noeticbraid_backend.settings import DPAPI_BLOB_PATH_ENV, Settings


class _FakeVault:
    def __init__(self, blob: DpapiBlob | None) -> None:
        self.blob = blob

    def load_credential(self) -> DpapiBlob | None:
        return self.blob


def _app(tmp_path: Path):
    return create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None))


def test_startup_token_openapi_has_no_request_body(tmp_path: Path) -> None:
    app = _app(tmp_path)
    operation = app.openapi()["paths"]["/api/auth/startup_token"]["post"]
    assert "requestBody" not in operation
    assert "parameters" not in operation or operation["parameters"] == []


def test_startup_token_route_has_no_body_query_or_header_params(tmp_path: Path) -> None:
    app = _app(tmp_path)
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/auth/startup_token"
    ]
    assert len(routes) == 1
    route = routes[0]
    assert route.body_field is None
    assert route.dependant.body_params == []
    assert route.dependant.query_params == []
    assert route.dependant.header_params == []


def test_startup_token_safe_refusal_is_contract_valid_and_ignores_json_body(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))

    for response in (
        client.post("/api/auth/startup_token"),
        client.post("/api/auth/startup_token", json={"ignored": True}),
    ):
        assert response.status_code == 200
        assert response.json() == {
            "accepted": False,
            "mode": "startup_credential_unavailable",
        }
        assert set(response.json()) == {"accepted", "mode"}
        assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers


def test_credential_vault_none_blob_path_does_not_read_dpapi_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(DPAPI_BLOB_PATH_ENV, str(tmp_path / "env.dpapi"))

    vault = CredentialVault(blob_path=None)

    assert vault.blob_path is None


def test_startup_token_configured_directory_blob_path_fails_closed(tmp_path: Path) -> None:
    app = create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=tmp_path))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {
        "accepted": False,
        "mode": "startup_credential_unavailable",
    }
    assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers


def test_startup_token_permission_error_blob_path_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    denied_path = tmp_path / "denied.dpapi"
    original_read_bytes = Path.read_bytes

    def _read_bytes(path: Path) -> bytes:
        if path == denied_path:
            raise PermissionError("denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", _read_bytes)
    app = create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=denied_path))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {
        "accepted": False,
        "mode": "startup_credential_unavailable",
    }
    assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers


def test_startup_token_dpapi_unavailable_refusal_is_contract_valid(tmp_path: Path) -> None:
    app = _app(tmp_path)
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))
    client = TestClient(app)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": False, "mode": "dpapi_unavailable"}
    assert set(response.json()) == {"accepted", "mode"}
    assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers


def test_startup_token_success_uses_header_not_json_body(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app(tmp_path)
    store = TokenStore(tmp_path / "state")
    app.state.token_store = store
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))
    monkeypatch.setattr(auth_route, "unprotect_secret", lambda blob: b"startup-material")
    client = TestClient(app)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    assert set(response.json()) == {"accepted", "mode"}
    raw_token = response.headers[BEARER_TOKEN_RESPONSE_HEADER]
    assert raw_token not in str(response.json())
    assert store.verify_token(raw_token) is not None
