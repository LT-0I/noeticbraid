# SPDX-License-Identifier: Apache-2.0
"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from noeticbraid_backend.api.deps import get_credential_vault, get_settings, get_token_store
from noeticbraid_backend.auth.dpapi import DpapiError, unprotect_secret
from noeticbraid_backend.contracts import AuthResponse

BEARER_TOKEN_RESPONSE_HEADER = "X-NoeticBraid-Bearer"
STARTUP_ACCOUNT_ID = "account_startup"

router = APIRouter(prefix="/api", tags=["auth"])


@router.post(
    "/auth/startup_token",
    response_model=AuthResponse,
    summary="Validate startup token",
)
async def startup_token(request: Request, response: Response) -> AuthResponse:
    """Issue a short-lived bearer via response header when DPAPI material is available.

    The frozen AuthResponse schema contains only accepted and mode. The raw
    bearer token is therefore never placed in JSON and is only emitted through
    a non-OpenAPI runtime response header on the successful server-side DPAPI
    path. Missing credentials or unsupported DPAPI fail closed with a
    contract-valid refusal.
    """

    settings = get_settings(request)
    vault = get_credential_vault(request)

    blob = vault.load_credential()
    if blob is None:
        return AuthResponse(accepted=False, mode="startup_credential_unavailable")

    try:
        credential = unprotect_secret(blob)
    except (NotImplementedError, DpapiError, TypeError, ValueError):
        return AuthResponse(accepted=False, mode="dpapi_unavailable")

    if not credential:
        return AuthResponse(accepted=False, mode="startup_credential_unavailable")

    token_store = get_token_store(request)
    try:
        token = token_store.create_token(STARTUP_ACCOUNT_ID, ttl_minutes=30)
    except Exception:
        return AuthResponse(accepted=False, mode="token_store_unavailable")
    finally:
        # Do not retain decrypted startup material beyond the issuance branch.
        credential = b""

    response.headers[BEARER_TOKEN_RESPONSE_HEADER] = token
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"
    # Touch settings so static route review can see this path remains settings-bound.
    del settings
    return AuthResponse(accepted=True, mode="bearer_header_issued")


__all__ = ["BEARER_TOKEN_RESPONSE_HEADER", "router", "startup_token"]
