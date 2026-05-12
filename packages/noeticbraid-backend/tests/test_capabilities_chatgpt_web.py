# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

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


def test_chatgpt_web_health_check_default_mock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("mock mode must not call web-ai-capability-hub")

    monkeypatch.setattr(target_module.web_ai_hub_client, "run_hub_command", explode)

    payload = health_check("cap_chatgpt_web", project_root=tmp_path)

    assert payload["result"]["mode"] == "mock"
    assert payload["result"]["status"] == "available"
    assert payload["result"]["artifact_ref"] is None
    assert not (tmp_path / ".omx" / "artifacts").exists()


def test_chatgpt_web_health_check_live_env_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.delenv("NOETICBRAID_WEB_AI_HUB_PATH", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("hub path env gate must block subprocess helpers")

    monkeypatch.setattr(target_module.web_ai_hub_client, "check_hub_browser_status", explode)

    missing = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]
    assert missing["status"] == "not_implemented"
    assert missing["error_msg"] == "Hub path not configured (NOETICBRAID_WEB_AI_HUB_PATH unset)"

    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setattr(target_module.web_ai_hub_client, "check_hub_browser_status", lambda _path: {"connected": True, "lastError": None})
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "get_chatgpt_pages",
        lambda _path: [{"id": "page_1", "url": "https://chatgpt.com/", "title": "ChatGPT"}],
    )

    healthy = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]

    assert healthy["mode"] == "live_opt_in"
    assert healthy["status"] == "healthy"
    assert healthy["version"] == "ChatGPT"
    assert healthy["last_checked"] is not None


def test_chatgpt_web_sanitize_forbidden_fields_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setenv("USER", "l1u")
    monkeypatch.setattr(target_module.web_ai_hub_client, "check_hub_browser_status", lambda _path: {"connected": True, "lastError": None})
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "get_chatgpt_pages",
        lambda _path: [
            {
                "id": "page_1",
                "url": "https://chatgpt.com/",
                "title": "ChatGPT alice@example.com token=secret /home/l1u/private",
                "cookies": "must-not-propagate",
                "cdp_endpoint": "ws://127.0.0.1/devtools/browser/secret",
            }
        ],
    )

    payload = health_check("cap_chatgpt_web", project_root=tmp_path)
    serialized = json.dumps(payload, ensure_ascii=False)
    artifact = _artifact_payload(tmp_path, payload["result"])
    all_keys = {key.lower() for key in _all_keys(payload)} | {key.lower() for key in _all_keys(artifact)}

    forbidden_fields = {
        "cookies",
        "session",
        "session_token",
        "authorization",
        "account_name",
        "email",
        "full_html",
        "dom",
        "raw_snapshot",
        "cdp_endpoint",
    }
    assert forbidden_fields.isdisjoint(all_keys)
    assert "alice@example.com" not in serialized
    assert "secret" not in serialized
    assert "/home/l1u" not in serialized
    assert len(payload["result"]["version"]) <= 64


def test_chatgpt_web_live_artifact_written_with_sdd_d2_06_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("NOETICBRAID_WEB_AI_HUB_PATH", str(tmp_path))
    monkeypatch.setattr(target_module.web_ai_hub_client, "check_hub_browser_status", lambda _path: {"connected": True, "lastError": None})
    monkeypatch.setattr(
        target_module.web_ai_hub_client,
        "get_chatgpt_pages",
        lambda _path: [{"id": "page_1", "url": "https://chatgpt.com/", "title": "ChatGPT"}],
    )

    result = health_check("cap_chatgpt_web", project_root=tmp_path)["result"]
    artifact = _artifact_payload(tmp_path, result)

    assert result["artifact_ref"].startswith(".omx/artifacts/health-check-cap_chatgpt_web-")
    assert artifact["sdd_id"] == "SDD-D2-06"
    assert artifact["sdd_id"] != "SDD-D2-03"
    assert artifact["capability_id"] == "cap_chatgpt_web"
    assert artifact["status"] == "healthy"
