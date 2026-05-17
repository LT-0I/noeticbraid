# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D19 Phase-2 workflow library and local orchestration tests."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.elicitation.local_ai import LOCAL_AI_ARGS_ENV, LOCAL_AI_BIN_ENV
from noeticbraid_backend.platform.orchestrate.critique import (
    CAP_MESSAGE,
    ReviewerVerdict,
    reconcile_verdicts,
    run_critique_loop,
)
from noeticbraid_backend.platform.orchestrate.engine import run_orchestration
from noeticbraid_backend.platform.orchestrate.nodes import HubExecutionNode
from noeticbraid_backend.platform.orchestrate.state import load_state, orchestration_path_for
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.workflows.audit import audit_library
from noeticbraid_backend.platform.workflows.loader import LIBRARY_DIR, discover_specs
from noeticbraid_backend.platform.workflows.selector import select_workflow
from noeticbraid_backend.settings import Settings

ACCOUNT = "beta_user_01"
OTHER_ACCOUNT = "beta_user_02"
PHASE2_FORBIDDEN = {
    "ledger",
    "dispatch",
    "critique",
    "internal_reason",
    "internal-reason",
    "orchestration",
    "rounds",
    "directive",
    "reviewer",
    "verdict",
    "evidence_node_ids",
    "workflow",
    "selector",
}


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), data_root


def _token(data_root: Path, account: str = ACCOUNT) -> str:
    return TokenStore(data_root).create_token(account)


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def _create_task(client: TestClient, token: str, title: str = "Phase 2 task") -> str:
    response = client.post("/platform/tasks", headers=_headers(token), json={"title": title})
    assert response.status_code == 200, response.text
    return str(response.json()["task"]["task_id"])


def _configure_stub(monkeypatch: pytest.MonkeyPatch, script: Path) -> None:
    monkeypatch.setenv(LOCAL_AI_BIN_ENV, sys.executable)
    monkeypatch.setenv(LOCAL_AI_ARGS_ENV, json.dumps([str(script)]))


