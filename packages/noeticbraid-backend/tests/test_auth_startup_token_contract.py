# SPDX-License-Identifier: Apache-2.0
"""Startup-token endpoint contract invariants."""
# ruff: noqa: E402

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from noeticbraid_backend.api.routes import auth as auth_route
from noeticbraid_backend.api.routes.auth import BEARER_TOKEN_RESPONSE_HEADER
from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth import vault as vault_module
from noeticbraid_backend.auth.dpapi import DpapiBlob
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.auth.vault import CredentialVault
from noeticbraid_backend.settings import DPAPI_BLOB_PATH_ENV, LOCAL_STARTUP_AUTH_ENV, Settings


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


def _portable_app(tmp_path: Path, *, local_startup_auth: bool = True):
    return create_app(
        Settings(
            state_dir=tmp_path / "state",
            dpapi_blob_path=None,
            local_startup_auth=local_startup_auth,
        )
    )


def _portable_client(tmp_path: Path, *, local_startup_auth: bool = True):
    app = _portable_app(tmp_path, local_startup_auth=local_startup_auth)
    return app, TestClient(app, raise_server_exceptions=False)


def _startup_secret_path(app) -> Path:
    return app.state.settings.local_startup_secret_path


def _write_secret(path: Path, secret: bytes = b"portable-startup-secret") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_bytes(secret)
    path.chmod(0o600)


def _assert_refused(response, mode: str) -> None:
    assert response.status_code == 200
    assert response.json() == {"accepted": False, "mode": mode}
    assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers


def test_local_startup_auth_opt_in_without_dpapi_mints_bearer_and_secret(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    raw_token = response.headers[BEARER_TOKEN_RESPONSE_HEADER]
    assert app.state.token_store.verify_token(raw_token) is not None
    secret_path = _startup_secret_path(app)
    secret_stat = secret_path.stat()
    assert stat.S_IMODE(secret_stat.st_mode) == 0o600
    assert secret_stat.st_uid == os.geteuid()


def test_local_startup_auth_rejects_preplaced_group_readable_secret(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    _write_secret(secret_path)
    secret_path.chmod(0o644)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")


def test_local_startup_auth_rejects_secret_owned_by_other_uid(tmp_path: Path, monkeypatch) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    _write_secret(secret_path)
    original_fstat = os.fstat

    def _fstat_with_other_secret_uid(fd: int):
        fd_stat = original_fstat(fd)
        try:
            fd_path = Path(os.readlink(f"/proc/self/fd/{fd}")).resolve()
        except OSError:
            return fd_stat
        if fd_path == secret_path.resolve():
            values = list(fd_stat)
            values[stat.ST_UID] = os.geteuid() + 1
            return os.stat_result(values)
        return fd_stat

    monkeypatch.setattr(os, "fstat", _fstat_with_other_secret_uid)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")


def test_local_startup_auth_off_with_blob_present_still_reports_dpapi_unavailable(
    tmp_path: Path,
) -> None:
    app, client = _portable_client(tmp_path, local_startup_auth=False)
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "dpapi_unavailable")


def test_local_startup_auth_off_without_blob_still_reports_startup_credential_unavailable(
    tmp_path: Path,
) -> None:
    app, client = _portable_client(tmp_path, local_startup_auth=False)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "startup_credential_unavailable")
    assert not _startup_secret_path(app).exists()


