from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from noeticbraid_core.account.account_pool_bridge import build_account_pool_payload, to_account_pool_profiles
from noeticbraid_core.account.models import PublicProfileSummary
from noeticbraid_core.account.store import AccountQuotaStore


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_account_pool_bridge_outputs_only_frozen_profiles_payload_shape(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    write_json(
        store.accounts_path,
        {
            "accounts": [
                {
                    "alias": "gpt-main",
                    "provider": "chatgpt",
                    "capabilities": ["chat"],
                    "browser_profile_label": "Profile 1",
                    "notes": "private",
                }
            ]
        },
    )
    write_json(store.state_path, {"gpt-main": {"status": "available", "remaining_estimate": "high"}})

    profiles = to_account_pool_profiles(store)
    payload = build_account_pool_payload(store)

    assert profiles == [
        {
            "alias": "gpt-main",
            "provider": "chatgpt",
            "status": "available",
            "remaining_estimate": "high",
            "capabilities": ["chat"],
        }
    ]
    assert payload == {"profiles": profiles}
    assert "session_health" not in payload
    assert "quota_state" not in payload
    assert "browser_profile_label" not in json.dumps(payload)


def test_public_profile_summary_frozen_mutation_raises() -> None:
    summary = PublicProfileSummary(
        alias="gpt-main",
        provider="chatgpt",
        status="available",
        remaining_estimate="high",
        capabilities=["chat"],
    )

    with pytest.raises(ValidationError):
        summary.alias = "other"
