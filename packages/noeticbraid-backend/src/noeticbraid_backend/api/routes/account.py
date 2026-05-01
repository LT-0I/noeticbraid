# SPDX-License-Identifier: Apache-2.0
"""Account-pool route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import AccountPoolDraft

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account/pool", response_model=AccountPoolDraft, summary="Account pool draft state")
async def account_pool() -> AccountPoolDraft:
    """Return a v1.0.0 account-pool fixture without profile_records."""

    return AccountPoolDraft(profiles=[])
