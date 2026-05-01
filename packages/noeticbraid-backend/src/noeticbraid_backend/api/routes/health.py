# SPDX-License-Identifier: Apache-2.0
"""Health route."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import CONTRACT_AUTHORITATIVE, CONTRACT_VERSION, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    """Return the frozen v1.0.0 health response."""

    return HealthResponse(status="ok", contract_version=CONTRACT_VERSION, authoritative=CONTRACT_AUTHORITATIVE)
