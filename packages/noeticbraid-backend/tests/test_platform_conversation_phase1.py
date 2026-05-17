# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D18 Phase-1 conversational platform task panel tests."""

from __future__ import annotations

import json
import stat
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
from noeticbraid_backend.platform.artifacts.ledger import _ledger_rows
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.local_ai import LOCAL_AI_ARGS_ENV, LOCAL_AI_BIN_ENV, run_elicitation_probe
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.settings import Settings

ACCOUNT = "beta_user_01"
OTHER_ACCOUNT = "beta_user_02"
IMAGE_REASON_ZH = "图像生成目前还达不到，这部分我们暂时做不了。"


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


def _write_stub(tmp_path: Path, payload: dict[str, Any], *, sleep: float = 0, exit_code: int = 0, raw: str | None = None) -> Path:
    script = tmp_path / f"stub_{len(list(tmp_path.glob('stub_*.py')))}.py"
    if raw is not None:
        body = raw
    else:
        body = "\n".join(
            [
                "import json, sys, time",
                f"time.sleep({sleep!r})",
                "stdin = sys.stdin.read()",
                "payload = " + repr(json.dumps(payload, ensure_ascii=False)),
                "print(payload)",
                f"raise SystemExit({exit_code})",
            ]
        )
    script.write_text(body, encoding="utf-8")
    script.chmod(0o700)
    return script


def _configure_stub(monkeypatch: pytest.MonkeyPatch, script: Path) -> None:
    monkeypatch.setenv(LOCAL_AI_BIN_ENV, sys.executable)
    monkeypatch.setenv(LOCAL_AI_ARGS_ENV, json.dumps([str(script)]))


def _create_task(client: TestClient, token: str, title: str = "Conversation task") -> dict[str, Any]:
    response = client.post("/platform/tasks", headers=_headers(token), json={"title": title})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"task", "view"}
    assert set(payload["view"]) == {"conversation", "deliverables", "coarse_status", "capability_notice"}
    return payload["task"]


