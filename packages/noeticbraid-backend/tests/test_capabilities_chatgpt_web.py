# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (REPO_ROOT / "packages" / "noeticbraid-core" / "src", PACKAGE_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace import capability_registry as target_module

health_check = target_module.health_check
FIXTURE_PATH = PACKAGE_ROOT / "tests" / "fixtures" / "chatgpt_web_consumer_health_mock.json"


def _fixture(name: str) -> dict[str, Any]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(data["scenarios"][name])


def _artifact_payload(tmp_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    artifact_ref = result["artifact_ref"]
    assert artifact_ref is not None
    artifact_path = tmp_path / artifact_ref
    assert artifact_path.exists()
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_all_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_all_keys(item))
        return keys
    return set()


def test_cap_chatgpt_web_entry_exists() -> None:
    capabilities = target_module.list_capabilities()
    entry = next(item for item in capabilities if item["capability_id"] == "cap_chatgpt_web")
    internal = next(item for item in target_module.CAPABILITIES if item["capability_id"] == "cap_chatgpt_web")

    assert entry["display_name"] == "ChatGPT Web"
    assert entry["end_type"] == "web"
    assert entry["status"] == "not_implemented"
    assert internal["command"] is None


def test_chatgpt_web_consumer_health_fixture_contains_four_hub_scenarios() -> None:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert set(data["scenarios"]) == {
        "connected-chatgpt-page",
        "connected-no-chatgpt-page",
        "disconnected",
        "command-timeout",
    }


def test_chatgpt_web_health_check_default_mock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("mock mode must not call web-ai-capability-hub")

    monkeypatch.setattr(target_module.web_ai_hub_client, "check_chatgpt_consumer_health", explode)

    payload = health_check("cap_chatgpt_web", project_root=tmp_path)

    assert payload["result"]["mode"] == "mock"
    assert payload["result"]["status"] == "available"
    assert payload["result"]["artifact_ref"] is None
    assert not (tmp_path / ".omx" / "artifacts").exists()


def test_chatgpt_web_health_check_live_env_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.delenv("NOETICBRAID_WEB_AI_HUB_PATH", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("hub path env gate must block subprocess helper")

    monkeypatch.setattr(target_module.web_ai_hub_client, "check_chatgpt_consumer_health", explode)

    missing = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]
    assert missing["status"] == "not_implemented"
    assert missing["error_msg"] == "Hub path not configured (NOETICBRAID_WEB_AI_HUB_PATH unset)"

    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", "relative/hub")
    relative = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]
    assert relative["status"] == "not_implemented"
    assert relative["error_msg"] == "web-ai-capability-hub 未配置或未启动"


def test_chatgpt_web_health_check_live_uses_single_consumer_health_call(tmp_path: Path, monkeypatch) -> None:
    calls: list[Path] = []
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))

    def fake_consumer_health(hub_path: Path) -> dict[str, Any]:
        calls.append(hub_path)
        return _fixture("connected-chatgpt-page")

    monkeypatch.setattr(target_module.web_ai_hub_client, "check_chatgpt_consumer_health", fake_consumer_health)

    healthy = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]

    assert calls == [tmp_path]
    assert healthy["mode"] == "live_opt_in"
    assert healthy["status"] == "healthy"
    assert healthy["version"] == "connected:healthy"
    assert healthy["error_msg"] is None
    assert healthy["last_checked"].startswith("2026-05-13T08:29:20.508")


def test_chatgpt_web_health_check_error_code_downgrades_to_unhealthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "check_chatgpt_consumer_health",
        lambda _path: _fixture("connected-no-chatgpt-page"),
    )

    result = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert result["version"] == "connected:not_implemented"
    assert result["error_msg"] == "TARGET_PAGE_MISSING: Target page missing in managed browser."


def test_chatgpt_web_health_check_disconnected_version(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "check_chatgpt_consumer_health",
        lambda _path: _fixture("disconnected"),
    )

    result = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert result["version"] == "disconnected"
    assert result["error_msg"] == "BROWSER_NOT_LAUNCHED: Managed browser is not launched."


def test_chatgpt_web_sanitize_forbidden_fields_absent_from_result_and_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setenv("USER", "l1u")
    malformed_health = _fixture("connected-no-chatgpt-page")
    malformed_health.update(
        {
            "message": "alice@example.com token=secret /home/l1u/private http://127.0.0.1:9222",
            "cdpEndpoint": "http://127.0.0.1:9222",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/secret",
            "profileDir": "/home/l1u/private-profile",
            "accountEmail": "alice@example.com",
            "cookies": [{"name": "session", "value": "must-not-propagate"}],
        }
    )
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "check_chatgpt_consumer_health",
        lambda _path: malformed_health,
    )

    payload = health_check("cap_chatgpt_web", project_root=tmp_path)
    serialized = json.dumps(payload, ensure_ascii=False)
    artifact = _artifact_payload(tmp_path, payload["result"])
    all_keys = {key.lower() for key in _all_keys(payload)} | {key.lower() for key in _all_keys(artifact)}

    forbidden_fields = {
        "cookies",
        "cookie",
        "session",
        "session_token",
        "authorization",
        "account_name",
        "accountemail",
        "account_email",
        "email",
        "full_html",
        "dom",
        "raw_snapshot",
        "rawsnapshot",
        "cdpendpoint",
        "cdp_endpoint",
        "websocketdebuggerurl",
        "profiledir",
        "profile_dir",
        "executablepath",
    }
    assert forbidden_fields.isdisjoint(all_keys)
    assert "alice@example.com" not in serialized
    assert "secret" not in serialized
    assert "/home/l1u" not in serialized
    assert "http://127.0.0.1:9222" not in serialized
    assert "TARGET_PAGE_MISSING:" in payload["result"]["error_msg"]
    assert len(payload["result"]["version"]) <= 256


def test_chatgpt_web_live_artifact_written_with_hotfix_sdd_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "check_chatgpt_consumer_health",
        lambda _path: _fixture("connected-chatgpt-page"),
    )

    result = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]
    artifact = _artifact_payload(tmp_path, result)

    assert result["artifact_ref"].startswith(".omx/artifacts/health-check-cap_chatgpt_web-")
    assert artifact["sdd_id"] == "SDD-D2-06-hotfix-02"
    assert artifact["sdd_id"] != "SDD-D2-06"
    assert artifact["capability_id"] == "cap_chatgpt_web"
    assert artifact["status"] == "healthy"
