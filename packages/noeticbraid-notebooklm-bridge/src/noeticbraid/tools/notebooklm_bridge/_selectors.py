"""Scoped selector configuration for NotebookLM UI automation."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from ._errors import NotebookLMSelectorError

DEFAULT_SCOPE = "notebooklm"
REQUIRED_SELECTOR_KEYS: tuple[str, ...] = (
    "add_source_button",
    "source_url_tab",
    "source_text_tab",
    "source_url_input",
    "source_title_input",
    "source_text_input",
    "source_submit_button",
    "source_ready_indicator",
    "briefing_generate_button",
    "briefing_refresh_button",
    "briefing_content",
    "faq_generate_button",
    "faq_item",
    "faq_question",
    "faq_answer",
    "login_required_signal",
)


class SelectorStore:
    """Load and validate scope/key selector mappings.

    Shape matches the current C2 selector-store style: ``{"scope": {"key":
    "selector" | ["selector", ...]}}``. The default scope is ``notebooklm``.
    """

    def __init__(self, selectors: dict[str, dict[str, list[str]]], *, path: Path | None = None) -> None:
        self.path = path
        self._selectors = selectors
        self.validate(DEFAULT_SCOPE, REQUIRED_SELECTOR_KEYS)

    @classmethod
    def load_default(cls) -> "SelectorStore":
        with resources.files(__package__).joinpath("selectors.json").open("r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)
        return cls.from_mapping(raw)

    @classmethod
    def load(cls, path: str | Path) -> "SelectorStore":
        resolved = Path(path)
        with resolved.open("r", encoding="utf-8-sig") as fh:
            raw = json.load(fh)
        return cls.from_mapping(raw, path=resolved)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], *, path: Path | None = None) -> "SelectorStore":
        if not isinstance(raw, dict):
            raise NotebookLMSelectorError("Selector configuration root must be a JSON object.")
        payload = raw.get("selectors", raw)
        if not isinstance(payload, dict):
            raise NotebookLMSelectorError("Selector configuration must contain an object mapping scopes to keys.")
        parsed: dict[str, dict[str, list[str]]] = {}
        for scope, mapping in payload.items():
            if scope in {"version", "notes"} or str(scope).startswith("$"):
                continue
            if not isinstance(scope, str) or not isinstance(mapping, dict):
                raise NotebookLMSelectorError("Selector scope must map to an object of selector keys.")
            parsed[scope] = {str(key): _normalize_candidates(str(key), value) for key, value in mapping.items()}
        return cls(parsed, path=path)

    def reload(self) -> None:
        if self.path is None:
            raise NotebookLMSelectorError("Cannot reload package-default selectors without an explicit path.")
        self._selectors = SelectorStore.load(self.path)._selectors

    def validate(self, scope: str, required_keys: Iterable[str]) -> None:
        missing = [key for key in required_keys if not self._selectors.get(scope, {}).get(key)]
        if missing:
            raise NotebookLMSelectorError(
                "Selector configuration is missing required notebooklm keys: "
                + ", ".join(sorted(missing))
            )

    def get(self, scope: str, key: str) -> list[str]:
        return list(self._selectors.get(scope, {}).get(key, []))

    def candidates(self, key: str, *, scope: str = DEFAULT_SCOPE) -> list[str]:
        values = self.get(scope, key)
        if not values:
            raise NotebookLMSelectorError(f"Selector key {scope}.{key} is not configured.")
        return values

    def first(self, key: str, *, scope: str = DEFAULT_SCOPE) -> str:
        return self.candidates(key, scope=scope)[0]

    def as_dict(self) -> dict[str, dict[str, list[str]]]:
        return {scope: {key: list(values) for key, values in mapping.items()} for scope, mapping in self._selectors.items()}


def _normalize_candidates(key: str, value: Any) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise NotebookLMSelectorError(f"Selector key '{key}' must be a string or list of strings.")
    cleaned: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise NotebookLMSelectorError(f"Selector key '{key}' contains a non-string or blank candidate.")
        cleaned.append(item.strip())
    return cleaned
