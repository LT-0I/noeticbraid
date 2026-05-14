from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import load_fixture, pool_from_config_doc
from noeticbraid.tools.notebooklm_rpc import INELIGIBILITY_REASONS, NotebookLMAccountUnavailableError


def test_pick_single_account_eligible(fixtures_dir, tmp_path, fake_clock):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)

    picked = pool.pick()

    assert picked.account_id == "test-alice"
    assert picked.label == "Test Alice"


def test_pick_multi_lru_tie_break(tmp_path, fake_clock):
    config = {
        "version": 1,
        "accounts": [
            {"account_id": "acct-c", "storage_state_path": "/tmp/c.json"},
            {"account_id": "acct-a", "storage_state_path": "/tmp/a.json"},
            {"account_id": "acct-b", "storage_state_path": "/tmp/b.json"},
        ],
    }
    state = {
        "version": 1,
        "updated_at": fake_clock().isoformat(),
        "accounts": {
            "acct-a": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "last_success_at": "2026-05-14T11:59:00+00:00", "consecutive_failures": 0},
            "acct-b": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "last_success_at": None, "consecutive_failures": 0},
            "acct-c": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "last_success_at": None, "consecutive_failures": 0},
        },
    }
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    assert pool.pick().account_id == "acct-b"


def test_pick_excludes_cool_down(fixtures_dir, tmp_path, fake_clock):
    pool = pool_from_config_doc(
        load_fixture(fixtures_dir, "pool_config_multi.json"),
        tmp_path,
        fake_clock,
        state_doc=load_fixture(fixtures_dir, "pool_state_cooldown.json"),
    )

    assert pool.pick().account_id == "test-bob"


def test_pick_excludes_quota_exhausted(fixtures_dir, tmp_path, fake_clock):
    config = load_fixture(fixtures_dir, "pool_config_multi.json")
    state = load_fixture(fixtures_dir, "pool_state_warm.json")
    state["accounts"]["test-carol"]["used_today"] = 3
    state["accounts"]["test-bob"]["last_success_at"] = "2026-05-14T11:59:00+00:00"
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    assert pool.pick().account_id == "test-alice"


def test_pick_all_rate_limited_raises(fixtures_dir, tmp_path, fake_clock):
    config = load_fixture(fixtures_dir, "pool_config_multi.json")
    state = load_fixture(fixtures_dir, "pool_state_warm.json")
    for account in state["accounts"].values():
        account["last_429_at"] = fake_clock().isoformat()
        account["cool_down_until"] = (fake_clock() + timedelta(minutes=30)).isoformat()
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        pool.pick()

    assert exc_info.value.reason == "all_rate_limited"
    assert exc_info.value.reason in INELIGIBILITY_REASONS


def test_pick_respects_exclude_set(fixtures_dir, tmp_path, fake_clock):
    pool = pool_from_config_doc(
        load_fixture(fixtures_dir, "pool_config_multi.json"),
        tmp_path,
        fake_clock,
        state_doc=load_fixture(fixtures_dir, "pool_state_warm.json"),
    )

    assert pool.pick(exclude=frozenset({"test-carol"})).account_id == "test-bob"
