# SPDX-License-Identifier: Apache-2.0
"""Module-local validator for SP-D Obsidian vault hub resources."""

from __future__ import annotations

import json
import re
from typing import Any

from .frontmatter import extract_frontmatter
from .path_policy import ModeEnforcer
from .resources import CONTRACT_VERSION, load_json_resource, load_schema, resource_root
from .settings import default_settings

SCHEMA_NAMES = [
    "dashboard",
    "digestion_item",
    "run_record_note",
    "side_note",
    "source_record_note",
    "task_note",
    "write_policy",
]


def validate_schemas() -> None:
    for name in SCHEMA_NAMES:
        schema = load_schema(name)
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            raise AssertionError(f"schema {name} must be a strict object")
        if name == "write_policy":
            if "contract_version" in schema.get("properties", {}):
                raise AssertionError("write_policy must not expose contract_version")
        elif schema["properties"]["contract_version"].get("const") != CONTRACT_VERSION:
            raise AssertionError(f"schema {name} must use contract {CONTRACT_VERSION}")


def validate_path_policy_cases() -> None:
    settings = default_settings()
    enforcer = ModeEnforcer(settings)
    cases = load_json_resource("fixtures/path_policy_cases.json")
    if not isinstance(cases, list) or not cases:
        raise AssertionError("path policy fixture must be a non-empty list")
    for case in cases:
        actual = enforcer.is_allowed_write_path(case["target_path"])
        if actual is not case["expected_allowed"]:
            raise AssertionError(f"path case {case['case_id']} expected {case['expected_allowed']}, got {actual}")


def validate_settings_resource() -> None:
    settings = default_settings()
    if settings.default_write_mode != "dry_run":
        raise AssertionError("default settings must be dry_run")
    if settings.namespace != "NoeticBraid":
        raise AssertionError("default namespace must be NoeticBraid")


def validate_resource_presence() -> None:
    root = resource_root()
    for name in SCHEMA_NAMES:
        if not (root / "schemas" / f"{name}.schema.json").is_file():
            raise AssertionError(f"missing schema {name}")
    for relative in [
        "config/obsidian_hub.settings.example.json",
        "fixtures/path_policy_cases.json",
        "templates/dashboard_today.md",
        "templates/task.md",
    ]:
        if not (root / relative).is_file():
            raise AssertionError(f"missing resource {relative}")


def validate_templates() -> None:
    root = resource_root() / "templates"
    for path in root.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for anchor in ["nb_type:", "schema_version:", "contract_version:", "tags:"]:
            if anchor not in text:
                raise AssertionError(f"template {path.name} missing {anchor}")
        if 'contract_version: "1.3.0"' not in text:
            raise AssertionError(f"template {path.name} must use contract_version 1.3.0")


def validate_template_instances() -> set[str]:
    checked: set[str] = set()
    schema_by_type = {
        "dashboard": "dashboard",
        "task": "task_note",
        "run_record": "run_record_note",
        "source_record": "source_record_note",
        "side_note": "side_note",
        "digestion_item": "digestion_item",
    }
    for path in (resource_root() / "templates").glob("*.md"):
        frontmatter, _body = extract_frontmatter(path.read_text(encoding="utf-8"))
        nb_type = frontmatter.get("nb_type")
        if nb_type not in schema_by_type:
            continue
        schema_name = schema_by_type[str(nb_type)]
        schema = load_schema(schema_name)
        instance = _sample_template_instance(frontmatter, schema)
        errors = _validate_instance(schema, instance, schema_name=schema_name)
        if errors:
            raise AssertionError(f"template {path.name} invalid: {errors}")
        checked.add(path.name)
    return checked


