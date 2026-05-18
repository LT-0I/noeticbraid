# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D22 Web-AI generate→cross-review chain tests (zero network)."""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.orchestrate import critique as critique_mod
from noeticbraid_backend.platform.orchestrate import nodes as nodes_mod
from noeticbraid_backend.platform.orchestrate.critique import CAP_MESSAGE, run_critique_loop
from noeticbraid_backend.platform.orchestrate.engine import run_orchestration
from noeticbraid_backend.platform.orchestrate.nodes import HubExecutionNode
from noeticbraid_backend.platform.orchestrate.web_modality_routes import resolve_web_modality
from noeticbraid_backend.platform.workspace_paths import resolve_user_path
from noeticbraid_backend.platform.workflows.selector import select_workflow
from noeticbraid_backend.settings import Settings

ACCOUNT = "d22_user_01"


def _enable_hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hub_root = tmp_path / "hub-root"
    hub_root.mkdir()
    monkeypatch.setenv("NOETICBRAID_PLATFORM_HUB_EXEC", "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub_root))
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setattr(nodes_mod.compat, "digest_matches", lambda _path: ("ok", None))
    monkeypatch.setattr(nodes_mod, "check_chatgpt_consumer_health", lambda _path: {"ok": True})


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), data_root


def _token(data_root: Path) -> str:
    return TokenStore(data_root).create_token(ACCOUNT)


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def _verdict(*, issues: list[str], evidence: list[str]) -> dict[str, Any]:
    return {
        "reviewer_family": "web:claude",
        "issues": issues,
        "rationale": "checked by cross-model reviewer",
        "confidence": 0.8,
        "evidence_node_ids": evidence,
    }


def test_d22_route_table_dispatchable_fail_closed_and_music_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    for modality in ("text", "document", "slides", "poster", "image", "video"):
        route = resolve_web_modality(modality)
        assert route.kind == "route"
        assert route.generator_op in compat.DISPATCHABLE
        assert route.reviewer_op in compat.DISPATCHABLE
        assert route.generator_vendor != route.reviewer_vendor
    assert resolve_web_modality("music").kind == "blocked"

    routes_mod = importlib.import_module("noeticbraid_backend.platform.orchestrate.web_modality_routes")
    monkeypatch.setattr(routes_mod.compat, "DISPATCHABLE", frozenset({"webai_claude_upload_and_query"}))
    reloaded = importlib.reload(routes_mod)
    blocked = reloaded.resolve_web_modality("image")
    assert isinstance(blocked, reloaded.ModalityBlocked)
    assert "compat.DISPATCHABLE" in blocked.reason
    monkeypatch.undo()
    importlib.reload(routes_mod)


def test_d22_gate_off_generation_is_dispatch_free_byte_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append((_args, _kwargs)) or {})

    outcome = HubExecutionNode().execute({"id": "fanout"}, {"account": ACCOUNT, "task_id": "task_gate_off"})

    assert outcome.status == "deferred"
    assert outcome.reason == "Web AI 将在后续阶段接入，本阶段暂不执行。"
    assert outcome.evidence_node_ids == []
    assert calls == []


def test_d22_gate_on_image_generation_reviews_with_confined_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_image_happy"
    artifact_ref = f"tasks/{task_id}/artifacts/hero.png"
    resolved = resolve_user_path(ACCOUNT, artifact_ref)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(b"png")
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        if op == "webai_chatgpt_generate_image":
            return {"outcome": "ok", "status": "ok", "payload": {"path": artifact_ref, "conversation_id": "conv_img"}}
        assert op == "webai_claude_upload_and_query"
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": json.dumps(_verdict(issues=[], evidence=[]))}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    model.initialize_task_files(ACCOUNT, task_id)
    payload = model.stamp_confirmed_requirements(task_id, [{"id": "req_image", "text": "Generate a hero image", "modality": "image"}])
    model.write_requirements(ACCOUNT, task_id, payload)

    result = run_orchestration(ACCOUNT, task_id)

    assert result.selected_workflow_id == "web_generate_and_cross_review"
    assert result.phase == "delivered"
    assert calls[0][0] == "webai_chatgpt_generate_image"
    assert calls[1][0] == "webai_claude_upload_and_query"
    assert set(calls[1][1]).issubset(compat.UPLOAD_FILE_KEYS)
    assert calls[1][1]["files"] == [str(resolved)]
    assert not any(str(tmp_path / "raw").lower() in repr(call).lower() for call in calls)


def test_d22_nonconforming_web_verdict_is_honest_deferred(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_bad_verdict")

    def dispatch(_op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        bad = {"reviewer_family": "web:claude", "issues": ["missing proof"], "evidence_node_ids": [], "confidence": 0.8}
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": json.dumps(bad)}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    result = run_critique_loop(
        ACCOUNT,
        "task_bad_verdict",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True, "conversation_id": "conv_doc"},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )

    assert result.status == "deferred"
    assert "evidence_node_ids" in str(result.reason)


