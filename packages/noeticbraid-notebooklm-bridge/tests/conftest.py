from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


def main_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def phase1_2_contract_path() -> Path:
    explicit = os.environ.get("NOETICBRAID_CONTRACT_PATH")
    path = Path(explicit) if explicit else main_repo_root() / "docs" / "contracts" / "phase1_2_openapi.yaml"
    assert path.is_file(), f"missing contract: {path}"
    return path


@pytest.fixture(scope="session")
def source_record_contract(phase1_2_contract_path: Path) -> dict:
    import yaml

    data = yaml.safe_load(phase1_2_contract_path.read_text(encoding="utf-8"))
    return data["components"]["schemas"]["SourceRecord"]


@pytest.fixture(scope="session")
def run_record_contract(phase1_2_contract_path: Path) -> dict:
    import yaml

    data = yaml.safe_load(phase1_2_contract_path.read_text(encoding="utf-8"))
    return data["components"]["schemas"]["RunRecord"]


class FakeC2Session:
    """Current noeticbraid-runtime BrowserSession-shaped fake.

    It intentionally has eval/click(x, y)/type_text(text), not evaluate/wait_for or
    click(selector)/type_text(selector, text).
    """

    tab_id = "tab_test"
    cdp_url = "ws://127.0.0.1/devtools/page/tab_test"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.events: list[dict] = []
        self.visible_text: dict[str, str] = {
            "briefing_content": "Briefing Doc\nSynthesized grounded answer.",
        }
        self.faq_items = [{"q": "What is SP-H?", "a": "The NotebookLM bridge."}]
        self.login_required = False

    @property
    def call_names(self) -> list[str]:
        return [name for name, _args in self.calls]

    def navigate(self, url: str, timeout_s: int = 30) -> None:
        self.calls.append(("navigate", (url, timeout_s)))

    def eval(self, expression: str, await_promise: bool = True, timeout_s: int = 30):
        self.calls.append(("eval", (expression, await_promise, timeout_s)))
        if "notebooklm_bridge:login_required" in expression:
            return self.login_required
        if "notebooklm_bridge:resolve_target" in expression:
            return {"x": 10, "y": 20, "found": True}
        if "notebooklm_bridge:any_present" in expression:
            return True
        if "notebooklm_bridge:extract_text:briefing_content" in expression:
            return self.visible_text.get("briefing_content", "")
        if "notebooklm_bridge:extract_faq" in expression:
            return self.faq_items
        return True

    def click(self, x: float, y: float, timeout_s: int = 30) -> None:
        self.calls.append(("click", (x, y, timeout_s)))

    def type_text(self, text: str, timeout_s: int = 30) -> None:
        self.calls.append(("type_text", (text, timeout_s)))

    def screenshot(self, save_to: str, timeout_s: int = 30) -> int:
        self.calls.append(("screenshot", (save_to, timeout_s)))
        return 0

    def close(self) -> None:
        self.calls.append(("close", ()))

    def emit_event(self, event: dict) -> None:
        self.events.append(json.loads(json.dumps(event)))


@pytest.fixture
def fake_c2_session() -> FakeC2Session:
    return FakeC2Session()


def assert_pattern(value: str, pattern: str) -> None:
    assert re.fullmatch(pattern, value), f"{value!r} does not match {pattern}"
