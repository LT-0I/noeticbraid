from __future__ import annotations

from datetime import timedelta

import notebooklm
import pytest

from conftest import FakeNotebookLMClient, load_fixture, pool_from_config_doc, read_json
from noeticbraid.tools.notebooklm_rpc import account_op


def _single_pool(fixtures_dir, tmp_path, fake_clock):
    config = load_fixture(fixtures_dir, "pool_config_single.json")
    return pool_from_config_doc(config, tmp_path, fake_clock)


def test_login_required_cooldown_12h(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", notebooklm.AuthError("login")) is True
    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]

    assert state["last_login_required_at"] == fake_clock().isoformat()
    assert state["cool_down_until"] == (fake_clock() + timedelta(seconds=43200)).isoformat()


def test_rate_limited_cooldown_1h(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", notebooklm.RateLimitError("rate")) is True
    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]

    assert state["last_429_at"] == fake_clock().isoformat()
    assert state["cool_down_until"] == (fake_clock() + timedelta(seconds=3600)).isoformat()


def test_captcha_substring_detection(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", ValueError("Captcha required")) is True
    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]

    assert state["last_captcha_at"] == fake_clock().isoformat()
    assert state["cool_down_until"] == (fake_clock() + timedelta(seconds=86400)).isoformat()


def test_server_error_streak_3_triggers_cooldown(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", notebooklm.ServerError("500")) is False
    assert pool.mark_failure("test-alice", notebooklm.ServerError("500")) is False
    assert read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]["cool_down_until"] is None
    assert pool.mark_failure("test-alice", notebooklm.ServerError("500")) is True

    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]
    assert state["consecutive_failures"] == 3
    assert state["cool_down_until"] == (fake_clock() + timedelta(seconds=1800)).isoformat()


async def test_not_found_does_not_change_state(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = pool_from_config_doc(
        load_fixture(fixtures_dir, "pool_config_single.json"),
        tmp_path,
        fake_clock,
        state_doc={
            "version": 1,
            "updated_at": fake_clock().isoformat(),
            "accounts": {
                "test-alice": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "consecutive_failures": 0}
            },
        },
    )
    before = (tmp_path / "pool-state.json").read_text(encoding="utf-8")
    patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))

    with pytest.raises(notebooklm.NotebookNotFoundError):
        async with account_op(pool) as (_client, _account_id):
            raise notebooklm.NotebookNotFoundError("nb1")

    assert (tmp_path / "pool-state.json").read_text(encoding="utf-8") == before
