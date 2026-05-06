from __future__ import annotations

import json
from pathlib import Path

import pytest

from noeticbraid.tools.notebooklm_bridge import NotebookLMSelectorError
from noeticbraid.tools.notebooklm_bridge._selectors import REQUIRED_SELECTOR_KEYS, SelectorStore


def test_default_selectors_are_scoped_and_complete() -> None:
    store = SelectorStore.load_default()
    for key in REQUIRED_SELECTOR_KEYS:
        assert store.get("notebooklm", key), key


def test_selector_store_rejects_missing_required_key(tmp_path: Path) -> None:
    path = tmp_path / "selectors.json"
    path.write_text(json.dumps({"notebooklm": {"add_source_button": "text=Add source"}}), encoding="utf-8")

    with pytest.raises(NotebookLMSelectorError, match="missing"):
        SelectorStore.load(path)


def _minimal_selector_payload() -> dict:
    from noeticbraid.tools.notebooklm_bridge._selectors import REQUIRED_SELECTOR_KEYS

    return {"version": "0.2.0", "notes": "test", "notebooklm": {key: "css=[data-test]" for key in REQUIRED_SELECTOR_KEYS}}


def test_default_selectors_do_not_use_overbroad_text_fallbacks() -> None:
    store = SelectorStore.load_default()
    assert "text=Sources" not in store.get("notebooklm", "source_ready_indicator")
    assert "text=Briefing" not in store.get("notebooklm", "briefing_content")


def test_load_selectors_env_override(tmp_path, monkeypatch) -> None:
    custom = tmp_path / "custom_selectors.json"
    custom.write_text(json.dumps(_minimal_selector_payload()), encoding="utf-8")
    monkeypatch.setenv("NOETICBRAID_NOTEBOOKLM_SELECTORS", str(custom))

    from noeticbraid.tools.notebooklm_bridge._browser_ops import _load_selectors

    store = _load_selectors()
    assert isinstance(store, SelectorStore)
    assert store.first("add_source_button") == "css=[data-test]"
