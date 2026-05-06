from __future__ import annotations

import json
from pathlib import Path

import pytest

from noeticbraid_runtime.browser.selector_store import SelectorStore, SelectorStoreError


def test_selector_store_loads_and_reloads_selector_json(tmp_path: Path) -> None:
    path = tmp_path / "selectors.json"
    path.write_text(json.dumps({"notebooklm": {"new_source": "button.add", "ask_box": ["textarea", "div[role=textbox]"]}}), encoding="utf-8")

    store = SelectorStore.load(path)
    assert store.get("notebooklm", "new_source") == ["button.add"]
    assert store.get("notebooklm", "ask_box") == ["textarea", "div[role=textbox]"]

    path.write_text(json.dumps({"notebooklm": {"new_source": "button.changed"}}), encoding="utf-8")
    store.reload()

    assert store.get("notebooklm", "new_source") == ["button.changed"]
    assert store.get("missing", "key") == []


def test_selector_store_fails_closed_on_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "selectors.json"
    path.write_text(json.dumps({"scope": {"bad": 42}}), encoding="utf-8")

    with pytest.raises(SelectorStoreError, match="invalid selector"):
        SelectorStore.load(path)
