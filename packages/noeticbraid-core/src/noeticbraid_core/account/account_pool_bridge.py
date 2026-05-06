# SPDX-License-Identifier: Apache-2.0
"""Bridge helpers for the frozen AccountPoolDraft wrapper.

The frozen contract exposes only a top-level `profiles` list. These helpers keep all
module-local account/quota/session details inside sanitized profile objects or private
state files; they never add top-level fields such as quota_state or session_health.
"""

from __future__ import annotations

from typing import Any

from noeticbraid_core.account.store import AccountQuotaStore


def to_account_pool_profiles(store: AccountQuotaStore) -> list[dict[str, Any]]:
    """Return sanitized profile dicts suitable for AccountPoolDraft(profiles=...)."""

    return [
        summary.model_dump(mode="json", exclude_none=True)
        for summary in store.public_profile_summaries()
    ]


def build_account_pool_payload(store: AccountQuotaStore) -> dict[str, list[dict[str, Any]]]:
    """Return the exact frozen wrapper payload shape: {"profiles": [...]} ."""

    return {"profiles": to_account_pool_profiles(store)}


__all__ = ["build_account_pool_payload", "to_account_pool_profiles"]
