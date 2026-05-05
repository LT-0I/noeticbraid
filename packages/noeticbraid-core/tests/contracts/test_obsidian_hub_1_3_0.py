"""Contract 1.3.0 Obsidian hub schema and model invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_DIR = REPO_ROOT / "docs" / "contracts"
HUB_DIR = CONTRACT_DIR / "obsidian-hub-1.3.0"
FROZEN_OPENAPI = CONTRACT_DIR / "phase1_2_openapi.yaml"


def _load_hub_schema(name: str) -> dict[str, object]:
    return json.loads((HUB_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def _property(schema: dict[str, object], field_name: str) -> dict[str, object]:
    return schema["properties"][field_name]


def _json_enum(schema: dict[str, object], field_name: str) -> set[str]:
    prop = _property(schema, field_name)
    if "enum" in prop:
        return set(prop["enum"])
    for option in prop.get("anyOf", []):
        if option.get("type") == "string" and "enum" in option:
            return set(option["enum"])
    raise AssertionError(f"{field_name} has no enum")


def _frozen_schema_section(schema_name: str) -> str:
    text = FROZEN_OPENAPI.read_text(encoding="utf-8")
    marker = f"    {schema_name}:\n"
    start = text.index(marker)
    match = re.search(r"^    [A-Za-z][A-Za-z0-9_]*:\n", text[start + len(marker) :], re.M)
    end = start + len(marker) + match.start() if match else len(text)
    return text[start:end]


def _frozen_property_section(schema_name: str, field_name: str) -> str:
    section = _frozen_schema_section(schema_name)
    marker = f"        {field_name}:\n"
    start = section.index(marker)
    match = re.search(
        r"^        [A-Za-z_][A-Za-z0-9_]*:\n",
        section[start + len(marker) :],
        re.M,
    )
    end = start + len(marker) + match.start() if match else len(section)
    return section[start:end]


def _frozen_enum(schema_name: str, field_name: str) -> set[str]:
    section = _frozen_property_section(schema_name, field_name)
    return set(re.findall(r"^          - ([^\n]+)$", section, re.M))


def _assert_schema_valid(schema: dict[str, object]) -> None:
    Draft7Validator.check_schema(schema)
    assert schema["additionalProperties"] is False


def _assert_model_fields(model: type[object], schema: dict[str, object]) -> None:
    assert set(model.model_fields) == set(schema["properties"])


def test_dashboard_schema_valid() -> None:
    from noeticbraid_core.schemas.obsidian_hub import Dashboard

    schema = _load_hub_schema("dashboard")
    _assert_schema_valid(schema)
    _assert_model_fields(Dashboard, schema)
    instance = Dashboard.model_validate(
        {
            "nb_type": "dashboard",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "dashboard_id": "dashboard_main",
            "title": "NoeticBraid overview",
            "date": "2026-05-05",
            "generated": True,
            "generated_at": "2026-05-05T12:00:00Z",
            "tags": ["noeticbraid/dashboard"],
            "source_run_id": None,
        }
    )
    assert instance.dashboard_id == "dashboard_main"


def test_task_note_field_mapping_to_frozen_task() -> None:
    from noeticbraid_core.schemas.obsidian_hub import TaskNote

    schema = _load_hub_schema("task_note")
    _assert_schema_valid(schema)
    _assert_model_fields(TaskNote, schema)
    assert _json_enum(schema, "task_type") == _frozen_enum("Task", "task_type")
    assert len(_json_enum(schema, "task_type")) == 3
    assert _json_enum(schema, "source_channel") == _frozen_enum("Task", "source_channel")
    assert len(_json_enum(schema, "source_channel")) == 5
    assert _json_enum(schema, "status") == _frozen_enum("Task", "status")
    assert len(_json_enum(schema, "status")) == 7
    assert _json_enum(schema, "approval_level") == _frozen_enum("Task", "approval_level")
    assert len(_json_enum(schema, "approval_level")) == 4
    assert TaskNote.model_validate(
        {
            "nb_type": "task",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "task_id": "task_obsidian_001",
            "task_type": "research",
            "risk_level": "low",
            "approval_level": "light",
            "status": "ready",
            "source_channel": "obsidian",
            "created_at": "2026-05-05T12:00:00Z",
            "tags": ["noeticbraid/task"],
            "account_hint": None,
            "project_ref": "project_alpha",
        }
    )


def test_run_record_note_event_type_subset_9_in_frozen_14() -> None:
    from noeticbraid_core.schemas.obsidian_hub import RunRecordNote

    schema = _load_hub_schema("run_record_note")
    _assert_schema_valid(schema)
    _assert_model_fields(RunRecordNote, schema)
    vault_values = _json_enum(schema, "event_type")
    frozen_values = _frozen_enum("RunRecord", "event_type")
    assert len(vault_values) == 9
    assert len(frozen_values) == 14
    assert vault_values < frozen_values
    assert RunRecordNote.model_validate(
        {
            "nb_type": "run_record",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "run_id": "run_obsidian_001",
            "task_id": "task_obsidian_001",
            "event_type": "lesson_candidate_created",
            "actor": "model",
            "status": "recorded",
            "created_at": "2026-05-05T12:00:00Z",
            "tags": ["noeticbraid/run"],
            "model_refs": ["model_gpt"],
            "source_refs": ["source_doc"],
            "artifact_refs": ["artifact_note"],
        }
    )


def test_source_record_note_source_type_subset_5_in_frozen_8() -> None:
    from noeticbraid_core.schemas.obsidian_hub import SourceRecordNote

    schema = _load_hub_schema("source_record_note")
    _assert_schema_valid(schema)
    _assert_model_fields(SourceRecordNote, schema)
    vault_values = _json_enum(schema, "source_type")
    assert vault_values == {"user_note", "web_page", "github_repo", "paper", "ai_output"}
    frozen_values = _frozen_enum("SourceRecord", "source_type")
    assert len(vault_values) == 5
    assert len(frozen_values) == 8
    assert vault_values < frozen_values
    assert SourceRecordNote.model_validate(
        {
            "nb_type": "source_record",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "source_ref_id": "source_obsidian_001",
            "source_type": "web_page",
            "title": "Source title",
            "captured_at": "2026-05-05T12:00:00Z",
            "quality_score": "high",
            "relevance_score": "medium",
            "tags": ["noeticbraid/source"],
            "canonical_url": "https://example.com/source",
            "local_path": None,
            "source_ref": "vault/source",
            "external_url": None,
            "author": None,
            "retrieved_by_run_id": "run_obsidian_001",
            "content_hash": "sha256:" + "a" * 64,
            "source_fingerprint": "fingerprint_obsidian_001",
            "evidence_role": None,
            "used_for_purpose": None,
        }
    )


def test_source_record_note_evidence_role_anyOf_null() -> None:
    schema = _load_hub_schema("source_record_note")
    for field_name, frozen_schema in (
        ("evidence_role", "SourceRecord"),
        ("used_for_purpose", "SourceRecord"),
    ):
        prop = _property(schema, field_name)
        assert "type" not in prop
        assert "enum" not in prop
        any_of = prop["anyOf"]
        string_options = [item for item in any_of if item.get("type") == "string"]
        null_options = [item for item in any_of if item.get("type") == "null"]
        assert len(string_options) == 1
        assert len(null_options) == 1
        assert set(string_options[0]["enum"]) == _frozen_enum(frozen_schema, field_name)


def test_side_note_user_response_5_includes_snoozed_vault_only() -> None:
    from noeticbraid_core.schemas.obsidian_hub import SideNoteNote

    schema = _load_hub_schema("side_note")
    _assert_schema_valid(schema)
    _assert_model_fields(SideNoteNote, schema)
    vault_values = _json_enum(schema, "user_response")
    frozen_values = _frozen_enum("SideNote", "user_response")
    assert vault_values == frozen_values | {"snoozed"}
    description = _property(schema, "user_response")["description"]
    assert "snoozed is a vault-only extension" in description
    assert "must not be sent" in description
    assert SideNoteNote.model_validate(
        {
            "nb_type": "side_note",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "note_id": "note_obsidian_001",
            "created_at": "2026-05-05T12:00:00Z",
            "linked_source_refs": ["source_obsidian_001"],
            "note_type": "challenge",
            "confidence": "medium",
            "user_response": "snoozed",
            "tags": ["noeticbraid/side-note"],
            "follow_up_ref": "digestion_obsidian_001",
            "project_ref": None,
        }
    )


def test_digestion_item_c_status_6_aligned_frozen() -> None:
    from noeticbraid_core.schemas.obsidian_hub import DigestionItemNote

    schema = _load_hub_schema("digestion_item")
    _assert_schema_valid(schema)
    _assert_model_fields(DigestionItemNote, schema)
    assert _json_enum(schema, "c_status") == _frozen_enum("DigestionItem", "c_status")
    assert len(_json_enum(schema, "c_status")) == 6
    assert DigestionItemNote.model_validate(
        {
            "nb_type": "digestion_item",
            "schema_version": "obsidian-hub-0.1",
            "contract_version": "1.3.0",
            "digestion_id": "digestion_obsidian_001",
            "side_note_id": "note_obsidian_001",
            "created_at": "2026-05-05T12:00:00Z",
            "c_status": "c3",
            "status": "open",
            "tags": ["noeticbraid/digestion"],
            "user_response_ref": None,
            "next_review_at": None,
        }
    )


def test_write_policy_no_contract_version_field() -> None:
    from noeticbraid_core.schemas.obsidian_hub import WritePolicy

    schema = _load_hub_schema("write_policy")
    _assert_schema_valid(schema)
    _assert_model_fields(WritePolicy, schema)
    assert "contract_version" not in schema["properties"]
    assert "nb_type" not in schema["properties"]
    assert "contract_version" not in schema["required"]
    assert "nb_type" not in schema["required"]
    policy = WritePolicy.model_validate(
        {
            "schema_version": "obsidian-hub-settings-0.1",
            "vault_root_env": "OBSIDIAN_HUB_VAULT_ROOT",
            "namespace": "NoeticBraid",
            "allowlist_relative_roots": ["NoeticBraid/generated/"],
            "denylist_relative_globs": ["NoeticBraid/private/**"],
            "default_write_mode": "dry_run",
            "generated_overwrite_allowed": True,
            "non_generated_overwrite_allowed": False,
            "stable_record_write_mode": "create_only",
            "atomic_write_intent": True,
            "user_dropzone_read_relative_root": "NoeticBraid/inbox/",
            "append_only_heading_policy": "status_and_decision_notes_only",
            "sync_log_relative_path": "NoeticBraid/logs/sync.jsonl",
            "generated_surface_requires_frontmatter": True,
            "optional_integrations": {"obsidian": "local"},
        }
    )
    assert policy.default_write_mode == "dry_run"
    with pytest.raises(ValidationError):
        WritePolicy.model_validate(
            {
                **policy.model_dump(),
                "sync_log_relative_path": "../private/token.txt",
            }
        )
