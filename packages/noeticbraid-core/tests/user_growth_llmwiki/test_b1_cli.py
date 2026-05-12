from __future__ import annotations

from pathlib import Path

from noeticbraid_core.user_growth_llmwiki.cli import main
from noeticbraid_core.user_growth_llmwiki.tracked_project import ProjectCandidate, save_registry


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _configure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_TRACKED_PROJECTS_PATH", str(tmp_path / "state" / "tracked_projects.json"))
    monkeypatch.setenv("NOETICBRAID_B1_CANDIDATE_QUEUE", str(tmp_path / "state" / "b1-detector.json"))


def _seed_confirmed() -> None:
    save_registry([ProjectCandidate(project_ref="Project Alpha", project_name="Project Alpha", aliases=["Alpha"], status="confirmed")])


def test_b1_cli_runs_detector(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    _seed_confirmed()
    vault = tmp_path / "vault"
    _write(vault / "Daily" / "2026-05-09.md", "[[Project Alpha]]\n")
    _write(vault / "Daily" / "2026-05-10.md", "[[Project Alpha]]\n")
    _write(vault / "Daily" / "2026-05-11.md", "[[Project Alpha]]\n")

    assert main(["b1-detect", str(vault)]) == 0

    out = capsys.readouterr().out
    assert "b1 candidates: 1" in out
    assert "queue:" in out


def test_b1_cli_returns_zero_when_no_trigger(tmp_path: Path, monkeypatch, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    _seed_confirmed()
    vault = tmp_path / "vault"
    _write(vault / "Daily" / "2026-05-11.md", "[[Project Alpha]]\n")

    assert main(["b1-detect", str(vault)]) == 0

    assert "b1 candidates: 0" in capsys.readouterr().out