def _assert_no_engineering_fields(value: Any) -> None:
    forbidden = {"ledger", "dispatch", "critique", "internal_reason", "internal-reason"}
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for item in value.values():
            _assert_no_engineering_fields(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_engineering_fields(item)


def test_create_elicit_conversation_confirm_view_happy_path_with_honest_image_notice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    stub = _write_stub(
        tmp_path,
        {
            "interpretations": [
                {"deliverable": "Launch brief", "modality": "document", "workflow_intent": "draft", "assumptions": ["short"]},
                {"deliverable": "Hero image", "modality": "image", "workflow_intent": "visual", "assumptions": ["new art"]},
            ],
            "questions": [
                {
                    "axis": "modality",
                    "question": "Do you want a document, an image, or both?",
                    "suggested_answer": "Both: a brief and an image concept.",
                }
            ],
            "requirements": [
                {"id": "req_doc", "text": "Write a launch brief", "modality": "document"},
                {"id": "req_image", "text": "Generate a hero image", "modality": "image"},
            ],
            "ready_to_confirm": False,
        },
    )
    _configure_stub(monkeypatch, stub)

    task = _create_task(client, token)
    task_id = task["task_id"]
    req_path = model.requirements_path_for(ACCOUNT, task_id)
    convo_path = model.conversation_path_for(ACCOUNT, task_id)
    assert stat.S_IMODE(req_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(convo_path.stat().st_mode) == 0o600

    elicit = client.post(
        f"/platform/tasks/{task_id}/elicit",
        headers=_headers(token),
        json={"raw_requirement": "Create a launch brief and hero image."},
    )
    assert elicit.status_code == 200, elicit.text
    conversation = elicit.json()["view"]["conversation"]
    assert [row["kind"] for row in conversation] == ["message", "question"]
    assert "Suggested answer: Both" in conversation[-1]["text"]

    turn = client.post(
        f"/platform/tasks/{task_id}/conversation",
        headers=_headers(token),
        json={"text": "Both, but keep the image as an honest blocked item if unavailable."},
    )
    assert turn.status_code == 200, turn.text
    assert turn.json()["view"]["conversation"][-1]["role"] == "assistant"

    confirm = client.post(
        f"/platform/tasks/{task_id}/requirements/confirm",
        headers=_headers(token),
        json={
            "requirements": [
                {"id": "req_doc", "text": "Write a launch brief", "modality": "document"},
                {"id": "req_image", "text": "Generate a hero image", "modality": "image"},
            ]
        },
    )
    assert confirm.status_code == 200, confirm.text
    confirmed = confirm.json()["requirements"]
    assert confirmed["status"] == "confirmed"
    by_id = {item["id"]: item for item in confirmed["requirements"]}
    assert by_id["req_doc"]["capability_status"] == "supported"
    assert by_id["req_doc"]["coarse_state"] == "pending"
    assert by_id["req_image"]["capability_status"] == "unavailable"
    assert by_id["req_image"]["coarse_state"] == "blocked"
    assert by_id["req_image"]["blocked_reason"] == IMAGE_REASON_ZH

    view = client.get(f"/platform/tasks/{task_id}/view", headers=_headers(token))
    assert view.status_code == 200, view.text
    payload = view.json()
    assert set(payload) == {"conversation", "deliverables", "coarse_status", "capability_notice"}
    _assert_no_engineering_fields(payload)
    assert payload["capability_notice"] == [
        {
            "modality": "image",
            "capability_status": "unavailable",
            "reason": IMAGE_REASON_ZH,
            "reason_zh": IMAGE_REASON_ZH,
            "reason_en": "Image generation is not good enough yet, so we cannot do this part for now.",
        }
    ]
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "ledger" not in rendered
    assert "critique" not in rendered
    assert "internal_reason" not in rendered


def test_elicitation_convergence_adds_ready_to_confirm_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    stub = _write_stub(
        tmp_path,
        {
            "interpretations": [
                {"deliverable": "Research memo", "modality": "research", "workflow_intent": "research", "assumptions": ["memo"]},
                {"deliverable": "Research memo", "modality": "research", "workflow_intent": "research", "assumptions": ["memo"]},
            ],
            "questions": [],
            "requirements": [{"id": "req_research", "text": "Research the market", "modality": "research"}],
            "ready_to_confirm": True,
        },
    )
    _configure_stub(monkeypatch, stub)
    task = _create_task(client, token, "Research task")

    response = client.post(
        f"/platform/tasks/{task['task_id']}/elicit",
        headers=_headers(token),
        json={"raw_requirement": "Research the market."},
    )

    assert response.status_code == 200, response.text
    rows = response.json()["view"]["conversation"]
    assert rows[-1]["kind"] == "message"
    assert "review and confirm" in rows[-1]["text"]


def test_local_ai_subprocess_uses_fixed_argv_and_stdin_for_untrusted_payload(tmp_path: Path) -> None:
    script = tmp_path / "echo_argv.py"
    script.write_text(
        "import json, sys\n"
        "print(json.dumps({'argv': sys.argv, 'stdin': sys.stdin.read()}))\n",
        encoding="utf-8",
    )
    raw_requirement = "make a doc; --model unsafe $(touch /tmp/nope)"

    result = run_elicitation_probe(raw_requirement, argv=[sys.executable, str(script)])

    assert result["ok"] is True
    assert result["argv"] == [str(script)]
    assert raw_requirement not in json.dumps(result["argv"])
    assert raw_requirement in result["stdin"]


@pytest.mark.parametrize(
    ("script_body", "expected"),
    [
        ("import time\ntime.sleep(2)\n", "timeout"),
        ("import sys\nsys.stderr.write('token=secret path /tmp/private')\nsys.exit(7)\n", "non_zero_exit"),
        ("print('not json')\n", "json_parse_error"),
    ],
)
def test_local_ai_failures_return_allowlisted_error_dicts(
    tmp_path: Path,
    script_body: str,
    expected: str,
) -> None:
    script = tmp_path / f"failure_{expected}.py"
    script.write_text(script_body, encoding="utf-8")

    result = run_elicitation_probe("raw", argv=[sys.executable, str(script)], timeout=1)

    assert result["ok"] is False
    assert result["error_type"] == expected
    assert "secret" not in result["error"]
    assert str(tmp_path) not in result["error"]


def test_endpoint_degrades_to_single_question_and_logs_local_failure_only_to_engineering_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    stub = _write_stub(tmp_path, {}, raw="print('not json')\n")
    _configure_stub(monkeypatch, stub)
    task = _create_task(client, token, "Degrade task")

    response = client.post(
        f"/platform/tasks/{task['task_id']}/elicit",
        headers=_headers(token),
        json={"raw_requirement": "Write a report with a credential-shaped value built at runtime."},
    )

    assert response.status_code == 200, response.text
    rows = response.json()["view"]["conversation"]
    assert [row["kind"] for row in rows] == ["message", "question"]
    assert "exact deliverable" in rows[-1]["text"]
    assert "json_parse_error" not in json.dumps(response.json(), sort_keys=True)
    ledger_rows = _ledger_rows(ACCOUNT, task["task_id"])
    assert any(row["type"] == "ai_call" and row["payload"]["gate_status"] == "json_parse_error" for row in ledger_rows)


def test_confirm_gate_writes_memory_and_memory_stays_per_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    other_token = _token(data_root, OTHER_ACCOUNT)
    task = _create_task(client, token, "Memory task")
    assert model.load_memory_profile(ACCOUNT) is None

    response = client.post(
        f"/platform/tasks/{task['task_id']}/requirements/confirm",
        headers=_headers(token),
        json={
            "requirements": [
                {"id": "req_pref", "text": "Always prefer concise launch briefs", "modality": "document"},
                {"id": "req_image", "text": "Create a supporting image", "modality": "image"},
            ]
        },
    )

    assert response.status_code == 200, response.text
    profile = model.load_memory_profile(ACCOUNT)
    assert profile is not None
    assert profile["prefs"][0]["key"] == "confirmed_preference:req_pref"
    assert profile["prefs"][0]["evidence_conversation_ref"]
    assert profile["declared_capability_gaps"][0]["modality"] == "image"
    assert model.load_memory_profile(OTHER_ACCOUNT) is None
    assert client.get(f"/platform/tasks/{task['task_id']}/view", headers=_headers(other_token)).status_code == 404


def test_cross_account_404_and_legacy_task_without_requirements_is_confirmed_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    task_id = "task_legacy_conversation"
    create_task(ACCOUNT, task_id=task_id, title="Legacy task", modality_targets=["document"])
    token = _token(data_root)
    other_token = _token(data_root, OTHER_ACCOUNT)

    view = client.get(f"/platform/tasks/{task_id}/view", headers=_headers(token))
    assert view.status_code == 200, view.text
    assert view.json()["conversation"] == []
    assert view.json()["coarse_status"] == []
    assert model.load_requirements(ACCOUNT, task_id)["status"] == "confirmed"
    assert model.load_requirements(ACCOUNT, task_id)["legacy"] is True

    cross = client.get(f"/platform/tasks/{task_id}/view", headers=_headers(other_token))
    assert cross.status_code == 404
    assert cross.json() == {"detail": "not_found"}


def test_capabilities_endpoint_returns_frozen_honest_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)

    response = client.get("/platform/capabilities", headers=_headers(token))

    assert response.status_code == 200
    registry = {item["modality"]: item for item in response.json()["capabilities"]}
    assert registry["text"]["capability_status"] == "supported"
    assert registry["image"]["capability_status"] == "unavailable"
    assert registry["image"]["reason_zh"] == IMAGE_REASON_ZH
    assert registry["slides"]["capability_status"] == "deferred"
