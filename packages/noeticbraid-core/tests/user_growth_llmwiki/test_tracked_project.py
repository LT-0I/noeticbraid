from __future__ import annotations

import json
from pathlib import Path

from noeticbraid_core.user_growth_llmwiki.cli import main
from noeticbraid_core.user_growth_llmwiki.tracked_project import ProjectCandidate, approve, auto_discover, load_registry, save_registry


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(tmp_path / "state" / "tracked_projects.json"))


def _write_queue_entry(queue_path: Path, entry: dict[str, object]) -> None:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps([entry], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_queue(queue_path: Path) -> list[dict[str, object]]:
    return json.loads(queue_path.read_text(encoding="utf-8"))


def test_auto_discovery_to_candidate(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    vault = tmp_path / "vault"
    _write(vault / "a.md", "[[Projects/Alpha]]\n")
    _write(vault / "b.md", "[[Projects/Alpha]]\n")
    _write(vault / "c.md", "[[Projects/Alpha]]\n")

    candidates = auto_discover(vault)

    assert [candidate.project_ref for candidate in candidates] == ["Projects/Alpha"]
    assert candidates[0].status == "candidate"
    assert load_registry()[0].candidate_type == "tracked_project"


def test_user_approval_confirmed(tmp_path: Path, monkeypatch) -> None:
    _configure(monkeypatch, tmp_path)
    save_registry([ProjectCandidate(project_ref="Projects/Alpha", project_name="Alpha", status="candidate")])

    approve("Projects/Alpha")

    assert load_registry()[0].status == "confirmed"


def test_cli_approve(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    save_registry([ProjectCandidate(project_ref="Projects/Alpha", project_name="Alpha", status="candidate")])

    assert main(["b1-approve", "Projects/Alpha"]) == 0

    assert load_registry()[0].status == "confirmed"
    assert "confirmed: Projects/Alpha" in capsys.readouterr().out


def test_cli_unconfirm(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    queue_path = tmp_path / "state" / "b1-detector.json"
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(queue_path))
    sample_candidate = {
        "candidate_id": "note_candidate_queue_1",
        "candidate_type": "b1_sidenote",
        "project_ref": "Projects/Alpha",
        "evidence_source": ["Daily/2026-05-10.md:1"],
        "created_at": "2026-05-15T12:00:00Z",
    }
    _write_queue_entry(queue_path, sample_candidate)
    save_registry([ProjectCandidate(project_ref="Projects/Alpha", project_name="Alpha", status="confirmed")])

    assert main(["b1-unconfirm", "Projects/Alpha"]) == 0

    assert load_registry()[0].status == "candidate"
    assert _read_queue(queue_path) == [sample_candidate]
    assert "candidate: Projects/Alpha" in capsys.readouterr().out
