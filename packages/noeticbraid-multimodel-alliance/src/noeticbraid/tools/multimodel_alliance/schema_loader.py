"""Load packaged schemas and fixtures for the SP-B runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import SCHEMA_BY_RECORD

PACKAGE_DIR = Path(__file__).resolve().parent
SCHEMA_DIR = PACKAGE_DIR / "schemas"
FIXTURE_DIR = PACKAGE_DIR / "fixtures"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_schema(record_type: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_BY_RECORD[record_type]
    except KeyError as exc:
        raise KeyError(f"unknown schema record type: {record_type}") from exc
    return load_json(SCHEMA_DIR / filename)


def load_fixture(filename: str) -> dict[str, Any]:
    return load_json(FIXTURE_DIR / filename)
