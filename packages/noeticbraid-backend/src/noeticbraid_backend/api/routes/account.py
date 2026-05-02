# SPDX-License-Identifier: Apache-2.0
"""Account-pool routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from noeticbraid_backend.api.deps import require_bearer
from noeticbraid_backend.auth.token_store import TokenRecord
from noeticbraid_backend.contracts import AccountPoolDraft

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account/pool", response_model=AccountPoolDraft, summary="Account pool draft state")
async def account_pool(_token: TokenRecord = Depends(require_bearer)) -> AccountPoolDraft:
    """Return a v1.0.0 account-pool fixture without profile_records."""

    return AccountPoolDraft(profiles=[])
