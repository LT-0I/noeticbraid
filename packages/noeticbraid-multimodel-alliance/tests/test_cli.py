from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")


def _cli_env() -> dict:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _SRC + (os.pathsep + existing if existing else "")
    return env


def write_task_card(name: str, payload: dict) -> Path:
    directory = ROOT / ".tmp" / "cli-test-inputs"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "noeticbraid.tools.multimodel_alliance", *args],
        cwd=ROOT,
        env=_cli_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cli_validate_fixtures():
    result = run_cli("validate-fixtures")
    assert result.returncode == 0, result.stderr
    assert "validated 3 multimodel alliance fixtures" in result.stdout


def test_cli_route_outputs_json():
    task_card = write_task_card(
        "task_card",
        {"task_id": "task_cli_medium", "risk_hint": "medium", "required_capabilities": ["planning", "code_review", "convergence"]},
    )
    result = run_cli("route", str(task_card), "--pretty")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["route_type"] == "dual_review"


def test_cli_run_fixture_validates_packaged_fixture():
    fixture = ROOT / "src" / "noeticbraid" / "tools" / "multimodel_alliance" / "fixtures" / "dual_review_prompt_cycle.json"
    result = run_cli("run-fixture", str(fixture), "--pretty")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"fixture_id": "fixture_dual_review_prompt_cycle", "status": "valid"}


def test_cli_route_positional_argument():
    """MUST-4: route subcommand accepts the task card as a positional argument."""
    task_card = {
        "task_id": "tc_positional",
        "task_type": "writing",
        "risk_hint": "low",
        "required_capabilities": ["writing"],
    }
    tc_path = write_task_card("tc_positional", task_card)
    result = subprocess.run(
        [sys.executable, "-m", "noeticbraid.tools.multimodel_alliance", "route", str(tc_path)],
        cwd=ROOT,
        env=_cli_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["route_type"] in {"single_model", "producer_reviewer"}
