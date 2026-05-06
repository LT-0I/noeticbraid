from __future__ import annotations

import json
from pathlib import Path

from noeticbraid_obsidian import validate_obsidian_hub
from noeticbraid_obsidian.resources import CONTRACT_VERSION, load_schema, resource_root


def test_embedded_schemas_are_contract_1_3_0_and_write_policy_has_no_contract_version() -> None:
    schema_names = [
        "dashboard",
        "task_note",
        "run_record_note",
        "source_record_note",
        "side_note",
        "digestion_item",
        "write_policy",
    ]
    schemas = {name: load_schema(name) for name in schema_names}

    assert CONTRACT_VERSION == "1.3.0"
    for name, schema in schemas.items():
        assert schema["additionalProperties"] is False, name
        if name == "write_policy":
            assert "contract_version" not in schema["properties"]
            assert "contract_version" not in schema["required"]
        else:
            assert schema["properties"]["contract_version"]["const"] == "1.3.0"


def test_path_policy_fixture_and_validator_pass() -> None:
    root = resource_root()
    cases = json.loads((root / "fixtures" / "path_policy_cases.json").read_text(encoding="utf-8"))

    assert {case["case_id"] for case in cases} >= {
        "allowed_generated_dashboard",
        "allowed_run_record_create_only",
        "denied_user_raw",
        "denied_parent_traversal_inside",
    }
    checks = validate_obsidian_hub.run_validation()
    assert "schemas" in checks
    assert "path-policy-cases" in checks
    assert "template-instances" in checks


def test_validator_template_instances() -> None:
    checked = validate_obsidian_hub.validate_template_instances()

    assert checked >= {
        "dashboard_today.md",
        "task.md",
        "run_record.md",
        "source_record.md",
        "side_note.md",
        "digestion_item.md",
    }


def test_readme_documents_reference_projects() -> None:
    package_root = Path(__file__).resolve().parent.parent
    text = (package_root / "README.md").read_text(encoding="utf-8")

    assert "obsidian-local-rest-api" in text
    assert "TaskNotes" in text
    assert "Dataview" in text
