# SPDX-License-Identifier: Apache-2.0
"""FastAPI application factory for the NoeticBraid backend."""

from __future__ import annotations

import importlib
import logging
from copy import deepcopy
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from noeticbraid_backend.api.routes import account, approval, auth, dashboard, health, ledger, workspace
from noeticbraid_backend.contracts import (
    CONTRACT_AUTHORITATIVE,
    CONTRACT_VERSION,
    CORE_SCHEMA_MODELS,
    OPENAPI_TITLE,
)
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
    schema.setdefault("info", {})["x-contract-version"] = CONTRACT_VERSION
    schema["info"]["x-status"] = "AUTHORITATIVE"
    schema["info"]["x-frozen"] = CONTRACT_AUTHORITATIVE

    component_schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    for model in CORE_SCHEMA_MODELS:
        component_schemas[model.__name__] = _inline_component_defs(
            model.model_json_schema(ref_template="#/components/schemas/{model}")
        )
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)
    component_schemas.pop("HTTPValidationError", None)
    component_schemas.pop("ValidationError", None)
    component_schemas.pop("AggregateArtifact", None)
    component_schemas.pop("AggregateError", None)
    component_schemas.pop("AggregateLesson", None)

    app.openapi_schema = schema
    return app.openapi_schema


def _inline_component_defs(component_schema: dict[str, Any]) -> dict[str, Any]:
    """Inline Pydantic sub-model definitions to keep contract components stable."""

    defs = component_schema.pop("$defs", {})
    if not defs:
        return component_schema

    def visit(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name in defs:
                    return visit(deepcopy(defs[name]))
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    return visit(component_schema)


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
    """Create and configure the Phase 1.2 Stage 2.2 FastAPI application."""

    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _validate_core_imports(app)
        yield

    app = FastAPI(
        title=OPENAPI_TITLE,
        version=CONTRACT_VERSION,
        openapi_version="3.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    # CORS does not expose X-NoeticBraid-Bearer to browsers in stage-2.2.
    # Browser integration with the auth header belongs to the stage-2.3 Console
    # real-backend swap; add expose_headers=[auth.BEARER_TOKEN_RESPONSE_HEADER]
    # there if the browser client needs to read the startup bearer response.
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
