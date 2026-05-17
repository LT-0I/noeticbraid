# SPDX-License-Identifier: Apache-2.0
"""Mounted ASGI sub-application for the additive platform shell."""

from __future__ import annotations

from fastapi import FastAPI


def build_platform_app() -> FastAPI:
    """Build the isolated platform sub-app mounted by the main app factory."""

    app = FastAPI(title="NoeticBraid Platform", version="0.1.0")
    from noeticbraid_backend.platform.artifacts.endpoint import register_platform_artifact_routes
    from noeticbraid_backend.platform.auth_session.endpoint import register_platform_auth_session_routes
    from noeticbraid_backend.platform.conversation.endpoint import register_platform_conversational_routes
    from noeticbraid_backend.platform.deliverable.endpoint import register_platform_deliverable_routes
    from noeticbraid_backend.platform.stt.endpoint import register_platform_stt_routes
    from noeticbraid_backend.platform.tasks.endpoint import register_platform_task_routes
    from noeticbraid_backend.platform.ws.endpoint import register_platform_ws_routes

    register_platform_task_routes(app)
    register_platform_artifact_routes(app)
    register_platform_conversational_routes(app)
    register_platform_deliverable_routes(app)
    register_platform_auth_session_routes(app)
    register_platform_stt_routes(app)
    register_platform_ws_routes(app)

    @app.get("/health", summary="Platform health check")
    async def platform_health() -> dict[str, str]:
        return {"status": "ok"}

    return app


__all__ = ["build_platform_app"]
