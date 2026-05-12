from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from noeticbraid_core.schemas.side_note_opt_out import (
    THROTTLE_REBUT_THRESHOLD,
    THROTTLE_ROLLING_WINDOW_DAYS,
    RebutRecord,
    SideNoteOptOutState,
)
from noeticbraid_core.user_growth_llmwiki.opt_out_store import load_opt_out_state, save_opt_out_state

NOW = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def test_default_state_empty_and_not_paused() -> None:
    state = SideNoteOptOutState()

    assert state.disabled_note_types == []
    assert state.throttled_note_types == []
    assert state.rebut_history == []
    assert state.paused is False
    assert state.last_updated.tzinfo is not None
    assert state.opt_out_schema_version == "1.0.0"


def test_rebut_record_within_30d_rolling_window() -> None:
    recent = RebutRecord(note_id="note_recent", note_type="hypothesis", timestamp=NOW - timedelta(days=29))
    old = RebutRecord(note_id="note_old", note_type="hypothesis", timestamp=NOW - timedelta(days=31))
    state = SideNoteOptOutState(rebut_history=[recent, old], last_updated=NOW)

    window_start = NOW - timedelta(days=THROTTLE_ROLLING_WINDOW_DAYS)
    in_window = [record for record in state.rebut_history if window_start <= record.timestamp <= NOW]

    assert [record.note_id for record in in_window] == ["note_recent"]


def test_disable_persists_after_save_load(tmp_path: Path) -> None:
    path = tmp_path / "side_note_opt_out.json"
    state = SideNoteOptOutState(disabled_note_types=["hypothesis"], last_updated=NOW)

    save_opt_out_state(state, path)
    loaded = load_opt_out_state(path)

    assert loaded.disabled_note_types == ["hypothesis"]
    assert loaded.paused is False


def test_three_distinct_rebuts_marks_throttled() -> None:
    records = [
        RebutRecord(note_id=f"note_{index}", note_type="hypothesis", timestamp=NOW - timedelta(days=index))
        for index in range(THROTTLE_REBUT_THRESHOLD)
    ]
    distinct_note_ids = {record.note_id for record in records}
    state = SideNoteOptOutState(rebut_history=records, throttled_note_types=["hypothesis"], last_updated=NOW)

    assert len(distinct_note_ids) == THROTTLE_REBUT_THRESHOLD
    assert "hypothesis" in state.throttled_note_types


def test_resume_clears_pause_not_throttle() -> None:
    paused = SideNoteOptOutState(paused=True, throttled_note_types=["hypothesis"], last_updated=NOW)

    resumed = paused.model_copy(update={"paused": False, "last_updated": NOW + timedelta(minutes=1)})

    assert resumed.paused is False
    assert resumed.throttled_note_types == ["hypothesis"]
