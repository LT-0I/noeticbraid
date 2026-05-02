#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Phase 1.2 OpenAPI 1.1.0 contract sidecar and runtime drift gate.

This gate intentionally avoids a YAML dependency. It mechanically reads the
frozen OpenAPI bytes and SHA-256 sidecar, checks exact anchor text for the frozen
file, and compares runtime FastAPI OpenAPI anchors produced by create_app().
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "docs" / "contracts" / "phase1_2_openapi.yaml"
SIDECAR_PATH = REPO_ROOT / "docs" / "contracts" / "phase1_2_openapi.yaml.sha256"

EXPECTED_INFO = {
    "openapi": "3.1.0",
    "title": "NoeticBraid Phase 1.2 API",
    "version": "1.1.0",
    "x-contract-version": "1.1.0",
    "x-status": "AUTHORITATIVE",
    "x-frozen": True,
}

EXPECTED_ROUTES: tuple[dict[str, object], ...] = (
    {
        "path": "/api/health",
        "method": "get",
        "tag": "health",
        "summary": "Health check",
        "operation_id": "health_api_health_get",
        "response_schema": "HealthResponse",
    },
    {
        "path": "/api/auth/startup_token",
        "method": "post",
        "tag": "auth",
        "summary": "Validate startup token",
        "operation_id": "startup_token_api_auth_startup_token_post",
        "response_schema": "AuthResponse",
    },
    {
        "path": "/api/dashboard/empty",
        "method": "get",
        "tag": "dashboard",
        "summary": "Empty dashboard state",
        "operation_id": "dashboard_empty_api_dashboard_empty_get",
        "response_schema": "EmptyDashboard",
    },
    {
        "path": "/api/workspace/threads",
        "method": "get",
        "tag": "workspace",
        "summary": "List workspace threads",
        "operation_id": "workspace_threads_api_workspace_threads_get",
        "response_schema": "WorkspaceThreads",
    },
    {
        "path": "/api/approval/queue",
        "method": "get",
        "tag": "approval",
        "summary": "List approval queue",
        "operation_id": "approval_queue_api_approval_queue_get",
        "response_schema": "ApprovalQueue",
    },
    {
        "path": "/api/account/pool",
        "method": "get",
        "tag": "account",
        "summary": "Account pool draft state",
        "operation_id": "account_pool_api_account_pool_get",
        "response_schema": "AccountPoolDraft",
    },
    {
        "path": "/api/ledger/runs",
        "method": "get",
        "tag": "ledger",
        "summary": "List run records",
        "operation_id": "ledger_runs_api_ledger_runs_get",
        "response_schema": "RunLedgerRuns",
    },
)

EXPECTED_SCHEMA_NAMES: tuple[str, ...] = (
    "HealthResponse",
    "AuthResponse",
    "EmptyDashboard",
    "WorkspaceThreads",
    "ApprovalQueue",
    "AccountPoolDraft",
    "RunLedgerRuns",
    "Task",
    "RunRecord",
    "SourceRecord",
    "ApprovalRequest",
    "SideNote",
    "DigestionItem",
)

EXPECTED_WRAPPER_FIELDS: dict[str, tuple[str, ...]] = {
    "HealthResponse": ("status", "contract_version", "authoritative"),
    "AuthResponse": ("accepted", "mode"),
    "EmptyDashboard": ("tasks", "approvals", "accounts"),
    "WorkspaceThreads": ("threads",),
    "ApprovalQueue": ("approvals",),
    "AccountPoolDraft": ("profiles",),
    "RunLedgerRuns": ("runs",),
}

EXPECTED_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "HealthResponse": ("status", "contract_version", "authoritative"),
    "AuthResponse": ("accepted", "mode"),
}

SIDECAR_RE = re.compile(r"^(?P<sha>[0-9A-Fa-f]{64}) \*(?P<name>phase1_2_openapi\.yaml)$")
PATH_RE = re.compile(r"^  (/api/[^:]+):$", re.MULTILINE)
SCHEMA_RE = re.compile(r"^    ([A-Za-z][A-Za-z0-9_]*):$", re.MULTILINE)
PROPERTY_RE = re.compile(r"^        ([A-Za-z_][A-Za-z0-9_]*):$")


@dataclass(frozen=True)
class ContractGateReport:
    """Structured PASS evidence returned by run_checks()."""

    contract_sha256: str
    sidecar_sha256: str
    frozen_paths: tuple[str, ...]
    runtime_paths: tuple[str, ...]
    runtime_schema_names: tuple[str, ...]