def test_d22_reinject_uses_reuse_conversation_and_missing_conversation_caps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_reinject")
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        if op == "webai_claude_send_prompt" and len(calls) == 1:
            return {
                "outcome": "ok",
                "status": "ok",
                "payload": {"response_text": json.dumps(_verdict(issues=["missing detail"], evidence=["round_1:fanout_req_doc"]))},
            }
        if op == "webai_chatgpt_send_prompt":
            return {"outcome": "ok", "status": "ok", "payload": {"response_text": "revised", "conversation_id": "conv_doc"}}
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": json.dumps(_verdict(issues=[], evidence=[]))}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    result = run_critique_loop(
        ACCOUNT,
        "task_reinject",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True, "conversation_id": "conv_doc"},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )
    assert result.status == "delivered"
    assert calls[1][0] == "webai_chatgpt_send_prompt"
    assert calls[1][1]["reuse_conversation"] is True
    assert result.artifact["conversation_id"] == "conv_doc"

    calls.clear()

    def missing_conv_dispatch(op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, {}))
        return {
            "outcome": "ok",
            "status": "ok",
            "payload": {"response_text": json.dumps(_verdict(issues=["missing detail"], evidence=["round_1:fanout_req_doc"]))},
        }

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", missing_conv_dispatch)
    capped = run_critique_loop(
        ACCOUNT,
        "task_reinject",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )
    assert capped.status == "capped"
    assert capped.reason == CAP_MESSAGE


