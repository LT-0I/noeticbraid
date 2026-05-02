# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies and factory helpers for Stage 2.2."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from noeticbraid_backend.auth.token_store import TokenRecord, TokenStore
from noeticbraid_backend.auth.vault import CredentialVault
from noeticbraid_backend.settings import Settings
from noeticbraid_backend.storage.factories import create_run_ledger, create_source_index

_UNAUTHORIZED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def get_settings(request: Request) -> Settings:
    """Return settings attached by the app factory."""

    return request.app.state.settings


def get_token_store(request: Request) -> TokenStore:
    """Return the app-scoped token store for the current settings."""

    existing = getattr(request.app.state, "token_store", None)
    if existing is not None:
        return existing
    store = TokenStore(get_settings(request).state_dir)
    request.app.state.token_store = store
    return store


def get_credential_vault(request: Request) -> CredentialVault:
    """Return the app-scoped credential vault."""

    existing = getattr(request.app.state, "credential_vault", None)
    if existing is not None:
        return existing
    vault = CredentialVault(get_settings(request).dpapi_blob_path)
    request.app.state.credential_vault = vault
    return vault


def require_bearer(request: Request) -> TokenRecord:
    """Verify a manually parsed Authorization: Bearer header.

    This intentionally reads Request.headers directly instead of using FastAPI
    Security/OAuth helpers, preserving the frozen OpenAPI contract's lack of
    bearer securitySchemes and route-level security arrays.
    """

    authorization = request.headers.get("Authorization")
    if authorization is None:
        raise _unauthorized()
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    record = get_token_store(request).verify_token(token.strip())
    if record is None:
        raise _unauthorized()
    return record


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=_UNAUTHORIZED.status_code, detail=_UNAUTHORIZED.detail)


__all__ = [
    "get_settings",
    "get_token_store",
    "get_credential_vault",
    "require_bearer",
    "create_run_ledger",
    "create_source_index",
]
