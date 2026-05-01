# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies and factory helpers for Stage 1."""

from __future__ import annotations

from fastapi import Request

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.auth.vault import CredentialVault
from noeticbraid_backend.settings import Settings
from noeticbraid_backend.storage.factories import create_run_ledger, create_source_index


def get_settings(request: Request) -> Settings:
    """Return settings attached by the app factory."""

    return request.app.state.settings


def get_token_store(request: Request) -> TokenStore:
    """Return a token-store skeleton for the current app settings."""

    return TokenStore(get_settings(request).state_dir)


def get_credential_vault(request: Request) -> CredentialVault:
    """Return the Stage 1 credential-vault skeleton."""

    return CredentialVault(get_settings(request).dpapi_blob_path)


__all__ = [
    "get_settings",
    "get_token_store",
    "get_credential_vault",
    "create_run_ledger",
    "create_source_index",
]
