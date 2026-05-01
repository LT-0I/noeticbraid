# SPDX-License-Identifier: Apache-2.0
"""Startup-token endpoint contract invariants."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings


def _app(tmp_path: Path):
    return create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None))


def test_startup_token_openapi_has_no_request_body(tmp_path: Path) -> None:
    app = _app(tmp_path)
    operation = app.openapi()["paths"]["/api/auth/startup_token"]["post"]
    assert "requestBody" not in operation
    assert "parameters" not in operation or operation["parameters"] == []


def test_startup_token_route_has_no_body_field(tmp_path: Path) -> None:
    app = _app(tmp_path)
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/auth/startup_token"
    ]
    assert len(routes) == 1
    route = routes[0]
    assert route.body_field is None
    assert route.dependant.body_params == []
    assert route.dependant.query_params == []
    assert route.dependant.header_params == []


def test_startup_token_accepts_empty_or_ignored_json_body(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    assert client.post("/api/auth/startup_token").json() == {
        "accepted": False,
        "mode": "stage1_skeleton",
    }
    assert client.post("/api/auth/startup_token", json={"ignored": True}).json() == {
        "accepted": False,
        "mode": "stage1_skeleton",
    }
