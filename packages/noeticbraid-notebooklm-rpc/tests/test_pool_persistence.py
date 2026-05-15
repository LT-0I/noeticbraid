from __future__ import annotations

import os

import pytest

from conftest import copy_fixture, load_fixture, pool_from_config_doc, read_json, write_json
from noeticbraid.tools.notebooklm_rpc import NotebookLMAccountPool, NotebookLMPoolStateError


def test_state_round_trip(fixtures_dir, tmp_path, fake_clock):
    pool = pool_from_config_doc(
        load_fixture(fixtures_dir, "pool_config_multi.json"),
        tmp_path,
        fake_clock,
        state_doc=load_fixture(fixtures_dir, "pool_state_warm.json"),
    )
    saved = read_json(tmp_path / "pool-state.json")
    restored = pool._state_from_doc(saved)

    assert restored["test-alice"].last_success_at.isoformat() == "2026-05-14T11:30:00+00:00"
    assert restored["test-bob"].used_today == 0
    assert restored["test-carol"].quota_reset_at.isoformat() == "2026-05-15T00:00:00+00:00"


def test_state_atomic_write(fixtures_dir, tmp_path, fake_clock, monkeypatch):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    with pool._lock:
        pool._persist_state_atomic()
    state_path = tmp_path / "pool-state.json"
    before = state_path.read_text(encoding="utf-8")

    def boom(src, dst):
        raise RuntimeError("replace failed")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(NotebookLMPoolStateError):
        pool.mark_success("test-alice")

    assert state_path.read_text(encoding="utf-8") == before
    assert list(tmp_path.glob("pool-state.json.tmp.*")) == []


def test_invalid_state_json_raises_pool_state_error(fixtures_dir, tmp_path):
    config_path = copy_fixture(fixtures_dir, tmp_path, "pool_config_single.json")
    state_path = tmp_path / "bad-state.json"
    state_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(NotebookLMPoolStateError):
        NotebookLMAccountPool.from_config(config_path, state_path=state_path)


def test_invalid_config_json_raises_pool_state_error(tmp_path):
    config_path = tmp_path / "pool.json"
    write_json(config_path, {"version": 1, "accounts": []})

    with pytest.raises(NotebookLMPoolStateError):
        NotebookLMAccountPool.from_config(config_path, state_path=tmp_path / "state.json")
