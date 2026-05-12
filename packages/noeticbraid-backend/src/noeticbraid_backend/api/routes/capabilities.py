# SPDX-License-Identifier: Apache-2.0
"""Capability registry routes for SDD-D2-02."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from noeticbraid_backend.api.deps import get_settings
from noeticbraid_backend.contracts import CapabilitiesResponse, CapabilityHealthCheckResponse
from noeticbraid_backend.omc_workspace.capability_registry import health_check, list_capabilities

router = APIRouter(prefix="/api", tags=["capabilities"])


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="List first-stage capabilities",
    operation_id="capabilities_api_capabilities_get",
)
async def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(capabilities=list_capabilities())


@router.post(
    "/capabilities/{id}/health-check",
    response_model=CapabilityHealthCheckResponse,
    summary="Run capability health check",
    operation_id="capability_health_check_api_capabilities_id_health_check_post",
)
async def capability_health_check(request: Request, id: str) -> CapabilityHealthCheckResponse:
    try:
        payload = health_check(id, project_root=get_settings(request).state_dir.parent)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="capability not found") from None
    return CapabilityHealthCheckResponse(**payload)


__all__ = ["capabilities", "capability_health_check"]
