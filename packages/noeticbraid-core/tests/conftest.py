"""Pytest helpers for Stage 1 candidate schema tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = CORE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> dict[str, Any]:
    """Read a fixture and remove non-model metadata fields."""

    data = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    data.pop("$schema_status", None)
    data.pop("contract_version", None)
    return data


@pytest.fixture
def load_schema_fixture():
    """Return a fixture loader that strips schema metadata before validation."""

    return read_fixture