def test_d22_bounded_rounds_and_user_gate_invariants(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_cap")
    revision_count = 0

    def local_task(payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        nonlocal revision_count
        assert timeout > 0
        if payload["kind"] == "critique_review":
            evidence = payload["evidence_node_ids"]
            verdict = _verdict(issues=["missing cited detail"], evidence=evidence)
            verdict["reviewer_family"] = payload["reviewer_family"]
            return {"ok": True, "verdict": verdict}
        revision_count += 1
        return {"ok": True, "artifact": {"text": f"revision {revision_count}"}, "score": revision_count / 10}

    monkeypatch.setattr(critique_mod, "run_local_task", local_task)
    capped = run_critique_loop(
        ACCOUNT,
        "task_cap",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft"},
        "round_1:fanout_req_doc",
    )
    assert capped.status == "capped"
    assert capped.terminated_by == "MAX_ROUNDS"
    assert any(CAP_MESSAGE in row["text"] for row in model.serialize_visible_conversation(ACCOUNT, "task_cap"))

    model.initialize_task_files(ACCOUNT, "task_taste")

    def taste_task(payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        assert timeout > 0
        evidence = payload["evidence_node_ids"]
        verdict = _verdict(issues=["tone preference taste issue"], evidence=evidence)
        verdict["reviewer_family"] = payload["reviewer_family"]
        return {"ok": True, "verdict": verdict}

    monkeypatch.setattr(critique_mod, "run_local_task", taste_task)
    deferred = run_critique_loop(
        ACCOUNT,
        "task_taste",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft"},
        "round_1:fanout_req_doc",
    )
    assert deferred.status == "deferred"
    assert deferred.decision_class == "taste"


def test_d22_reviewer_gate_off_defers_without_fabrication(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_review_gate_off")
    calls: list[object] = []
    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append((_args, _kwargs)) or {})

    result = run_critique_loop(
        ACCOUNT,
        "task_review_gate_off",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True, "conversation_id": "conv_doc"},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )

    assert result.status == "deferred"
    assert result.artifact["text"] == "draft"
    assert calls == []


def test_d22_web_reviewer_empty_verdicts_defer_without_fabrication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_empty_web_verdicts")
    # Concrete reviewer families always append or return early; emulate the guard seam directly.
    monkeypatch.setattr(critique_mod, "_uses_web_reviewer", lambda _families: True)

    result = run_critique_loop(
        ACCOUNT,
        "task_empty_web_verdicts",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True, "conversation_id": "conv_doc"},
        "round_1:fanout_req_doc",
        reviewer_families=(),
    )

    assert result.status == "deferred"
    assert result.reason == "web reviewer produced no conforming verdict"
    assert result.terminated_by == "deferred"
    assert result.status not in {"delivered", "capped"}
    assert result.rounds == []


def test_d22_two_zone_view_and_deliverables_stay_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _enable_hub(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = client.post("/platform/tasks", headers=_headers(token), json={"title": "D22 image"}).json()["task"]["task_id"]
    artifact_ref = f"tasks/{task_id}/artifacts/hero.png"
    resolved = resolve_user_path(ACCOUNT, artifact_ref)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(b"png")

    def dispatch(op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        if op == "webai_chatgpt_generate_image":
            return {"outcome": "ok", "status": "ok", "payload": {"path": artifact_ref, "conversation_id": "conv_img"}}
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": json.dumps(_verdict(issues=[], evidence=[]))}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={"requirements": [{"id": "req_image", "text": "Generate a hero image", "modality": "image"}]},
    )
    assert confirm.status_code == 200
    response = client.post(f"/platform/tasks/{task_id}/orchestrate", headers=_headers(token))
    deliverables = client.get(f"/platform/tasks/{task_id}/deliverables", headers=_headers(token)).json()["deliverables"]

    view = response.json()["view"]
    assert set(view) == {"conversation", "deliverables", "coarse_status", "capability_notice"}
    forbidden = {"conversation_url", "hub", "reviewer", "sha", "provenance", "conversation_id"}
    rendered = json.dumps({"view": view, "deliverables": deliverables}, ensure_ascii=False, sort_keys=True)
    assert not any(key in rendered for key in forbidden)
    requirements = model.load_requirements(ACCOUNT, task_id)["requirements"][0]
    assert set(requirements).issuperset({"id", "text", "modality", "capability_status", "coarse_state"})


def test_d22_selector_picks_web_workflow_and_existing_intents_regress() -> None:
    for modality in ("image", "video", "slides", "poster"):
        payload = model.stamp_confirmed_requirements("task_selector", [{"id": f"req_{modality}", "text": f"Create {modality}", "modality": modality}])
        assert select_workflow(payload).spec.id == "web_generate_and_cross_review"

    assert select_workflow(model.stamp_confirmed_requirements("task_selector", [{"id": "r", "text": "Research and compare sources", "modality": "research"}])).spec.id == "research_and_synthesize"
    assert select_workflow(model.stamp_confirmed_requirements("task_selector", [{"id": "d", "text": "Draft a document and revise it", "modality": "document"}])).spec.id == "document_draft_and_refine"
    assert select_workflow(model.stamp_confirmed_requirements("task_selector", [{"id": "c", "text": "Implement code fix", "modality": "code"}])).spec.id == "code_change_and_review"


def test_d22_frozen_files_and_contract_sidecar_are_unchanged() -> None:
    frozen = [
        "packages/noeticbraid-backend/src/noeticbraid_backend/platform/orchestration",
        "packages/noeticbraid-backend/src/noeticbraid_backend/omc_workspace",
        "packages/noeticbraid-backend/src/noeticbraid_backend/platform/conversation/model.py",
        "packages/noeticbraid-backend/src/noeticbraid_backend/app.py",
        "packages/noeticbraid-backend/src/noeticbraid_backend/platform/auth.py",
        "packages/noeticbraid-backend/src/noeticbraid_backend/api/routes/auth.py",
        "scripts/check_phase1_2_contract_gate.py",
        "pyproject.toml",
    ]
    # HEAD-relative (matches the D21 _match_git_head guard): catches any
    # uncommitted/unauthorized drift of the §1 frozen set, while not
    # permanently failing on a separately SDD-authorized, reviewed, shipped
    # frozen change (e.g. the SDD-D23 hub re-pin of web_ai_hub_compat.py).
    diff = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *frozen],
        cwd=REPO_ROOT,
        check=False,
    )
    assert diff.returncode == 0, "frozen §1 set changed vs HEAD (uncommitted/unauthorized)"

    # The contract "sidecar" is docs/contracts/phase1_2_openapi.yaml.sha256
    # (`<64 hex> *phase1_2_openapi.yaml`); 96ce4bac…839b7 is the SHA-256 *value*
    # the gate computes over the frozen OpenAPI bytes, not a file name. Pin both
    # the recorded sidecar digest and the actual frozen-contract content hash.
    expected_sha = "96ce4bac5e3c9f1c976e21bc68d32ff2ba02c5ef9fe16bb8189eb3fbfbf839b7"
    sidecar = REPO_ROOT / "docs" / "contracts" / "phase1_2_openapi.yaml.sha256"
    assert sidecar.is_file(), "contract sidecar missing"
    sidecar_sha, _, sidecar_name = sidecar.read_text(encoding="ascii").strip().partition(" *")
    assert sidecar_sha.lower() == expected_sha, "contract sidecar digest tampered"
    assert sidecar_name == "phase1_2_openapi.yaml", "contract sidecar target tampered"
    contract = REPO_ROOT / "docs" / "contracts" / "phase1_2_openapi.yaml"
    assert sidecar_sha.lower() == hashlib.sha256(contract.read_bytes()).hexdigest(), (
        "frozen OpenAPI contract bytes do not match the recorded sidecar digest"
    )

    gate = subprocess.run(
        ["python3", "scripts/check_phase1_2_contract_gate.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert gate.returncode == 0, gate.stderr
    assert "sidecar_sha256=96ce4bac5e3c9f1c976e21bc68d32ff2ba02c5ef9fe16bb8189eb3fbfbf839b7" in gate.stdout
