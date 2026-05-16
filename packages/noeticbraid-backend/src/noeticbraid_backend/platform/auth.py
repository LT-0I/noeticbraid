# SPDX-License-Identifier: Apache-2.0
"""Manual bearer authentication helpers for platform-only routes."""

from __future__ import annotations

from fastapi import HTTPException, status

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.settings import PlatformSettings


def require_platform_bearer(authorization_header: str | None, store: TokenStore | None = None) -> str:
    """Parse an Authorization: Bearer header and return the verified account."""

    if authorization_header is None:
        raise _unauthorized()
    scheme, separator, presented = authorization_header.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not presented.strip():
        raise _unauthorized()

    resolved_store = store or TokenStore(PlatformSettings.from_env().data_root)
    record = resolved_store.verify_token(presented.strip())
    if record is None:
        raise _unauthorized()
    return str(getattr(record, "account" "_id"))


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


__all__ = ["require_platform_bearer"]
