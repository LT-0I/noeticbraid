# SPDX-License-Identifier: Apache-2.0
"""Hot-reloadable selector store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SelectorStoreError(Exception):
    """Raised when selector configuration cannot be trusted."""


class SelectorStore:
    """Load and hot-reload selectors from a small JSON file.

    Expected shape:

    ```json
    {
      "scope": {
        "selector_name": "css selector",
        "fallbacks": ["css one", "css two"]
      }
    }
    ```
    """

    def __init__(self, path: Path, selectors: dict[str, dict[str, list[str]]]) -> None:
        self.path = Path(path)
        self._selectors = selectors

    @classmethod
    def load(cls, path: str | Path) -> "SelectorStore":
        """Load selectors from `path`."""

        resolved = Path(path)
        return cls(resolved, _read_selectors(resolved))

    def reload(self) -> None:
        """Reload selectors from the original path."""

        self._selectors = _read_selectors(self.path)

    def get(self, scope: str, key: str) -> list[str]:
        """Return selectors for scope/key, or an empty list when missing.

        The returned list is a newly allocated detached copy; mutating it does not
        affect the store's internal state.
        """

        return list(self._selectors.get(scope, {}).get(key, []))

    def as_dict(self) -> dict[str, dict[str, list[str]]]:
        """Return a defensive copy for diagnostics."""

        return {scope: {key: list(values) for key, values in mapping.items()} for scope, mapping in self._selectors.items()}


def _read_selectors(path: Path) -> dict[str, dict[str, list[str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise SelectorStoreError(f"invalid selector file {path.name}") from None
    if not isinstance(payload, dict):
        raise SelectorStoreError("invalid selector root: expected object")
    parsed: dict[str, dict[str, list[str]]] = {}
    for scope, raw_mapping in payload.items():
        if not isinstance(scope, str) or not isinstance(raw_mapping, dict):
            raise SelectorStoreError("invalid selector scope")
        parsed[scope] = {}
        for key, raw_value in raw_mapping.items():
            if not isinstance(key, str):
                raise SelectorStoreError("invalid selector key")
            if isinstance(raw_value, str):
                values = [raw_value]
            elif isinstance(raw_value, list) and all(isinstance(item, str) and item.strip() for item in raw_value):
                values = [item.strip() for item in raw_value]
            else:
                raise SelectorStoreError("invalid selector value")
            parsed[scope][key] = values
    return parsed


__all__ = ["SelectorStore", "SelectorStoreError"]
