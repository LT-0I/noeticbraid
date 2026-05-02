# SPDX-License-Identifier: Apache-2.0
"""Account-pool routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from noeticbraid_backend.account_quota.store import AccountQuotaStore, AccountQuotaStoreError
from noeticbraid_backend.api.deps import get_settings, require_bearer
from noeticbraid_backend.auth.token_store import TokenRecord
from noeticbraid_backend.contracts import AccountPoolDraft
from noeticbraid_backend.settings import Settings

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account/pool", response_model=AccountPoolDraft, summary="Account pool draft state")
async def account_pool(
    _token: TokenRecord = Depends(require_bearer),
    settings: Settings = Depends(get_settings),
) -> AccountPoolDraft:
    """Return sanitized quota summaries without changing the frozen wrapper."""

    store = AccountQuotaStore.from_settings(settings)
    try:
        profiles = [summary.model_dump(mode="json") for summary in store.public_profile_summaries()]
    except AccountQuotaStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="account_quota_state_unavailable",
        ) from exc
    return AccountPoolDraft(profiles=profiles)
