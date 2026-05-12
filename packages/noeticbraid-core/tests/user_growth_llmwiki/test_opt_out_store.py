from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from noeticbraid_core.schemas.side_note_opt_out import SideNoteOptOutState
from noeticbraid_core.user_growth_llmwiki.opt_out_store import load_opt_out_state, save_opt_out_state

NOW = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def test_json_load_save_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = SideNoteOptOutState(disabled_note_types=["fact"], paused=True, last_updated=NOW)

    save_opt_out_state(state, path)
    loaded = load_opt_out_state(path)

    assert loaded.disabled_note_types == ["fact"]
    assert loaded.paused is True
    assert loaded.last_updated == NOW


def test_env_override_path(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "env-state.json"
    monkeypatch.setenv("NOETICBRAID_SIDE_NOTE_OPT_OUT_PATH", str(path))

    save_opt_out_state(SideNoteOptOutState(throttled_note_types=["hypothesis"], last_updated=NOW))
    loaded = load_opt_out_state()

    assert path.exists()
    assert loaded.throttled_note_types == ["hypothesis"]


def test_corrupted_file_logs_and_returns_default_permissive(tmp_path: Path, caplog) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        state = load_opt_out_state(path)

    assert state.paused is False
    assert state.disabled_note_types == []
    assert state.throttled_note_types == []
    assert "permissive default" in caplog.text
