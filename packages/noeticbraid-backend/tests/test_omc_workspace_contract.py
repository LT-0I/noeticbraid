# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (REPO_ROOT / "packages" / "noeticbraid-core" / "src", PACKAGE_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.contracts import CONTRACT_1_3_ROUTE_SPECS, CONTRACT_VERSION, OMC_WORKSPACE_ROUTE_SPECS


def test_contract_version_minor_bump_only_to_1_4_0() -> None:
    assert CONTRACT_VERSION == "1.4.0"
    assert not CONTRACT_VERSION.startswith("2.")


def test_new_omc_routes_in_frozen_route_specs() -> None:
    route_paths = {(spec["method"], spec["path"]) for spec in CONTRACT_1_3_ROUTE_SPECS}
    new_paths = {(spec["method"], spec["path"]) for spec in OMC_WORKSPACE_ROUTE_SPECS}

    assert new_paths == {
        ("POST", "/api/projects/omc-ingest/tasks"),
        ("GET", "/api/projects/omc-ingest/candidates"),
        ("GET", "/api/projects/omc-ingest/adopted-history"),
        ("POST", "/api/candidates/{id}/adopt"),
        ("GET", "/api/capabilities"),
        ("POST", "/api/capabilities/{id}/health-check"),
    }
    assert new_paths.issubset(route_paths)
