from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from noeticbraid_core.schemas.side_note import SideNote, TONE_CONSTRAINT_LITERAL, USER_RESPONSE_CHANNEL_VALUES
from noeticbraid_core.schemas.side_note_opt_out import SideNoteOptOutState
from noeticbraid_core.user_growth_llmwiki.b1_detector import CandidateB1SideNote, run_b1_detector, run_b1_detector_with_report
from noeticbraid_core.user_growth_llmwiki.opt_out_store import save_opt_out_state
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
    opt_out = tmp_path / "state" / "side_note_opt_out.json"
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(registry))
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(queue))
    monkeypatch.setenv("NOETICBRAID_SIDE_NOTE_OPT_OUT_PATH", str(opt_out))
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


def _seed_confirmed_projects(project_refs: list[str]) -> None:
    save_registry(
        [
            ProjectCandidate(
                project_ref=project_ref,
                project_name=project_ref.split("/")[-1],
                aliases=[project_ref.split("/")[-1]],
                status="confirmed",
            )
            for project_ref in project_refs
        ]
    )


def _three_day_mentions(vault: Path, project_ref: str = "Project Alpha") -> None:
    _mention_days(vault, project_ref, 3)


def _mention_days(vault: Path, project_ref: str, count: int) -> None:
    for index in range(count):
        day = 14 - index
        path = vault / "Daily" / f"2026-05-{day:02d}.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        _write(path, existing + f"Mention [[{project_ref}]].\n")


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


def test_tier_hypothesis_three_day_claim_marker(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 3)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "hypothesis"
    assert candidates[0].confidence == "medium"
    assert "Hypothesis: 过去 14 天的笔记中有" in candidates[0].claim


def test_tier_action_suggestion_five_day_claim_marker(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 5)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "action_suggestion"
    assert candidates[0].confidence == "medium"
    assert "建议在本周内为" in candidates[0].claim


def test_tier_fact_seven_day_claim_marker_without_hypothesis_prefix(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 7)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "fact"
    assert candidates[0].confidence == "high"
    assert "过去 14 天的笔记中有" in candidates[0].claim
    assert "未观察到" in candidates[0].claim
    assert not candidates[0].claim.startswith("Hypothesis:")


def test_tier_boundary_four_days_stays_hypothesis(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 4)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "hypothesis"
    assert candidates[0].confidence == "medium"


def test_tier_boundary_six_days_stays_action_suggestion(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 6)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "action_suggestion"
    assert candidates[0].confidence == "medium"


def test_tier_boundary_eight_days_stays_fact(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 8)

    candidates = run_b1_detector(vault, RUN_AT)

    assert len(candidates) == 1
    assert candidates[0].note_type == "fact"
    assert candidates[0].confidence == "high"


def test_opt_out_disabled_fact_skips_fact_tier(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 7)
    save_opt_out_state(SideNoteOptOutState(disabled_note_types=["fact"], last_updated=RUN_AT))

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "opt_out_disabled:fact"


def test_opt_out_disabled_action_suggestion_skips_action_tier(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 5)
    save_opt_out_state(SideNoteOptOutState(disabled_note_types=["action_suggestion"], last_updated=RUN_AT))

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert report.candidates == []
    assert report.skip_reasons["Project Alpha"] == "opt_out_disabled:action_suggestion"


def test_opt_out_disabled_hypothesis_does_not_block_fact_tier(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _seed_confirmed()
    _mention_days(vault, "Project Alpha", 7)
    save_opt_out_state(SideNoteOptOutState(disabled_note_types=["hypothesis"], last_updated=RUN_AT))

    report = run_b1_detector_with_report(vault, RUN_AT)

    assert len(report.candidates) == 1
    assert report.candidates[0].note_type == "fact"
    assert "Project Alpha" not in report.skip_reasons


def test_claim_text_uniqueness_across_three_tiers(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    project_counts = {
        "Projects/Hypothesis": 3,
        "Projects/Action": 5,
        "Projects/Fact": 7,
    }
    _seed_confirmed_projects(list(project_counts))
    for project_ref, count in project_counts.items():
        _mention_days(vault, project_ref, count)

    candidates = run_b1_detector(vault, RUN_AT)

    by_ref = {candidate.project_ref: candidate for candidate in candidates}
    assert len(by_ref) == 3
    assert by_ref["Projects/Hypothesis"].note_type == "hypothesis"
    assert by_ref["Projects/Action"].note_type == "action_suggestion"
    assert by_ref["Projects/Fact"].note_type == "fact"
    claims = {candidate.claim for candidate in candidates}
    assert len(claims) == 3
    assert "Hypothesis: 过去 14 天的笔记中有" in by_ref["Projects/Hypothesis"].claim
    assert "建议在本周内为" in by_ref["Projects/Action"].claim
    assert "过去 14 天的笔记中有" in by_ref["Projects/Fact"].claim
