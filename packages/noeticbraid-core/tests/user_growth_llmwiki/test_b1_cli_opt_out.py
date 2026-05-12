from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from noeticbraid_core.schemas.side_note_opt_out import RebutRecord, SideNoteOptOutState
from noeticbraid_core.user_growth_llmwiki.cli import build_parser, main
from noeticbraid_core.user_growth_llmwiki.opt_out_store import load_opt_out_state, save_opt_out_state

NOW = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def _configure(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "state" / "side_note_opt_out.json"
    monkeypatch.setenv("NOETICBRAID_SIDE_NOTE_OPT_OUT_PATH", str(path))
    return path


def _three_rebuts() -> list[RebutRecord]:
    return [
        RebutRecord(note_id=f"note_{index}", note_type="hypothesis", timestamp=NOW - timedelta(days=index))
        for index in range(3)
    ]


def test_b1_cli_opt_out(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)

    assert main(["b1-opt-out", "--note-type=hypothesis"]) == 0

    assert load_opt_out_state().disabled_note_types == ["hypothesis"]


def test_b1_cli_rebut_increments(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)

    assert main(["b1-rebut", "--note-id=free_form_note", "--note-type=hypothesis"]) == 0
    assert main(["b1-rebut", "--note-id=free_form_note", "--note-type=hypothesis"]) == 0
    assert main(["b1-rebut", "--note-id=another_free_form_note", "--note-type=hypothesis"]) == 0
    assert main(["b1-rebut", "--note-id=third_free_form_note", "--note-type=hypothesis"]) == 0
    state = load_opt_out_state()

    assert [(record.note_id, record.note_type) for record in state.rebut_history] == [
        ("free_form_note", "hypothesis"),
        ("another_free_form_note", "hypothesis"),
        ("third_free_form_note", "hypothesis"),
    ]
    assert state.throttled_note_types == ["hypothesis"]


def test_b1_cli_accept_resets_rebut_counter(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    save_opt_out_state(
        SideNoteOptOutState(
            rebut_history=_three_rebuts(),
            throttled_note_types=["hypothesis"],
            last_updated=NOW,
        )
    )

    assert main(["b1-accept", "--note-id=note_accepted", "--note-type=hypothesis"]) == 0
    state = load_opt_out_state()

    assert state.rebut_history == []
    assert state.throttled_note_types == []


def test_b1_cli_mark_inaccurate_does_not_count(tmp_path: Path, monkeypatch) -> None:
    path = _configure(monkeypatch, tmp_path)

    assert main(["b1-mark-inaccurate", "--note-id=note_any", "--note-type=hypothesis"]) == 0

    assert not path.exists()


def test_b1_cli_pause(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)

    assert main(["b1-pause"]) == 0

    assert load_opt_out_state().paused is True


def test_b1_cli_resume(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    save_opt_out_state(SideNoteOptOutState(paused=True, throttled_note_types=["hypothesis"], last_updated=NOW))

    assert main(["b1-resume"]) == 0
    state = load_opt_out_state()
    assert state.paused is False
    assert state.throttled_note_types == ["hypothesis"]

    with pytest.raises(SystemExit):
        build_parser().parse_args(["b1-resume", "--help"])
    help_out = capsys.readouterr().out
    assert "does NOT clear" in help_out
    assert "throttled_note_types" in help_out
