# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D20 Phase-3 live hub seam tests with no real network."""

from __future__ import annotations

import ast
import json
import re
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
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.conversation import deliverable_view, model
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.elicitation.local_ai import LOCAL_AI_ARGS_ENV, LOCAL_AI_BIN_ENV
from noeticbraid_backend.platform.orchestrate import engine as engine_mod
from noeticbraid_backend.platform.orchestrate import nodes as nodes_mod
from noeticbraid_backend.platform.orchestrate import state
from noeticbraid_backend.platform.orchestrate.critique import CAP_MESSAGE
from noeticbraid_backend.platform.orchestrate.nodes import HubExecutionNode
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.workflows.schema import WorkflowSelector, WorkflowSpec
from noeticbraid_backend.platform.workflows.selector import SelectionResult
from noeticbraid_backend.settings import Settings

ACCOUNT = "phase3_user_01"
OTHER_ACCOUNT = "phase3_user_02"
PHASE3_FORBIDDEN = {
    "conversation_id",
    "sha",
    "sha256",
    "critique",
    "orchestration",
    "rounds",
    "directive",
    "reviewer",
    "verdict",
    "workflow",
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


def _create_task(client: TestClient, token: str, title: str = "Phase 3 task") -> str:
    response = client.post("/platform/tasks", headers=_headers(token), json={"title": title})
    assert response.status_code == 200, response.text
    return str(response.json()["task"]["task_id"])


def _write_local_task_stub(tmp_path: Path, *, mode: str) -> Path:
    script = tmp_path / f"phase3_stub_{mode}_{len(list(tmp_path.glob('phase3_stub_*.py')))}.py"
    script.write_text(
        "import json, sys\n"
        "envelope = json.loads(sys.stdin.read())\n"
        "payload = envelope.get('payload') or {}\n"
        "kind = payload.get('kind')\n"
        f"mode = {mode!r}\n"
        "if kind == 'critique_review':\n"
        "    evidence = payload.get('evidence_node_ids') or []\n"
        "    issues = [] if mode == 'consensus' else ['missing cited detail']\n"
        "    print(json.dumps({'verdict': {'reviewer_family': payload.get('reviewer_family'), 'issues': issues, 'rationale': 'checked', 'confidence': 0.8, 'evidence_node_ids': evidence if issues else []}}))\n"
        "elif kind == 'apply_revision_directive':\n"
        "    artifact = payload.get('artifact') or {}\n"
        "    print(json.dumps({'artifact': {'text': str(artifact.get('text', 'draft')) + ' revised'}, 'score': 0.5}))\n"
        "else:\n"
        "    raw = envelope.get('raw_requirement') or 'Draft a document'\n"
        "    print(json.dumps({'requirements': [{'id': 'req_doc', 'text': raw, 'modality': 'document'}], 'questions': [], 'ready_to_confirm': True}))\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _configure_stub(monkeypatch: pytest.MonkeyPatch, script: Path) -> None:
    monkeypatch.setenv(LOCAL_AI_BIN_ENV, sys.executable)
    monkeypatch.setenv(LOCAL_AI_ARGS_ENV, json.dumps([str(script)]))


def _enable_hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hub_root = tmp_path / "hub-root"
    hub_root.mkdir()
    monkeypatch.setenv("NOETICBRAID_PLATFORM_HUB_EXEC", "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub_root))
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setattr(nodes_mod.compat, "digest_matches", lambda _path: ("ok", None))
    monkeypatch.setattr(nodes_mod, "check_chatgpt_consumer_health", lambda _path: {"ok": True})
    return hub_root


def _hub_selection() -> SelectionResult:
    spec = WorkflowSpec(
        id="phase3_hub_workflow",
        version="1.0.0",
        description="Use when Phase 3 tests need the hub fanout seam.",
        selector=WorkflowSelector((), (), (), (), ()),
        inputs=(),
        isolation={},
        nodes=(
            {"id": "elicit", "type": "interview", "impl": "clarifygpt_divergence"},
            {"id": "fanout", "type": "orchestrate", "agents": ["web_gpt"]},
            {"id": "critique_loop", "type": "reconcile", "max_rounds": 3, "exit": ["consensus"]},
            {"id": "deliver", "type": "artifact_sink", "target": "task.deliverables"},
        ),
        edges=(),
        termination={},
        capability_honesty={},
    )
    return SelectionResult(spec, 1, False, False, "matched")


def _assert_no_engineering_fields(value: Any) -> None:
    if isinstance(value, dict):
        assert PHASE3_FORBIDDEN.isdisjoint(value)
        for item in value.values():
            _assert_no_engineering_fields(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_engineering_fields(item)


def test_hub_execution_node_gate_off_is_phase2_deferred_and_dispatch_free(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append({}) or {})

    outcome = HubExecutionNode().execute({"id": "fanout"}, {"account": ACCOUNT, "task_id": "task_phase3_gate_off"})

    assert outcome.status == "deferred"
    assert outcome.reason == capability_for("web_ai").blocked_reason
    assert outcome.evidence_node_ids == []
    assert calls == []


def test_hub_execution_node_gate_on_unhealthy_is_honest_deferred(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_hub(monkeypatch, tmp_path)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        nodes_mod,
        "check_chatgpt_consumer_health",
        lambda _path: {"ok": False, "errorCode": "LOGIN_REQUIRED", "message": "LOGIN_REQUIRED"},
    )
    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append({}) or {})

    outcome = HubExecutionNode().execute({"id": "fanout"}, {"account": ACCOUNT, "task_id": "task_phase3_unhealthy"})

    assert outcome.status == "deferred"
    assert "LOGIN_REQUIRED" in str(outcome.reason)
    assert calls == []


def test_hub_execution_node_gate_on_ok_and_blocked_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_hub(monkeypatch, tmp_path)
    recorded: list[tuple[str, dict[str, Any]]] = []

    def ok_dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        recorded.append((op, dict(params)))
        return {
            "outcome": "ok",
            "status": "ok",
            "payload": {"response_text": "real hub draft", "conversation_id": "conv_phase3"},
        }

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", ok_dispatch)
    outcome = HubExecutionNode().execute(
        {"id": "fanout", "type": "orchestrate", "agents": ["web_gpt"]},
        {"account": ACCOUNT, "task_id": "task_phase3_ok", "requirement": {"text": "Draft a document"}},
    )
    assert outcome.status == "succeeded"
    assert outcome.artifact == {"text": "real hub draft", "hub": True, "conversation_id": "conv_phase3"}
    assert recorded[0][0] == "webai_chatgpt_send_prompt"
    assert recorded[0][1]["reuse_conversation"] is False
    assert len(recorded[0][1]["prompt"]) <= compat.PROMPT_MAX_CHARS

    def blocked_dispatch(_op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return {"outcome": "blocked", "status": "error", "reason": "LOGIN_REQUIRED", "payload": {}}

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", blocked_dispatch)
    blocked = HubExecutionNode().execute(
        {"id": "fanout"},
        {"account": ACCOUNT, "task_id": "task_phase3_blocked", "requirement": {"text": "Draft"}},
    )
    assert blocked.status == "deferred"
    assert blocked.reason == "LOGIN_REQUIRED"


def test_live_critique_reuses_conversation_and_mid_loop_block_stamps_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="issues"))
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setattr(engine_mod, "select_workflow", lambda *_args, **_kwargs: _hub_selection())
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        if params["reuse_conversation"] is False:
            return {"outcome": "ok", "status": "ok", "payload": {"response_text": "draft", "conversation_id": "conv_loop"}}
        return {"outcome": "blocked", "status": "error", "reason": "LOGIN_REQUIRED", "payload": {}}

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", dispatch)
    task_id = _create_task(client, token, "Phase 3 blocked revision")
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a document", "modality": "document"}]},
    )
    assert confirm.status_code == 200, confirm.text

    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))

    assert response.status_code == 200, response.text
    assert [call[1]["reuse_conversation"] for call in calls] == [False, True]
    assert all(call[0] == "webai_chatgpt_send_prompt" for call in calls)
    assert all(len(call[1]["prompt"]) <= compat.PROMPT_MAX_CHARS for call in calls)
    status = client.get(f"/platform/tasks/{task_id}/orchestrate/status", headers=_headers(token)).json()
    assert status["phase"] == "blocked"
    row = status["coarse_status"][0]
    assert row["coarse_state"] == "blocked"
    assert row["blocked_reason"] == "LOGIN_REQUIRED"


