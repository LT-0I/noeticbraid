from __future__ import annotations

from datetime import datetime, timezone

from conftest import load_fixture, pool_from_config_doc, read_json


def test_quota_reset_utc_midnight(fixtures_dir, tmp_path, fake_clock):
    fake_clock.now = datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)
    config = load_fixture(fixtures_dir, "pool_config_single.json")
    state = {
        "version": 1,
        "updated_at": "2026-05-14T12:00:00+00:00",
        "accounts": {
            "test-alice": {"used_today": 5, "quota_reset_at": "2026-05-15T00:00:00+00:00", "consecutive_failures": 0}
        },
    }
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    pool.pick()
    status = pool.status()["accounts"][0]

    assert status["used_today"] == 0
    assert status["quota_reset_at"] == "2026-05-16T00:00:00+00:00"


def test_quota_reset_asia_shanghai_tz(tmp_path, fake_clock):
    config = {
        "version": 1,
        "accounts": [
            {"account_id": "test-asia", "storage_state_path": "/tmp/asia.json", "quota_reset_tz": "Asia/Shanghai"}
        ],
    }
    pool = pool_from_config_doc(config, tmp_path, fake_clock)

    pool.pick()

    assert pool.status()["accounts"][0]["quota_reset_at"] == "2026-05-14T16:00:00+00:00"


def test_quota_reset_persists(fixtures_dir, tmp_path, fake_clock):
    fake_clock.now = datetime(2026, 5, 15, 0, 1, 0, tzinfo=timezone.utc)
    config = load_fixture(fixtures_dir, "pool_config_single.json")
    state = {
        "version": 1,
        "updated_at": "2026-05-14T12:00:00+00:00",
        "accounts": {
            "test-alice": {"used_today": 5, "quota_reset_at": "2026-05-15T00:00:00+00:00", "consecutive_failures": 0}
        },
    }
    pool = pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state)

    pool.pick()
    written = read_json(tmp_path / "pool-state.json")

    assert written["accounts"]["test-alice"]["used_today"] == 0
    assert written["accounts"]["test-alice"]["quota_reset_at"] == "2026-05-16T00:00:00+00:00"
