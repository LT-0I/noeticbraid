from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from noeticbraid_core.schemas.side_note_opt_out import RebutRecord, SideNoteOptOutState
from noeticbraid_core.user_growth_llmwiki.b1_detector import run_b1_detector_with_report
from noeticbraid_core.user_growth_llmwiki.cli import main
from noeticbraid_core.user_growth_llmwiki.opt_out_store import load_opt_out_state, save_opt_out_state
from noeticbraid_core.user_growth_llmwiki.tracked_project import ProjectCandidate, save_registry

RUN_AT = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    registry = tmp_path / "state" / "tracked_projects.json"
    queue = tmp_path / "state" / "b1-detector.json"
    opt_out = tmp_path / "state" / "side_note_opt_out.json"
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(registry))
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(queue))
    monkeypatch.setenv("NOETICBRAID_SIDE_NOTE_OPT_OUT_PATH", str(opt_out))
    return queue, opt_out


def _seed_confirmed(project_ref: str = "Project Alpha") -> None:
    save_registry(
        [
            ProjectCandidate(
                project_ref=project_ref,
                project_name=project_ref.split("/")[-1],
                aliases=[project_ref.split("/")[-1], "Alpha"],
                status="confirmed",
            )
        ]
    )


def _three_day_mentions(vault: Path, project_ref: str = "Project Alpha") -> None:
    _write(vault / "Daily" / "2026-05-12.md", f"Mention [[{project_ref}]].\n")
    _write(vault / "Daily" / "2026-05-13.md", f"Mention [[{project_ref}]].\n")
    _write(vault / "Daily" / "2026-05-14.md", f"Mention [[{project_ref}]].\n")


def _queue_row(created_at: str) -> dict[str, object]:
    return {
        "candidate_type": "b1_sidenote",
        "candidate_id": "note_existing_opt_out",
        "project_ref": "Project Alpha",
        "window_id": "2026-04-10..2026-04-24",
        "detector_policy_version": "b1_detector_v1",
        "evidence_source": ["Daily/2026-04-22.md:1", "Daily/2026-04-23.md:1", "Daily/2026-04-24.md:1"],
        "note_type": "hypothesis",
        "claim": "existing",
        "confidence": "medium",
        "tone_constraint": "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal",
        "user_response_channel": ["accept", "rebut", "mark_inaccurate", "disable_this_type"],
        "user_response": "unread",
        "created_at": created_at,
        "mention_count_same_day_dedup": 3,
        "progress_checks": {"mtime_unchanged": True, "no_new_done": True, "no_new_response": True},
        "cooldown_decision": "not_existing_in_window",
        "source_refs_only": True,
    }


def _three_recent_rebuts() -> list[RebutRecord]:
    return [
        RebutRecord(note_id=f"note_rebut_{index}", note_type="hypothesis", timestamp=RUN_AT - timedelta(days=index + 1))
        for index in range(3)
    ]


def test_b1_detector_paused_exit_early(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    save_opt_out_state(SideNoteOptOutState(paused=True, last_updated=RUN_AT))

    report = run_b1_detector_with_report(tmp_path / "vault", RUN_AT)

    assert report.paused is True
    assert report.candidates == []
    assert report.skip_reasons == {"__opt_out__": "paused"}


def test_b1_detector_disabled_note_type_skipped(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)
    save_opt_out_state(SideNoteOptOutState(disabled_note_types=["hypothesis"], last_updated=RUN_AT))

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "opt_out_disabled:hypothesis"


def test_b1_detector_throttle_extends_cooldown_30d(tmp_path: Path, monkeypatch) -> None:
    queue, _opt_out = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(json.dumps([_queue_row("2026-04-25T12:00:00Z")]), encoding="utf-8")
    save_opt_out_state(
        SideNoteOptOutState(
            throttled_note_types=["hypothesis"],
            rebut_history=_three_recent_rebuts(),
            last_updated=RUN_AT,
        )
    )

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "cooldown"


def test_accept_resets_rebut_counter_per_note_type(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    save_opt_out_state(
        SideNoteOptOutState(
            throttled_note_types=["hypothesis"],
            rebut_history=_three_recent_rebuts(),
            last_updated=RUN_AT,
        )
    )

    assert main(["b1-accept", "--note-id=note_any", "--note-type=hypothesis"]) == 0
    state = load_opt_out_state()

    assert state.rebut_history == []
    assert "hypothesis" not in state.throttled_note_types


def test_mark_inaccurate_does_not_count(tmp_path: Path, monkeypatch) -> None:
    _queue, opt_out = _configure(monkeypatch, tmp_path)

    assert main(["b1-mark-inaccurate", "--note-id=note_any", "--note-type=hypothesis"]) == 0

    assert not opt_out.exists()


def test_throttle_auto_clears_when_rolling_window_drops_below_threshold(tmp_path: Path, monkeypatch) -> None:
    queue, _opt_out = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(json.dumps([_queue_row("2026-04-25T12:00:00Z")]), encoding="utf-8")
    save_opt_out_state(
        SideNoteOptOutState(
            throttled_note_types=["hypothesis"],
            rebut_history=[
                RebutRecord(note_id="note_recent_1", note_type="hypothesis", timestamp=RUN_AT - timedelta(days=1)),
                RebutRecord(note_id="note_recent_2", note_type="hypothesis", timestamp=RUN_AT - timedelta(days=2)),
                RebutRecord(note_id="note_old", note_type="hypothesis", timestamp=RUN_AT - timedelta(days=31)),
            ],
            last_updated=RUN_AT,
        )
    )

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert len(report.candidates) == 1
    assert load_opt_out_state().throttled_note_types == []


def test_b1_detector_corrupt_opt_out_state_logs_error_and_runs_permissive(tmp_path: Path, monkeypatch, caplog) -> None:
    _queue, opt_out = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)
    opt_out.parent.mkdir(parents=True, exist_ok=True)
    opt_out.write_text("{bad json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        report = run_b1_detector_with_report(vault, RUN_AT)

    assert len(report.candidates) == 1
    assert "permissive default" in caplog.text
