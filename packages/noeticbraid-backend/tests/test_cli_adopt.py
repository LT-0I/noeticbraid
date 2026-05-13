# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.cli.__main__ import main
from noeticbraid_backend.omc_workspace.adoption import adopt_candidate
from noeticbraid_backend.omc_workspace.project_store import DEFAULT_UPGRADE_RULE, OMCProjectStore
from noeticbraid_core.r6_gate import R6GateState
from noeticbraid_core.schemas import CandidateLesson


class TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def _candidate(candidate_id: str) -> dict[str, object]:
    return CandidateLesson(
        candidate_id=candidate_id,
        project_id="omc-ingest",
        source_sdd_ids=["SDD-D2-01", "SDD-D2-02"],
        summary="candidate lesson for CLI adoption tests",
        status="candidate",
        upgrade_rule=DEFAULT_UPGRADE_RULE,
        adopted_at=None,
        adopted_by=None,
        run_record_ref=f"run_{candidate_id}",
        reuse_evidence_refs=[],
        artifact_refs=[f"artifact_convergence_{candidate_id}"],
        source_refs=["source_omc_metadata"],
        r6_gate=R6GateState(),
    ).model_dump(mode="json")


def _store(project_root: Path) -> OMCProjectStore:
    return OMCProjectStore(project_root / "state")


def _seed_candidate(project_root: Path, candidate_id: str) -> None:
    _store(project_root).upsert_candidate(_candidate(candidate_id))


def _stored_candidate(project_root: Path, candidate_id: str) -> CandidateLesson:
    row = _store(project_root).find_candidate(candidate_id)
    assert row is not None
    return CandidateLesson.model_validate(row)


def _run_cli(project_root: Path, candidate_id: str, *extra: str) -> int:
    return main(["omc", "adopt-candidate", candidate_id, *extra, "--project-root", str(project_root)])


def test_happy_path_yes_flag(tmp_path: Path, capsys) -> None:
    candidate_id = "memory_cli_happy_path"
    _seed_candidate(tmp_path, candidate_id)

    exit_code = _run_cli(tmp_path, candidate_id, "--yes")

    captured = capsys.readouterr()
    artifact_path = Path(captured.out.strip())
    assert exit_code == 0, captured.err
    assert artifact_path.exists()
    assert artifact_path.name.startswith(f"candidate-adoption-{candidate_id}-")
    assert "adopted_by: `cli-user`" in artifact_path.read_text(encoding="utf-8")
    stored = _stored_candidate(tmp_path, candidate_id)
    assert stored.status == "adopted"
    assert stored.adopted_by == "cli-user"
    assert stored.adopted_at is not None


def test_prompt_accepts_y(tmp_path: Path, monkeypatch, capsys) -> None:
    candidate_id = "memory_cli_prompt_y"
    _seed_candidate(tmp_path, candidate_id)
    monkeypatch.setattr(sys, "stdin", TtyStringIO("y\n"))

    exit_code = _run_cli(tmp_path, candidate_id)

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert "Adopt candidate memory_cli_prompt_y" in captured.err
    assert Path(captured.out.strip()).exists()
    assert _stored_candidate(tmp_path, candidate_id).status == "adopted"


def test_prompt_accepts_yes_uppercase(tmp_path: Path, monkeypatch, capsys) -> None:
    candidate_id = "memory_cli_prompt_yes_uppercase"
    _seed_candidate(tmp_path, candidate_id)
    monkeypatch.setattr(sys, "stdin", TtyStringIO("YES\n"))

    exit_code = _run_cli(tmp_path, candidate_id)

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert Path(captured.out.strip()).exists()
    assert _stored_candidate(tmp_path, candidate_id).status == "adopted"


def test_prompt_rejects_n(tmp_path: Path, monkeypatch, capsys) -> None:
    candidate_id = "memory_cli_prompt_n"
    _seed_candidate(tmp_path, candidate_id)
    monkeypatch.setattr(sys, "stdin", TtyStringIO("n\n"))

    exit_code = _run_cli(tmp_path, candidate_id)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    stored = _stored_candidate(tmp_path, candidate_id)
    assert stored.status == "candidate"
    assert stored.adopted_at is None
    assert not (tmp_path / ".omx" / "artifacts").exists()


def test_non_tty_without_yes(tmp_path: Path, monkeypatch, capsys) -> None:
    candidate_id = "memory_cli_non_tty"
    _seed_candidate(tmp_path, candidate_id)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = _run_cli(tmp_path, candidate_id)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "non-interactive shell requires --yes" in captured.err
    assert _stored_candidate(tmp_path, candidate_id).status == "candidate"


def test_candidate_not_found(tmp_path: Path, capsys) -> None:
    exit_code = _run_cli(tmp_path, "memory_cli_missing", "--yes")

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "candidate not found: memory_cli_missing" in captured.err


def test_already_confirmed(tmp_path: Path, capsys) -> None:
    candidate_id = "memory_cli_already_confirmed"
    adopted = adopt_candidate(_candidate(candidate_id), project_root=tmp_path, actor="user")["candidate"]
    adopted["status"] = "confirmed"
    _store(tmp_path).adopt_candidate(adopted)

    exit_code = _run_cli(tmp_path, candidate_id, "--yes")

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert "candidate already confirmed: memory_cli_already_confirmed" in captured.err


def test_invalid_candidate_id_format(tmp_path: Path, capsys) -> None:
    exit_code = _run_cli(tmp_path, "not-a-valid-id", "--yes")

    captured = capsys.readouterr()
    assert exit_code == 4
    assert captured.out == ""
    assert "invalid candidate_id format: not-a-valid-id" in captured.err
