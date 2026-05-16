# SPDX-License-Identifier: Apache-2.0
"""Mounted ASGI sub-application for the additive platform shell."""

from __future__ import annotations

from fastapi import FastAPI


def build_platform_app() -> FastAPI:
    """Build the isolated platform sub-app mounted by the main app factory."""

    app = FastAPI(title="NoeticBraid Platform", version="0.1.0")
    from noeticbraid_backend.platform.ws.endpoint import register_platform_ws_routes

    register_platform_ws_routes(app)

    @app.get("/health", summary="Platform health check")
    async def platform_health() -> dict[str, str]:
        return {"status": "ok"}

    return app


__all__ = ["build_platform_app"]
