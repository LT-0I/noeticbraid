from __future__ import annotations

import notebooklm

from conftest import load_fixture, pool_from_config_doc, read_json


def _single_pool(fixtures_dir, tmp_path, fake_clock, *, state_doc=None):
    return pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock, state_doc=state_doc)


def test_unknown_exception_does_not_rotate(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", KeyError("x")) is False
    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]

    assert state["consecutive_failures"] == 1
    assert state["cool_down_until"] is None


def test_captcha_substring_in_other_error_triggers_captcha_cooldown(fixtures_dir, tmp_path, fake_clock):
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock)

    assert pool.mark_failure("test-alice", ValueError("captcha required")) is True
    state = read_json(tmp_path / "pool-state.json")["accounts"]["test-alice"]

    assert state["last_captcha_at"] == fake_clock().isoformat()
    assert state["cool_down_until"] is not None


def test_notebook_not_found_does_not_change_state(fixtures_dir, tmp_path, fake_clock):
    state_doc = {
        "version": 1,
        "updated_at": fake_clock().isoformat(),
        "accounts": {
            "test-alice": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "consecutive_failures": 0}
        },
    }
    pool = _single_pool(fixtures_dir, tmp_path, fake_clock, state_doc=state_doc)
    before = (tmp_path / "pool-state.json").read_text(encoding="utf-8")

    assert pool.mark_failure("test-alice", notebooklm.NotebookNotFoundError("nb1")) is False

    assert (tmp_path / "pool-state.json").read_text(encoding="utf-8") == before
