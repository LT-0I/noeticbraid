# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 platform import boundary tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

PLATFORM_ROOT = SRC_ROOT / "noeticbraid_backend" / "platform"
HUB_IMPORT = "noeticbraid_backend.omc_workspace.web_ai_hub_automation"
DISALLOWED_AI_ESCAPE_IMPORT_ROOTS = {"aiohttp", "http", "httpx", "requests", "socket", "subprocess", "urllib"}


def _py_files() -> list[Path]:
    return sorted(path for path in PLATFORM_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
                modules.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_only_hub_adapter_imports_web_ai_hub_automation() -> None:
    importers: list[str] = []
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(module == HUB_IMPORT for module in _imported_modules(tree)):
            importers.append(path.relative_to(PLATFORM_ROOT).as_posix())

    assert importers == ["orchestration/hub_adapter.py"]


def test_platform_has_no_direct_raw_ai_call_escape_imports() -> None:
    findings: list[str] = []
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_modules(tree):
            root = module.split(".", 1)[0]
            if root in DISALLOWED_AI_ESCAPE_IMPORT_ROOTS:
                findings.append(f"{path.relative_to(PLATFORM_ROOT).as_posix()}:{module}")

    assert findings == []


def test_hub_adapter_does_not_widen_hub_gating() -> None:
    source = (PLATFORM_ROOT / "orchestration" / "hub_adapter.py").read_text(encoding="utf-8")

    assert "WAH_AUTO_CONFIRM" not in source
    assert "confirmed" not in source
    assert "environ" not in source
