from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
TASK_CARD = ROOT / "examples" / "task_card_omc_ingest.json"


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = SRC + (os.pathsep + existing if existing else "")
    return env


def test_cli_debate_loop_mock_smoke(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "noeticbraid.tools.multimodel_alliance",
            "debate-loop",
            str(TASK_CARD),
            "--mock-invocations",
            "--state-root",
            str(tmp_path / "state"),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--pretty",
        ],
        cwd=ROOT,
        env=_cli_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["provider_mode"] == "mock"
    assert Path(payload["artifact_paths"]["candidate_jsonl"]).is_file()
    assert Path(payload["artifact_paths"]["ledger_jsonl"]).is_file()