def _sample_template_instance(frontmatter: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema["properties"]
    return {key: _sample_value(key, value, properties.get(key, {})) for key, value in frontmatter.items()}


def _sample_value(field_name: str, value: Any, prop: dict[str, Any]) -> Any:
    if value == [] and _allows_type(prop, "null") and not _allows_type(prop, "array"):
        return None
    if isinstance(value, list):
        return [_sample_value(field_name, item, prop.get("items", {})) for item in value]
    if isinstance(value, str) and "{{" in value and "}}" in value:
        return _sample_for_field(field_name)
    return value


def _sample_for_field(field_name: str) -> str:
    samples = {
        "dashboard_id": "dashboard_today",
        "date": "2026-05-06",
        "generated_at": "2026-05-06T12:00:00Z",
        "source_run_id": "run_obsidian_001",
        "task_id": "task_obsidian_001",
        "run_id": "run_obsidian_001",
        "note_id": "note_obsidian_001",
        "side_note_id": "note_obsidian_001",
        "digestion_id": "digestion_obsidian_001",
        "source_ref_id": "source_obsidian_001",
        "linked_source_refs": "source_obsidian_001",
        "source_ref": "source_obsidian_001",
        "model_refs": "model_obsidian_001",
        "source_refs": "source_obsidian_001",
        "artifact_refs": "artifact_obsidian_001",
        "model_ref": "model_obsidian_001",
        "artifact_ref": "artifact_obsidian_001",
        "follow_up_ref": "digestion_obsidian_001",
        "project_ref": "project_alpha",
        "created_at": "2026-05-06T12:00:00Z",
        "captured_at": "2026-05-06T12:00:00Z",
        "retrieved_by_run_id": "run_obsidian_001",
        "title": "Example source",
        "author": "Example author",
        "source_fingerprint": "fingerprint_obsidian_001",
        "next_review_at": "2026-05-07T12:00:00Z",
        "account_hint": "gpt-main",
    }
    return samples.get(field_name, "sample")


def _validate_instance(schema: dict[str, Any], instance: dict[str, Any], *, schema_name: str) -> list[str]:
    errors: list[str] = []
    required = schema.get("required", [])
    for field_name in required:
        if field_name not in instance:
            errors.append(f"{schema_name}.{field_name}: missing required")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for field_name in instance:
            if field_name not in properties:
                errors.append(f"{schema_name}.{field_name}: additional property")
    for field_name, value in instance.items():
        prop = properties.get(field_name)
        if prop is not None:
            errors.extend(_validate_value(prop, value, f"{schema_name}.{field_name}"))
    return errors


def _validate_value(prop: dict[str, Any], value: Any, label: str) -> list[str]:
    if "anyOf" in prop:
        candidates = [_validate_value(option, value, label) for option in prop["anyOf"]]
        return [] if any(not candidate for candidate in candidates) else candidates[0]
    errors: list[str] = []
    if "const" in prop and value != prop["const"]:
        errors.append(f"{label}: expected const {prop['const']!r}")
    if "enum" in prop and value not in prop["enum"]:
        errors.append(f"{label}: expected enum {prop['enum']!r}")
    expected_type = prop.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        errors.append(f"{label}: expected type {expected_type!r}")
        return errors
    if isinstance(value, str) and "pattern" in prop and re.search(prop["pattern"], value) is None:
        errors.append(f"{label}: pattern mismatch {prop['pattern']!r}")
    if isinstance(value, list):
        item_schema = prop.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_validate_value(item_schema, item, f"{label}[{index}]"))
    return errors


def _matches_type(value: Any, expected_type: str | list[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    return {
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "null": value is None,
    }.get(expected_type, True)


def _allows_type(prop: dict[str, Any], expected_type: str) -> bool:
    prop_type = prop.get("type")
    return prop_type == expected_type or (isinstance(prop_type, list) and expected_type in prop_type)


def run_validation() -> list[str]:
    validate_resource_presence()
    validate_settings_resource()
    validate_path_policy_cases()
    validate_schemas()
    validate_templates()
    validate_template_instances()
    return [
        "resource-presence",
        "settings-boundary",
        "path-policy-cases",
        "schemas",
        "templates",
        "template-instances",
    ]


def main() -> int:
    try:
        checks = run_validation()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS: obsidian hub checks: " + ", ".join(checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
