# SPDX-License-Identifier: Apache-2.0
"""Package resource helpers for embedded SP-D contracts and fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "obsidian-hub-0.1"
CONTRACT_VERSION = "1.3.0"


def resource_root() -> Path:
    """Return the package resource directory."""

    return Path(__file__).resolve().parent


def load_schema(name: str) -> dict[str, Any]:
    """Load one embedded JSON schema by stem name.

    Examples: ``load_schema("task_note")`` and ``load_schema("write_policy")``.
    """

    path = resource_root() / "schemas" / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_resource(relative: str) -> Any:
    """Load a JSON resource relative to the package root."""

    return json.loads((resource_root() / relative).read_text(encoding="utf-8"))
