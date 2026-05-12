from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from noeticbraid_core.r6_gate import R6_GATE_DEFAULT_TTL_DAYS, R6GateState, evaluate_r6_gate
from noeticbraid_core.user_growth_llmwiki.b1_detector import run_b1_detector_with_report
from noeticbraid_core.user_growth_llmwiki.cli import main
from noeticbraid_core.user_growth_llmwiki.tracked_project import ProjectCandidate, approve, auto_discover, load_registry, save_registry

RUN_AT = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(tmp_path / "state" / "tracked_projects.json"))
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(tmp_path / "state" / "b1-detector.json"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_tracked_project_embeds_gate(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _write(vault / "a.md", "[[Projects/Alpha]]\n")
    _write(vault / "b.md", "[[Projects/Alpha]]\n")
    _write(vault / "c.md", "[[Projects/Alpha]]\n")

    [candidate] = auto_discover(vault)

    assert candidate.r6_gate is not None
    assert candidate.r6_gate.reuse_count == 0
    assert candidate.r6_gate.ledger_evidence_refs == []
    created = datetime.fromisoformat(candidate.created_at.replace("Z", "+00:00"))
    assert candidate.r6_gate.expires_at == created + timedelta(days=R6_GATE_DEFAULT_TTL_DAYS)
    record = candidate.to_record()
    assert record["r6_gate"]["r6_gate_schema_version"] == "1.0.0"
    round_tripped = ProjectCandidate.from_record(record)
    assert round_tripped.r6_gate == candidate.r6_gate


def test_b1_approve_sets_adopted_at(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    save_registry(
        [
            ProjectCandidate(
                project_ref="Projects/Alpha",
                project_name="Alpha",
                status="candidate",
                r6_gate=R6GateState(expires_at=RUN_AT + timedelta(days=1)),
            )
        ]
    )

    approve("Projects/Alpha")

    [candidate] = load_registry()
    assert candidate.status == "confirmed"
    assert candidate.r6_gate is not None
    assert candidate.r6_gate.adopted_at is not None
    assert evaluate_r6_gate(candidate.r6_gate, now=RUN_AT) == "confirmed"


def test_expired_project_skipped_by_detector(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _write(vault / "Daily" / "2026-05-13.md", "[[Projects/Alpha]]\n")
    _write(vault / "Daily" / "2026-05-14.md", "[[Projects/Alpha]]\n")
    _write(vault / "Daily" / "2026-05-15.md", "[[Projects/Alpha]]\n")
    save_registry(
        [
            ProjectCandidate(
                project_ref="Projects/Alpha",
                project_name="Alpha",
                status="candidate",
                r6_gate=R6GateState(expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc)),
            )
        ]
    )

    assert main(["b1-detect", str(vault)]) == 0

    [candidate] = load_registry()
    assert candidate.status == "expired"
    queue = tmp_path / "state" / "b1-detector.json"
    assert not queue.exists()


def test_expired_project_cleanup_runs_for_detector_library_callers(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _write(vault / "Daily" / "2026-05-13.md", "[[Projects/Alpha]]\n")
    _write(vault / "Daily" / "2026-05-14.md", "[[Projects/Alpha]]\n")
    _write(vault / "Daily" / "2026-05-15.md", "[[Projects/Alpha]]\n")
    save_registry(
        [
            ProjectCandidate(
                project_ref="Projects/Alpha",
                project_name="Alpha",
                status="candidate",
                r6_gate=R6GateState(expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc)),
            )
        ]
    )

    report = run_b1_detector_with_report(vault, RUN_AT)

    [candidate] = load_registry()
    assert candidate.status == "expired"
    assert report.candidates == []
    assert not (tmp_path / "state" / "b1-detector.json").exists()


def test_gate_cleanup_cli_marks_expired(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    save_registry(
        [
            ProjectCandidate(
                project_ref="Projects/Alpha",
                project_name="Alpha",
                status="candidate",
                r6_gate=R6GateState(expires_at=datetime(2000, 1, 1, tzinfo=timezone.utc)),
            )
        ]
    )

    assert main(["b1-gate-cleanup"]) == 0

    [candidate] = load_registry()
    assert candidate.status == "expired"
    assert "expired tracked_project candidates: 1" in capsys.readouterr().out
