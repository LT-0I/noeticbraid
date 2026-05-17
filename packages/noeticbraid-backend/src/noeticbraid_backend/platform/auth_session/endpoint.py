# SPDX-License-Identifier: Apache-2.0
"""Env-gated platform development auth-session endpoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.settings import PlatformSettings
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

BEARER_TOKEN_RESPONSE_HEADER = "X-NoeticBraid-Bearer"


def register_platform_auth_session_routes(platform_app: FastAPI) -> None:
    """Register env-gated platform auth-session route on the mounted sub-app."""

    @platform_app.post("/auth/session", summary="Issue a platform development bearer")
    async def platform_auth_session(response: Response) -> dict[str, bool | str]:
        settings = PlatformSettings.from_env()
        account = settings.dev_session_account
        if account is None:
            raise _not_found()
        try:
            resolve_user_path(account, ".")
        except Exception as exc:
            raise _not_found() from exc

        token = TokenStore(settings.data_root).create_token(account, ttl_minutes=30)
        response.headers[BEARER_TOKEN_RESPONSE_HEADER] = token
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Authorization"
        return {"accepted": True, "mode": "platform_session_issued"}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["BEARER_TOKEN_RESPONSE_HEADER", "register_platform_auth_session_routes"]
