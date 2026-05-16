# SPDX-License-Identifier: Apache-2.0
"""Account-pool routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from noeticbraid_backend.account_quota.store import AccountQuotaStore, AccountQuotaStoreError
from noeticbraid_backend.api.deps import get_settings, require_bearer
from noeticbraid_backend.auth.token_store import TokenRecord
from noeticbraid_backend.contracts import AccountPoolDraft, AccountStatusDetail
from noeticbraid_backend.omc_workspace.capability_registry import (
    CAPABILITIES,
    LIVE_SUBPROCESS_TIMEOUT_SECONDS,
    _sanitize_and_truncate,
)
from noeticbraid_backend.settings import Settings
from noeticbraid_core.account.status_observer import AccountStatusRecord, observe_status

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


@router.get("/account/status", response_model=AccountStatusDetail, summary="Account status detail")
async def account_status(
    _token: TokenRecord = Depends(require_bearer),
) -> AccountStatusDetail:
    """Return sanitized read-only status for the first-batch account caps."""

    accounts = [
        AccountStatusRecord.model_validate(record).model_dump(mode="json")
        for record in observe_status(
            CAPABILITIES,
            cli_timeout_seconds=LIVE_SUBPROCESS_TIMEOUT_SECONDS,
            sanitize_message=_sanitize_and_truncate,
        )
    ]
    return AccountStatusDetail(accounts=accounts)