def _write_local_task_stub(tmp_path: Path, *, mode: str = "consensus", family: str | None = None) -> Path:
    script = tmp_path / f"phase2_stub_{mode}_{len(list(tmp_path.glob('phase2_stub_*.py')))}.py"
    script.write_text(
        "import json, sys\n"
        "envelope = json.loads(sys.stdin.read())\n"
        "payload = envelope.get('payload') or {}\n"
        "kind = payload.get('kind')\n"
        f"mode = {mode!r}\n"
        f"forced_family = {family!r}\n"
        "if kind == 'fanout':\n"
        "    req = payload.get('inputs', {}).get('requirement', {})\n"
        "    print(json.dumps({'artifact': {'text': 'draft for ' + str(req.get('id', 'req'))}}))\n"
        "elif kind == 'critique_review':\n"
        "    fam = forced_family or payload.get('reviewer_family') or 'unknown'\n"
        "    evidence = payload.get('evidence_node_ids') or []\n"
        "    if mode == 'consensus':\n"
        "        issues = []\n"
        "    elif mode == 'taste':\n"
        "        issues = ['tone preference taste issue']\n"
        "    elif mode == 'user_challenge':\n"
        "        issues = ['contradicts user explicitly requested direction']\n"
        "    else:\n"
        "        issues = ['missing cited detail']\n"
        "    print(json.dumps({'verdict': {'reviewer_family': fam, 'issues': issues, 'rationale': 'checked', 'confidence': 0.8, 'evidence_node_ids': evidence if issues else []}}))\n"
        "elif kind == 'apply_revision_directive':\n"
        "    artifact = payload.get('artifact') or {}\n"
        "    text = str(artifact.get('text', 'draft')) + ' revised'\n"
        "    score = min(1.0, 0.1 * (text.count('revised') + 1))\n"
        "    print(json.dumps({'artifact': {'text': text}, 'score': score}))\n"
        "else:\n"
        "    print(json.dumps({'artifact': {'text': 'generic artifact'}}))\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _confirmed_payload(task_id: str, text: str, modality: str = "document", req_id: str = "req_1") -> dict[str, Any]:
    return model.stamp_confirmed_requirements(task_id, [{"id": req_id, "text": text, "modality": modality}])


def _assert_no_engineering_fields(value: Any) -> None:
    if isinstance(value, dict):
        assert PHASE2_FORBIDDEN.isdisjoint(value)
        for item in value.values():
            _assert_no_engineering_fields(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_engineering_fields(item)


def test_workflow_library_discovers_four_public_specs_and_audit_passes() -> None:
    specs = discover_specs()

    assert [spec.id for spec in specs] == [
        "code_change_and_review",
        "document_draft_and_refine",
        "research_and_synthesize",
        "open_orchestration",
    ]
    assert len(specs) == 4
    assert all("_internal" not in spec.id for spec in specs)
    result = audit_library()
    assert result.ok, result.messages
    assert result.selectable_count == 4


def test_workflow_loader_rejects_malformed_and_duplicate_id(tmp_path: Path) -> None:
    malformed_dir = tmp_path / "malformed"
    malformed_dir.mkdir()
    (malformed_dir / "broken.workflow.json").write_text(json.dumps({"workflow": {"id": "broken"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        discover_specs(malformed_dir)

    duplicate_dir = tmp_path / "duplicate"
    duplicate_dir.mkdir()
    first = LIBRARY_DIR / "document_draft_and_refine.workflow.json"
    shutil.copy(first, duplicate_dir / "a.workflow.json")
    shutil.copy(first, duplicate_dir / "b.workflow.json")
    with pytest.raises(ValueError, match="duplicate workflow id"):
        discover_specs(duplicate_dir)


def test_selector_picks_expected_and_fallback_appends_one_question(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_selector_phase2"
    model.initialize_task_files(ACCOUNT, task_id)
    research = _confirmed_payload(task_id, "Research across sources and compare options", "research")

    selected = select_workflow(research)

    assert selected.spec.id == "research_and_synthesize"
    assert selected.used_fallback is False

    generic = _confirmed_payload(task_id, "Help me with something broad", "text")
    fallback = select_workflow(generic, account=ACCOUNT, task_id=task_id)

    assert fallback.spec.id == "open_orchestration"
    assert fallback.used_fallback is True
    questions = [row for row in model.serialize_visible_conversation(ACCOUNT, task_id) if row["kind"] == "question"]
    assert len(questions) == 1
    assert "general plan" in questions[0]["text"]


def test_engine_confirmed_runs_pending_to_done_and_view_leaks_no_intermediate_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="consensus"))
    task_id = _create_task(client, token)
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a concise document", "modality": "document"}]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["requirements"]["requirements"][0]["coarse_state"] == "pending"

    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))

    assert response.status_code == 200, response.text
    view = response.json()["view"]
    assert set(view) == {"conversation", "deliverables", "coarse_status", "capability_notice"}
    _assert_no_engineering_fields(view)
    assert view["coarse_status"] == [
        {
            "requirement_id": "req_doc",
            "text": "Draft a concise document",
            "coarse_state": "done",
            "capability_status": "supported",
        }
    ]
    status = client.get(f"/platform/tasks/{task_id}/orchestrate/status", headers=_headers(token))
    assert status.status_code == 200, status.text
    assert status.json()["phase"] == "delivered"
    assert orchestration_path_for(ACCOUNT, task_id).is_file()
    rendered = json.dumps(view, ensure_ascii=False, sort_keys=True)
    assert "Started: Draft" in rendered
    assert "Completed: Draft" in rendered


def test_engine_non_confirmed_and_legacy_are_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_non_confirmed_phase2"
    model.initialize_task_files(ACCOUNT, task_id)

    result = run_orchestration(ACCOUNT, task_id)

    assert result.selected_workflow_id is None
    assert load_state(ACCOUNT, task_id) is None
    assert model.load_requirements(ACCOUNT, task_id)["status"] == "eliciting"

    legacy_id = "task_legacy_phase2"
    create_task(ACCOUNT, task_id=legacy_id, title="Legacy", modality_targets=[])
    legacy = run_orchestration(ACCOUNT, legacy_id)

    assert legacy.selected_workflow_id is None
    assert model.load_requirements(ACCOUNT, legacy_id)["legacy"] is True
    assert load_state(ACCOUNT, legacy_id) is None


def test_endpoint_rejects_not_confirmed_and_blocked_capability_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)

    not_confirmed = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))
    assert not_confirmed.status_code == 400
    assert not_confirmed.json() == {"detail": "not_confirmed"}

    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_image", "text": "Generate a hero image", "modality": "image"}]},
    )
    assert confirm.status_code == 200, confirm.text
    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))

    assert response.status_code == 200, response.text
    row = response.json()["view"]["coarse_status"][0]
    assert row["coarse_state"] == "blocked"
    assert row["capability_status"] == "unavailable"
    assert row["blocked_reason"] == capability_for("image").blocked_reason


