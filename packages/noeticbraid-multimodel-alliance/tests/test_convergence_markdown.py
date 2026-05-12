from __future__ import annotations

from pathlib import Path

from noeticbraid.tools.multimodel_alliance.convergence_markdown import render_convergence_markdown
from noeticbraid.tools.multimodel_alliance.loop import run_debate_loop

ROOT = Path(__file__).resolve().parents[1]
TASK_CARD = ROOT / "examples" / "task_card_omc_ingest.json"
GOLDEN = ROOT / "src" / "noeticbraid" / "tools" / "multimodel_alliance" / "fixtures" / "omc_convergence_markdown_golden.md"


def test_markdown_generated_from_structured_records_only(tmp_path):
    result = run_debate_loop(TASK_CARD, state_root=tmp_path / "state", artifact_root=tmp_path / "artifacts")

    markdown = render_convergence_markdown(
        route=result["route"],
        debate=result["debate"],
        convergence=result["convergence"],
        candidates=[result["candidate"]],
    )
    assert markdown == GOLDEN.read_text(encoding="utf-8").rstrip("\n")
    assert "raw provider transcript" not in markdown.lower()
    assert "Source of truth: structured ModelRoute" in markdown
