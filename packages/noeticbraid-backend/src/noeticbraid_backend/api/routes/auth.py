# SPDX-License-Identifier: Apache-2.0
"""Authentication route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import AuthResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.post(
    "/auth/startup_token",
    response_model=AuthResponse,
    summary="Validate startup token",
)
async def startup_token() -> AuthResponse:
    """Stage 1 startup-token endpoint; no request body and always rejects."""

    return AuthResponse(accepted=False, mode="stage1_skeleton")