def test_local_startup_auth_reuses_preplaced_valid_secret_without_rewriting(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    original_secret = b"stable-portable-secret"
    _write_secret(secret_path, original_secret)

    first_response = client.post("/api/auth/startup_token")
    second_response = client.post("/api/auth/startup_token")

    assert first_response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    assert second_response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    assert app.state.token_store.verify_token(first_response.headers[BEARER_TOKEN_RESPONSE_HEADER])
    assert app.state.token_store.verify_token(second_response.headers[BEARER_TOKEN_RESPONSE_HEADER])
    assert secret_path.read_bytes() == original_secret
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600


def test_local_startup_auth_rejects_symlink_secret_without_reading_target(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.parent.chmod(0o700)
    target = tmp_path / "attacker-secret"
    target.write_bytes(b"attacker-controlled-secret")
    secret_path.symlink_to(target)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")
    assert target.read_bytes() == b"attacker-controlled-secret"


def test_local_startup_auth_rejects_unsafe_parent_without_creating_secret(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.parent.chmod(0o777)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")
    assert not secret_path.exists()


def test_local_startup_auth_rejects_non_regular_secret(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.parent.chmod(0o700)
    secret_path.mkdir()
    secret_path.chmod(0o600)

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")


def test_local_startup_auth_rejects_whitespace_only_secret(tmp_path: Path) -> None:
    app, client = _portable_client(tmp_path)
    secret_path = _startup_secret_path(app)
    _write_secret(secret_path, b" \n\t")

    response = client.post("/api/auth/startup_token")

    _assert_refused(response, "local_startup_secret_rejected")


@pytest.mark.parametrize("raw", [None, "", " ", "0", "false", "yes", "on", "anything"])
def test_local_startup_auth_env_parser_defaults_off(raw: str | None, monkeypatch) -> None:
    if raw is None:
        monkeypatch.delenv(LOCAL_STARTUP_AUTH_ENV, raising=False)
    else:
        monkeypatch.setenv(LOCAL_STARTUP_AUTH_ENV, raw)

    assert Settings.from_env().local_startup_auth is False


@pytest.mark.parametrize("raw", ["1", " TRUE "])
def test_local_startup_auth_env_parser_accepts_only_one_or_true(raw: str, monkeypatch) -> None:
    monkeypatch.setenv(LOCAL_STARTUP_AUTH_ENV, raw)

    assert Settings.from_env().local_startup_auth is True


def test_dpapi_success_wins_even_when_portable_secret_is_corrupt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app, client = _portable_client(tmp_path)
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))
    secret_path = _startup_secret_path(app)
    _write_secret(secret_path, b"corrupt-portable-secret")
    secret_path.chmod(0o644)
    monkeypatch.setattr(auth_route, "unprotect_secret", lambda blob: b"startup-material")

    def _portable_branch_must_not_run(path: Path) -> bytes | None:
        raise AssertionError("portable fallback must not run when DPAPI succeeds")

    monkeypatch.setattr(auth_route, "load_or_create_local_startup_secret", _portable_branch_must_not_run)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    assert app.state.token_store.verify_token(response.headers[BEARER_TOKEN_RESPONSE_HEADER])


def test_local_startup_secret_file_exists_race_reopens_without_rewriting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    secret_path = tmp_path / "state" / "auth" / "startup_secret"
    existing_secret = b"race-created-secret"
    _write_secret(secret_path, existing_secret)
    original_open = os.open
    create_attempts = 0

    def _open_with_file_exists(path, flags: int, mode: int = 0o777, *, dir_fd=None):
        nonlocal create_attempts
        if Path(path) == secret_path and flags & os.O_CREAT and flags & os.O_EXCL:
            create_attempts += 1
            raise FileExistsError("created by racing process")
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", _open_with_file_exists)

    secret = vault_module.load_or_create_local_startup_secret(secret_path)

    assert create_attempts == 1
    assert secret == existing_secret
    assert secret_path.read_bytes() == existing_secret


def test_local_startup_auth_falls_back_when_dpapi_unprotect_raises(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app, client = _portable_client(tmp_path)
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))
    _write_secret(_startup_secret_path(app), b"fallback-after-dpapi-raise")

    def _raise_dpapi_unavailable(blob: DpapiBlob) -> bytes:
        raise NotImplementedError("DPAPI unavailable")

    monkeypatch.setattr(auth_route, "unprotect_secret", _raise_dpapi_unavailable)

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "mode": "bearer_header_issued"}
    assert app.state.token_store.verify_token(response.headers[BEARER_TOKEN_RESPONSE_HEADER])


@pytest.mark.parametrize(
    ("secret", "expected_mode"),
    [
        (b"fallback-after-empty-dpapi", "bearer_header_issued"),
        (b" \n\t", "local_startup_secret_rejected"),
    ],
)
def test_local_startup_auth_falls_back_when_dpapi_unprotect_returns_empty(
    tmp_path: Path,
    monkeypatch,
    secret: bytes,
    expected_mode: str,
) -> None:
    app, client = _portable_client(tmp_path)
    app.state.credential_vault = _FakeVault(DpapiBlob(ciphertext=b"test-placeholder"))
    _write_secret(_startup_secret_path(app), secret)
    monkeypatch.setattr(auth_route, "unprotect_secret", lambda blob: b"")

    response = client.post("/api/auth/startup_token")

    assert response.status_code == 200
    assert response.json() == {"accepted": expected_mode == "bearer_header_issued", "mode": expected_mode}
    if expected_mode == "bearer_header_issued":
        assert app.state.token_store.verify_token(response.headers[BEARER_TOKEN_RESPONSE_HEADER])
    else:
        assert BEARER_TOKEN_RESPONSE_HEADER not in response.headers