def test_critique_rejects_issue_without_evidence_and_reconciles_one_directive() -> None:
    with pytest.raises(ValueError, match="evidence_node_ids"):
        ReviewerVerdict.from_json_dict(
            {"reviewer_family": "codex", "issues": ["missing proof"], "rationale": "x", "confidence": 0.5, "evidence_node_ids": []}
        )
    verdicts = [
        ReviewerVerdict("codex", ["missing source"], "r1", 0.7, ["round_1:fanout_req"]),
        ReviewerVerdict("gemini", ["missing source", "tighten wording"], "r2", 0.9, ["round_1:fanout_req"]),
    ]

    directive = reconcile_verdicts(verdicts)

    assert directive.directive_text.startswith("Address these evidence-cited issues")
    assert directive.decision_class == "mechanical"
    assert directive.evidence_node_ids == ["round_1:fanout_req"]
    assert len([directive]) == 1


def test_critique_homogeneous_reviewers_exit_marginal_low_confidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="issues", family="codex"))
    task_id = "task_homogeneous_phase2"
    model.initialize_task_files(ACCOUNT, task_id)

    result = run_critique_loop(ACCOUNT, task_id, {"id": "req_1", "text": "Draft", "modality": "document"}, {"text": "draft"}, "round_1:fanout_req_1")

    assert result.status == "delivered"
    assert result.terminated_by == "marginal"
    assert result.low_confidence is True
    assert result.reason == "single-reviewer, low-confidence"


def test_critique_cap_delivers_best_and_appends_honest_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="issues"))
    task_id = "task_cap_phase2"
    model.initialize_task_files(ACCOUNT, task_id)

    result = run_critique_loop(ACCOUNT, task_id, {"id": "req_1", "text": "Draft", "modality": "document"}, {"text": "draft"}, "round_1:fanout_req_1")

    assert result.status == "capped"
    assert result.terminated_by == "MAX_ROUNDS"
    rows = model.serialize_visible_conversation(ACCOUNT, task_id)
    assert any(CAP_MESSAGE in row["text"] for row in rows)


@pytest.mark.parametrize("mode", ["taste", "user_challenge"])
def test_critique_taste_and_user_challenge_surface_single_user_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode=mode))
    task_id = f"task_{mode}_phase2"
    model.initialize_task_files(ACCOUNT, task_id)

    result = run_critique_loop(ACCOUNT, task_id, {"id": "req_1", "text": "Draft", "modality": "document"}, {"text": "draft"}, "round_1:fanout_req_1")

    assert result.status == "deferred"
    assert result.decision_class == mode
    questions = [row for row in model.serialize_visible_conversation(ACCOUNT, task_id) if row["kind"] == "question"]
    assert len(questions) == 1
    assert "final decision is needed" in questions[0]["text"]


def test_hub_execution_node_returns_deferred_web_ai_reason() -> None:
    outcome = HubExecutionNode().execute({}, {})

    assert outcome.status == "deferred"
    assert outcome.reason == capability_for("web_ai").blocked_reason
    assert outcome.evidence_node_ids == []


def test_cross_account_orchestrate_and_status_are_opaque_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    other_token = _token(data_root, OTHER_ACCOUNT)
    task_id = _create_task(client, token)
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a document", "modality": "document"}]},
    )
    assert confirm.status_code == 200, confirm.text

    orchestrate = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(other_token))
    status = client.get(f"/platform/tasks/{task_id}/orchestrate/status", headers=_headers(other_token))

    assert orchestrate.status_code == 404
    assert orchestrate.json() == {"detail": "not_found"}
    assert status.status_code == 404
    assert status.json() == {"detail": "not_found"}


def test_phase2_source_contains_no_lowercase_network_forbidden_imports() -> None:
    roots = [
        SRC_ROOT / "noeticbraid_backend" / "platform" / "orchestrate",
        SRC_ROOT / "noeticbraid_backend" / "platform" / "workflows",
        SRC_ROOT / "noeticbraid_backend" / "platform" / "conversation",
        SRC_ROOT / "noeticbraid_backend" / "platform" / "elicitation",
    ]
    pattern = re.compile(r"(^|[^.])\b(requests|httpx|aiohttp|socket|urllib)\b")
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json"}:
                if pattern.search(path.read_text(encoding="utf-8")):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
