# SPDX-License-Identifier: Apache-2.0
"""Factories for Phase 1.1 core storage objects."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _import_core_attr(module_name: str, attr_name: str) -> Any:
    """Import a core storage attribute lazily so route fixtures remain lightweight."""

    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def create_run_ledger(root: Path | None = None) -> Any:
    """Create a `noeticbraid_core.RunLedger` when the core package is installed."""

    run_ledger = _import_core_attr("noeticbraid_core.ledger", "RunLedger")
    return run_ledger(root=root)


def create_source_index(root: Path | None = None) -> Any:
    """Create a `noeticbraid_core.FileBucketSourceIndex` when core is installed."""

    source_index = _import_core_attr("noeticbraid_core.source_index", "FileBucketSourceIndex")
    return source_index(root=root)


__all__ = ["create_run_ledger", "create_source_index"]
