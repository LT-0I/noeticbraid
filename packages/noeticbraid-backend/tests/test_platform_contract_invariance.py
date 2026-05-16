# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Platform mount must not perturb the frozen runtime OpenAPI contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from starlette.routing import Mount

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings

_GATE_PATH = REPO_ROOT / "scripts" / "check_phase1_2_contract_gate.py"
_SPEC = importlib.util.spec_from_file_location("check_phase1_2_contract_gate", _GATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
contract_gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = contract_gate
_SPEC.loader.exec_module(contract_gate)

FROZEN_SIDECAR_SHA256 = "96ce4bac5e3c9f1c976e21bc68d32ff2ba02c5ef9fe16bb8189eb3fbfbf839b7"
FROZEN_RUNTIME_PATHS = sorted(str(route["path"]) for route in contract_gate.EXPECTED_RUNTIME_ROUTES)
FROZEN_RUNTIME_SCHEMAS = set(contract_gate.EXPECTED_RUNTIME_SCHEMA_NAMES)


def _settings(tmp_path: Path) -> Settings:
    return Settings(state_dir=tmp_path / "state")


@pytest.mark.parametrize("enabled", [False, True], ids=["platform_flag_unset", "platform_flag_enabled"])
def test_real_app_contract_gate_is_invariant_across_platform_flag_states(
    enabled: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    if enabled:
        monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    else:
        monkeypatch.delenv("NOETICBRAID_PLATFORM_ENABLED", raising=False)

    app = create_app(_settings(tmp_path))
    schema = app.openapi()

    assert sorted(schema["paths"]) == FROZEN_RUNTIME_PATHS
    assert set(schema.get("components", {}).get("schemas", {})) == FROZEN_RUNTIME_SCHEMAS

    report = contract_gate.run_checks(REPO_ROOT)
    assert report.sidecar_sha256 == FROZEN_SIDECAR_SHA256
    assert report.contract_sha256 == FROZEN_SIDECAR_SHA256
    assert sorted(report.runtime_paths) == FROZEN_RUNTIME_PATHS
    assert set(report.runtime_schema_names) == FROZEN_RUNTIME_SCHEMAS

    mounted_paths = [route.path for route in app.routes if isinstance(route, Mount)]
    if enabled:
        assert "/platform" in mounted_paths
    else:
        assert "/platform" not in mounted_paths
        assert not data_root.exists()