def test_backfill_deliverable_endpoint_and_gate_off_smoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="consensus"))
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setattr(engine_mod, "select_workflow", lambda *_args, **_kwargs: _hub_selection())
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": "delivered draft", "conversation_id": "conv_done"}}

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", dispatch)
    task_id = _create_task(client, token, "Phase 3 delivered")
    elicit = client.post(
        f"/platform/tasks/{task_id}/elicit",
        headers=_headers(token),
        json={"raw_requirement": "Draft a document"},
    )
    assert elicit.status_code == 200, elicit.text
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a document", "modality": "document"}]},
    )
    assert confirm.status_code == 200, confirm.text

    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))
    delivered = client.get(f"/platform/tasks/{task_id}/deliverables", headers=_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["view"]["coarse_status"][0]["coarse_state"] == "done"
    assert calls and calls[0][1]["reuse_conversation"] is False
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["deliverables"] == [
        {
            "requirement_id": "req_doc",
            "title": "Draft a document",
            "status": "delivered",
            "download_ref": f"tasks/{task_id}/orchestration/final/final_req_doc.json",
        }
    ]
    _assert_no_engineering_fields(delivered.json()["deliverables"])
    view = client.get(f"/platform/tasks/{task_id}/view", headers=_headers(token)).json()
    assert set(view) == {"conversation", "deliverables", "coarse_status", "capability_notice"}

    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    calls.clear()
    gate_off_id = _create_task(client, token, "Phase 3 gate off")
    confirm_off = client.post(
        f"/platform/tasks/{gate_off_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a document", "modality": "document"}]},
    )
    assert confirm_off.status_code == 200, confirm_off.text
    gate_off = client.post(f"/platform/tasks/{gate_off_id}/orchestrate", headers=_headers(token))
    gate_off_deliverables = client.get(f"/platform/tasks/{gate_off_id}/deliverables", headers=_headers(token))
    assert gate_off.status_code == 200, gate_off.text
    assert calls == []
    assert gate_off.json()["view"]["coarse_status"][0]["coarse_state"] == "blocked"
    assert gate_off.json()["view"]["coarse_status"][0]["blocked_reason"] == capability_for("web_ai").blocked_reason
    assert gate_off_deliverables.json()["deliverables"][0]["status"] == "blocked"
    assert "download_ref" not in gate_off_deliverables.json()["deliverables"][0]