def _fail(message: str) -> None:
    raise AssertionError(message)


def _repo_root(repo_root: Path | None = None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else REPO_ROOT


def _contract_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "contracts" / "phase1_2_openapi.yaml"


def _sidecar_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "contracts" / "phase1_2_openapi.yaml.sha256"


def parse_sidecar(sidecar_bytes: bytes) -> tuple[str, str]:
    """Parse `<SHA256> *phase1_2_openapi.yaml` from ASCII sidecar bytes."""

    text = sidecar_bytes.decode("ascii").strip()
    match = SIDECAR_RE.fullmatch(text)
    if match is None:
        _fail("phase1_2_openapi.yaml.sha256 must be '<64 hex> *phase1_2_openapi.yaml'")
    return match.group("sha").lower(), match.group("name")


def verify_sidecar_bytes(repo_root: Path | None = None) -> tuple[str, str]:
    """Read frozen contract bytes and sidecar bytes and compare SHA-256."""

    root = _repo_root(repo_root)
    contract_bytes = _contract_path(root).read_bytes()
    sidecar_sha, sidecar_name = parse_sidecar(_sidecar_path(root).read_bytes())
    actual_sha = hashlib.sha256(contract_bytes).hexdigest()
    if sidecar_name != "phase1_2_openapi.yaml":
        _fail(f"unexpected sidecar file target: {sidecar_name}")
    if actual_sha != sidecar_sha:
        _fail(f"contract sidecar mismatch: actual {actual_sha}, sidecar {sidecar_sha}")
    return actual_sha, sidecar_sha


def _ensure_import_paths(repo_root: Path) -> None:
    for path in (
        repo_root / "packages" / "noeticbraid-core" / "src",
        repo_root / "packages" / "noeticbraid-backend" / "src",
    ):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _extract_path_section(contract_text: str, path: str) -> str:
    marker = f"  {path}:\n"
    start = contract_text.find(marker)
    if start < 0:
        _fail(f"missing frozen path section: {path}")
    next_path = contract_text.find("\n  /api/", start + len(marker))
    components = contract_text.find("\ncomponents:", start + len(marker))
    candidates = [idx for idx in (next_path, components) if idx != -1]
    end = min(candidates) if candidates else len(contract_text)
    return contract_text[start:end]


def _schema_block(contract_text: str) -> str:
    marker = "  schemas:\n"
    start = contract_text.find(marker)
    if start < 0:
        _fail("missing frozen components.schemas section")
    return contract_text[start + len(marker) :]


def _extract_schema_section(contract_text: str, schema_name: str) -> str:
    block = _schema_block(contract_text)
    marker = f"    {schema_name}:\n"
    start = block.find(marker)
    if start < 0:
        _fail(f"missing frozen schema section: {schema_name}")
    next_match = SCHEMA_RE.search(block, start + len(marker))
    end = next_match.start() if next_match is not None else len(block)
    return block[start:end]


def _schema_property_names_from_yaml(contract_text: str, schema_name: str) -> tuple[str, ...]:
    section = _extract_schema_section(contract_text, schema_name)
    lines = section.splitlines()
    try:
        properties_index = lines.index("      properties:")
    except ValueError:
        return ()
    names: list[str] = []
    for line in lines[properties_index + 1 :]:
        if line.startswith("      ") and not line.startswith("        "):
            break
        match = PROPERTY_RE.match(line)
        if match is not None:
            names.append(match.group(1))
    return tuple(names)


def _schema_required_names_from_yaml(contract_text: str, schema_name: str) -> tuple[str, ...]:
    section = _extract_schema_section(contract_text, schema_name)
    lines = section.splitlines()
    required: list[str] = []
    for index, line in enumerate(lines):
        if line == "      required:":
            for candidate in lines[index + 1 :]:
                if candidate.startswith("      - "):
                    required.append(candidate.removeprefix("      - ").strip())
                    continue
                break
            return tuple(required)
    return ()


def _assert_no_public_security_metadata_in_frozen(contract_text: str) -> None:
    if "securitySchemes" in contract_text:
        _fail("frozen OpenAPI exposes securitySchemes")
    if re.search(r"^\s+security:\s*$", contract_text, re.MULTILINE):
        _fail("frozen OpenAPI exposes route-level security")
    if re.search(r"\bAuthorization\b", contract_text):
        _fail("frozen OpenAPI exposes Authorization")


def _assert_no_public_security_metadata_in_runtime(schema: dict[str, Any]) -> None:
    if "securitySchemes" in schema.get("components", {}):
        _fail("runtime OpenAPI exposes securitySchemes")
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            if "security" in operation:
                _fail(f"runtime OpenAPI exposes route-level security for {method.upper()} {path}")
            parameters = operation.get("parameters", [])
            for parameter in parameters:
                if parameter.get("name") == "Authorization":
                    _fail(f"runtime OpenAPI exposes Authorization parameter for {method.upper()} {path}")


def _assert_frozen_contract(contract_text: str) -> tuple[str, ...]:
    expected_paths = tuple(str(route["path"]) for route in EXPECTED_ROUTES)
    actual_paths = tuple(PATH_RE.findall(contract_text))
    if actual_paths != expected_paths:
        _fail(f"frozen path order/set mismatch: actual={actual_paths!r}, expected={expected_paths!r}")

    for anchor in (
        "openapi: 3.1.0",
        "  title: NoeticBraid Phase 1.2 API",
        "  version: 1.1.0",
        "  x-contract-version: 1.1.0",
        "  x-status: AUTHORITATIVE",
        "  x-frozen: true",
    ):
        if anchor not in contract_text:
            _fail(f"missing frozen metadata anchor: {anchor}")

    for route in EXPECTED_ROUTES:
        path = str(route["path"])
        method = str(route["method"])
        tag = str(route["tag"])
        summary = str(route["summary"])
        operation_id = str(route["operation_id"])
        response_schema = str(route["response_schema"])
        section = _extract_path_section(contract_text, path)
        for anchor in (
            f"    {method}:",
            f"      - {tag}",
            f"      summary: {summary}",
            f"      operationId: {operation_id}",
            f"                $ref: '#/components/schemas/{response_schema}'",
        ):
            if anchor not in section:
                _fail(f"missing frozen anchor for {method.upper()} {path}: {anchor}")
        if path == "/api/auth/startup_token" and "requestBody" in section:
            _fail("POST /api/auth/startup_token must not define requestBody")
        if re.search(r"^\s+security:\s*$", section, re.MULTILINE):
            _fail(f"frozen route section exposes security for {method.upper()} {path}")
        if re.search(r"\bAuthorization\b", section):
            _fail(f"frozen route section exposes Authorization for {method.upper()} {path}")

    _assert_no_public_security_metadata_in_frozen(contract_text)

    actual_schema_names = tuple(SCHEMA_RE.findall(_schema_block(contract_text)))
    missing = set(EXPECTED_SCHEMA_NAMES) - set(actual_schema_names)
    extra = set(actual_schema_names) - set(EXPECTED_SCHEMA_NAMES)
    if missing or extra:
        _fail(f"frozen schema-name set mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

    for schema_name, expected_fields in EXPECTED_WRAPPER_FIELDS.items():
        actual_fields = _schema_property_names_from_yaml(contract_text, schema_name)
        if actual_fields != expected_fields:
            _fail(f"frozen {schema_name} field order mismatch: actual={actual_fields}, expected={expected_fields}")
    for schema_name, expected_required in EXPECTED_REQUIRED_FIELDS.items():
        actual_required = _schema_required_names_from_yaml(contract_text, schema_name)
        if actual_required != expected_required:
            _fail(f"frozen {schema_name} required order mismatch: actual={actual_required}, expected={expected_required}")
    return actual_paths


def _runtime_schema(repo_root: Path) -> dict[str, Any]:
    _ensure_import_paths(repo_root)
    from noeticbraid_backend.app import create_app
    from noeticbraid_backend.settings import Settings

    app = create_app(Settings(state_dir=repo_root / ".stage2_4_contract_gate_state", dpapi_blob_path=None))
    return app.openapi()


def _assert_runtime_contract(schema: dict[str, Any], repo_root: Path) -> tuple[str, ...]:
    from noeticbraid_backend.contracts import ALL_SCHEMA_NAMES, CONTRACT_AUTHORITATIVE, CONTRACT_VERSION, OPENAPI_TITLE

    if schema.get("openapi") != EXPECTED_INFO["openapi"]:
        _fail(f"runtime openapi mismatch: {schema.get('openapi')!r}")
    info = schema.get("info", {})
    expected_info = {
        "title": OPENAPI_TITLE,
        "version": CONTRACT_VERSION,
        "x-contract-version": CONTRACT_VERSION,
        "x-status": EXPECTED_INFO["x-status"],
        "x-frozen": CONTRACT_AUTHORITATIVE,
    }
    for key, expected in expected_info.items():
        if info.get(key) != expected:
            _fail(f"runtime info.{key} mismatch: actual={info.get(key)!r}, expected={expected!r}")

    expected_paths = tuple(str(route["path"]) for route in EXPECTED_ROUTES)
    runtime_paths = tuple(schema.get("paths", {}).keys())
    if runtime_paths != expected_paths:
        _fail(f"runtime path order/set mismatch: actual={runtime_paths!r}, expected={expected_paths!r}")

    for route in EXPECTED_ROUTES:
        path = str(route["path"])
        method = str(route["method"])
        operation = schema["paths"][path][method]
        expected_tag = str(route["tag"])
        expected_summary = str(route["summary"])
        expected_operation_id = str(route["operation_id"])
        expected_response_schema = str(route["response_schema"])
        if operation.get("tags") != [expected_tag]:
            _fail(f"runtime tags mismatch for {method.upper()} {path}: {operation.get('tags')!r}")
        if operation.get("summary") != expected_summary:
            _fail(f"runtime summary mismatch for {method.upper()} {path}: {operation.get('summary')!r}")
        if operation.get("operationId") != expected_operation_id:
            _fail(f"runtime operationId mismatch for {method.upper()} {path}: {operation.get('operationId')!r}")
        response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"].get("$ref")
        if response_ref != f"#/components/schemas/{expected_response_schema}":
            _fail(f"runtime response ref mismatch for {method.upper()} {path}: {response_ref!r}")
        if path == "/api/auth/startup_token" and "requestBody" in operation:
            _fail("runtime POST /api/auth/startup_token must not define requestBody")

    _assert_no_public_security_metadata_in_runtime(schema)

    if tuple(ALL_SCHEMA_NAMES) != EXPECTED_SCHEMA_NAMES:
        _fail(f"contract helper schema-name order mismatch: {tuple(ALL_SCHEMA_NAMES)!r}")
    components = schema.get("components", {}).get("schemas", {})
    runtime_schema_names = tuple(components.keys())
    if set(runtime_schema_names) != set(EXPECTED_SCHEMA_NAMES):
        missing = set(EXPECTED_SCHEMA_NAMES) - set(runtime_schema_names)
        extra = set(runtime_schema_names) - set(EXPECTED_SCHEMA_NAMES)
        _fail(f"runtime schema-name set mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

    for schema_name, expected_fields in EXPECTED_WRAPPER_FIELDS.items():
        properties = components[schema_name].get("properties", {})
        actual_fields = tuple(properties.keys())
        if actual_fields != expected_fields:
            _fail(f"runtime {schema_name} field order mismatch: actual={actual_fields}, expected={expected_fields}")
    for schema_name, expected_required in EXPECTED_REQUIRED_FIELDS.items():
        actual_required = tuple(components[schema_name].get("required", ()))
        if actual_required != expected_required:
            _fail(f"runtime {schema_name} required order mismatch: actual={actual_required}, expected={expected_required}")
    return runtime_paths


def run_checks(repo_root: Path | None = None) -> ContractGateReport:
    """Run all Phase 1.2 Stage 2.4 contract checks and return PASS evidence."""

    root = _repo_root(repo_root)
    actual_sha, sidecar_sha = verify_sidecar_bytes(root)
    contract_text = _contract_path(root).read_bytes().decode("utf-8")
    frozen_paths = _assert_frozen_contract(contract_text)
    runtime = _runtime_schema(root)
    runtime_paths = _assert_runtime_contract(runtime, root)
    runtime_schema_names = tuple(runtime["components"]["schemas"].keys())
    return ContractGateReport(
        contract_sha256=actual_sha,
        sidecar_sha256=sidecar_sha,
        frozen_paths=frozen_paths,
        runtime_paths=runtime_paths,
        runtime_schema_names=runtime_schema_names,
    )


def main() -> int:
    try:
        report = run_checks()
    except Exception as exc:
        print("phase1_2_contract_gate: FAIL")
        print(f"  - {type(exc).__name__}: {exc}")
        return 1
    print("phase1_2_contract_gate: PASS")
    print(f"  sidecar_sha256={report.sidecar_sha256}")
    print(f"  paths={len(report.runtime_paths)}")
    print(f"  schemas={len(report.runtime_schema_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
