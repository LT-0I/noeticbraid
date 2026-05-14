from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import load_fixture, pool_from_config_doc
from noeticbraid.tools.notebooklm_rpc import INELIGIBILITY_REASONS, NotebookLMAccountUnavailableError


def test_ineligibility_reason_all_quota_exhausted(fixtures_dir, tmp_path, fake_clock):
    config = load_fixture(fixtures_dir, "pool_config_multi.json")
    state = load_fixture(fixtures_dir, "pool_state_warm.json")
    for account in state["accounts"].values():
        account["used_today"] = 3
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        pool.pick()

    assert exc_info.value.reason == "all_quota_exhausted"


def test_ineligibility_reason_mixed(fixtures_dir, tmp_path, fake_clock):
    config = load_fixture(fixtures_dir, "pool_config_multi.json")
    config["accounts"] = config["accounts"][:2]
    state = load_fixture(fixtures_dir, "pool_state_warm.json")
    state["accounts"] = {key: state["accounts"][key] for key in ["test-alice", "test-bob"]}
    state["accounts"]["test-alice"]["used_today"] = 3
    state["accounts"]["test-bob"]["last_429_at"] = fake_clock().isoformat()
    state["accounts"]["test-bob"]["cool_down_until"] = (fake_clock() + timedelta(minutes=30)).isoformat()
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        pool.pick()

    assert exc_info.value.reason == "mixed"


def test_ineligibility_reason_all_excluded(fixtures_dir, tmp_path, fake_clock):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_multi.json"), tmp_path, fake_clock)

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        pool.pick(exclude=frozenset({"test-alice", "test-bob", "test-carol"}))

    assert exc_info.value.reason == "all_excluded"


def test_INELIGIBILITY_REASONS_set_matches_spec():
    assert INELIGIBILITY_REASONS == frozenset(
        {
            "all_rate_limited",
            "all_login_required",
            "all_captcha",
            "all_server_error_streak",
            "all_quota_exhausted",
            "all_excluded",
            "mixed",
            "pool_empty",
        }
    )
