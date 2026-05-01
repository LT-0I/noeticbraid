# SPDX-License-Identifier: Apache-2.0
"""FastAPI application factory for the NoeticBraid backend skeleton."""

from __future__ import annotations

import importlib
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from noeticbraid_backend.api.routes import account, approval, auth, dashboard, health, ledger, workspace
from noeticbraid_backend.contracts import CONTRACT_VERSION, CORE_SCHEMA_MODELS, OPENAPI_TITLE
from noeticbraid_backend.settings import Settings

LOGGER = logging.getLogger(__name__)

DEV_CORS_ORIGINS = (
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


def _build_custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Build OpenAPI with the unreferenced Phase 1.1 core schemas included."""

    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    component_schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    for model in CORE_SCHEMA_MODELS:
        component_schemas.setdefault(
            model.__name__,
            model.model_json_schema(ref_template="#/components/schemas/{model}"),
        )

    app.openapi_schema = schema
    return app.openapi_schema


def _validate_core_imports(app: FastAPI) -> None:
    """Record whether the Phase 1.1 core package is importable in this runtime."""

    try:
        importlib.import_module("noeticbraid_core")
    except Exception as exc:
        LOGGER.warning("noeticbraid_core import check failed in skeleton runtime: %s", exc)
        app.state.core_import_ok = False
        app.state.core_import_error = repr(exc)
    else:
        app.state.core_import_ok = True
        app.state.core_import_error = None


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Phase 1.2 Stage 1 FastAPI application."""

    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _validate_core_imports(app)
        yield

    app = FastAPI(
        title=OPENAPI_TITLE,
        version=CONTRACT_VERSION,
        openapi_version="3.0.3",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(workspace.router)
    app.include_router(approval.router)
    app.include_router(account.router)
    app.include_router(ledger.router)
    app.openapi = lambda: _build_custom_openapi(app)

    return app


__all__ = ["create_app"]
