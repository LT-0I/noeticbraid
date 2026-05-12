from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from noeticbraid_core.schemas.side_note import SideNote, TONE_CONSTRAINT_LITERAL, USER_RESPONSE_CHANNEL_VALUES
from noeticbraid_core.user_growth_llmwiki.b1_detector import CandidateB1SideNote, run_b1_detector, run_b1_detector_with_report
from noeticbraid_core.user_growth_llmwiki.tracked_project import ProjectCandidate, save_registry

RUN_AT = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _configure(monkeypatch, tmp_path: Path) -> Path:
    registry = tmp_path / "state" / "tracked_projects.json"
    queue = tmp_path / "state" / "b1-detector.json"
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(registry))
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(queue))
    return queue


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


def test_b1_detector_main_flow(tmp_path: Path, monkeypatch) -> None:
    queue = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.project_ref == "Project Alpha"
    assert candidate.note_type == "hypothesis"
    assert candidate.confidence == "medium"
    assert candidate.tone_constraint == TONE_CONSTRAINT_LITERAL
    assert set(candidate.user_response_channel) == set(USER_RESPONSE_CHANNEL_VALUES)
    assert all(ref.rsplit(":", 1)[-1].isdigit() for ref in candidate.evidence_source)
    rows = json.loads(queue.read_text(encoding="utf-8"))
    assert rows[0]["candidate_type"] == "b1_sidenote"


def test_b1_candidate_writes_to_queue_not_vault(tmp_path: Path, monkeypatch) -> None:
    queue = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)
    before = _snapshot(vault)

    candidates = run_b1_detector(vault, RUN_AT)

    assert candidates
    assert queue.exists()
    assert _snapshot(vault) == before


def test_trigger_threshold_three(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _write(vault / "Daily" / "2026-05-13.md", "Mention [[Project Alpha]].\n")
    _write(vault / "Daily" / "2026-05-14.md", "Mention [[Project Alpha]].\n")

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "below_threshold:2/3"


def test_window_fourteen_days(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _write(vault / "Daily" / "2026-04-30.md", "Old mention [[Project Alpha]].\n")
    _write(vault / "Daily" / "2026-05-13.md", "Mention [[Project Alpha]].\n")
    _write(vault / "Daily" / "2026-05-14.md", "Mention [[Project Alpha]].\n")

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "below_threshold:2/3"


def test_same_day_dedup(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _write(
        vault / "Daily" / "2026-05-14.md",
        "Mention [[Project Alpha]].\nMention [[Project Alpha]] again.\nAlias Alpha too.\n",
    )

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "below_threshold:1/3"


def test_cooldown_one_per_window(tmp_path: Path, monkeypatch) -> None:
    queue = _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _three_day_mentions(vault)

    first = run_b1_detector(vault, RUN_AT)
    second = run_b1_detector_with_report(vault, RUN_AT)

    assert len(first) == 1
    assert second.candidates == []
    assert second.skip_reasons["Project Alpha"] == "cooldown"
    assert len(json.loads(queue.read_text(encoding="utf-8"))) == 1


def test_candidate_transforms_to_sidenote_passing_validation() -> None:
    """R1 architectural test: candidate transforms to a D1-01 v2-valid SideNote."""

    candidate = CandidateB1SideNote(
        candidate_id="note_candidate_test_1",
        project_ref="Projects/test-project",
        window_id="2026-05-01..2026-05-15",
        evidence_source=["2026-05-10.md:42", "2026-05-08.md:18", "2026-05-05.md:11"],
        note_type="hypothesis",
        claim="test claim from candidate",
        confidence="medium",
        tone_constraint=TONE_CONSTRAINT_LITERAL,
        user_response_channel=list(USER_RESPONSE_CHANNEL_VALUES),
        created_at="2026-05-15T12:00:00Z",
        mention_count_same_day_dedup=3,
        progress_checks={
            "mtime_unchanged": True,
            "no_new_done": True,
            "no_new_response": True,
        },
    )

    sidenote = candidate.to_sidenote(note_id="note_test_1", claim="test claim")

    assert sidenote.note_id == "note_test_1"
    assert sidenote.claim == "test claim"
    assert sidenote.evidence_source == sidenote.linked_source_refs
    SideNote.model_validate(sidenote.model_dump())


def test_window_boundary_exactly_fourteen_days_inclusive(tmp_path: Path, monkeypatch) -> None:
    """G3 edge case: mention exactly at window start (RUN_AT - 14 days) is included."""

    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed("Projects/test-project")
    _write(vault / "Daily" / "2026-05-01.md", "Mention [[Projects/test-project]].\n")
    _write(vault / "Daily" / "2026-05-10.md", "Mention [[Projects/test-project]].\n")
    _write(vault / "Daily" / "2026-05-12.md", "Mention [[Projects/test-project]].\n")

    candidates = run_b1_detector(vault_path=vault, run_timestamp_utc=RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].project_ref == "Projects/test-project"