def test_cap_reuses_hub_revision_and_preserves_hub_rounds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    _configure_stub(monkeypatch, _write_local_task_stub(tmp_path, mode="issues"))
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setattr(engine_mod, "select_workflow", lambda *_args, **_kwargs: _hub_selection())
    calls: list[dict[str, Any]] = []

    def dispatch(_op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append(dict(params))
        response = "draft" if params["reuse_conversation"] is False else f"revised {len(calls)}"
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": response, "conversation_id": "conv_cap"}}

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", dispatch)
    task_id = _create_task(client, token, "Phase 3 capped")
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_doc", "text": "Draft a document", "modality": "document"}]},
    )
    assert confirm.status_code == 200, confirm.text

    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))

    assert response.status_code == 200, response.text
    assert [call["reuse_conversation"] for call in calls] == [False, True, True]
    rows = model.serialize_visible_conversation(ACCOUNT, task_id)
    assert any(CAP_MESSAGE in row["text"] for row in rows)
    run_state = state.load_state(ACCOUNT, task_id)
    assert run_state is not None
    assert run_state["status"] == "capped"
    assert any(round_row.get("hub") is True for round_row in run_state["rounds"])


def test_per_task_deliverables_blocked_cases_and_cross_account(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    other_token = _token(data_root, OTHER_ACCOUNT)
    task_id = _create_task(client, token, "Phase 3 image")
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_image", "text": "Generate an image", "modality": "image"}]},
    )
    assert confirm.status_code == 200, confirm.text

    deliverables = client.get(f"/platform/tasks/{task_id}/deliverables", headers=_headers(token))
    cross = client.get(f"/platform/tasks/{task_id}/deliverables", headers=_headers(other_token))

    assert deliverables.status_code == 200, deliverables.text
    assert deliverables.json()["deliverables"] == [
        {
            "requirement_id": "req_image",
            "title": "Generate an image",
            "status": "blocked",
            "blocked_reason": capability_for("image").blocked_reason,
        }
    ]
    assert cross.status_code == 404
    assert cross.json() == {"detail": "not_found"}

    model.write_requirements(
        ACCOUNT,
        task_id,
        {
            "task_id": task_id,
            "schema_version": model.REQUIREMENTS_SCHEMA_VERSION,
            "status": "confirmed",
            "requirements": [
                {
                    "id": "req_done_missing",
                    "text": "Done but file missing",
                    "modality": "document",
                    "capability_status": "supported",
                    "coarse_state": "done",
                }
            ],
        },
    )
    assert deliverable_view.per_task_deliverables(ACCOUNT, task_id)[0] == {
        "requirement_id": "req_done_missing",
        "title": "Done but file missing",
        "status": "blocked",
        "blocked_reason": "Final artifact is not available.",
    }


def test_state_blocked_and_forward_compatible_round_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_phase3_state"
    create_task(ACCOUNT, task_id=task_id, title="State", modality_targets=[])
    payload = state.initial_state(task_id, "phase3_hub_workflow")
    payload["status"] = "blocked"
    payload["rounds"] = [
        {
            "round": 1,
            "artifact_ref": state.round_artifact_ref(task_id, 1, "fanout_req"),
            "decision_class": "mechanical",
            "terminated_by": "failed",
            "extra_future_key": {"kept": True},
            "hub": True,
        }
    ]
    validated = state.validate_state(payload)
    assert validated["status"] == "blocked"
    assert validated["rounds"][0]["hub"] is True
    assert validated["rounds"][0]["extra_future_key"] == {"kept": True}

    phase2_payload = state.initial_state(task_id, "phase2_workflow")
    phase2_payload["status"] = "delivered"
    phase2_payload["rounds"] = [
        {
            "round": 1,
            "artifact_ref": state.round_artifact_ref(task_id, 1, "fanout_req"),
            "decision_class": "mechanical",
            "terminated_by": "fanout",
        }
    ]
    phase2 = state.write_state(ACCOUNT, task_id, phase2_payload)
    assert "hub" not in phase2["rounds"][0]
    assert state.load_state(ACCOUNT, task_id) == phase2


def test_phase3_no_network_grep_and_import_allowlist() -> None:
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

    allowed = {
        "noeticbraid_backend.platform.orchestration": {"hub_adapter"},
        "noeticbraid_backend.omc_workspace": {"web_ai_hub_compat", "web_ai_hub_client"},
        "noeticbraid_backend.omc_workspace.web_ai_hub_client": {
            "CHATGPT_PROFILE",
            "check_chatgpt_consumer_health",
            "sanitize_error_msg",
        },
    }
    bad_imports: list[str] = []
    for path in (SRC_ROOT / "noeticbraid_backend" / "platform" / "orchestrate").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in allowed:
                    imported = {alias.name for alias in node.names}
                    if not imported.issubset(allowed[node.module]):
                        bad_imports.append(f"{path.name}:{node.module}:{sorted(imported)}")
                elif node.module.startswith("noeticbraid_backend.omc_workspace") or node.module.startswith(
                    "noeticbraid_backend.platform.orchestration"
                ):
                    bad_imports.append(f"{path.name}:{node.module}")
    assert bad_imports == []
