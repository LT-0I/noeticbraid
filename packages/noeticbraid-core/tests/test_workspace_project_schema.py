from __future__ import annotations

from noeticbraid_core.schemas import WorkspaceProject


def test_omc_workspace_project_minimum_fields(load_schema_fixture) -> None:
    project = WorkspaceProject.model_validate(load_schema_fixture("omc_workspace_project"))

    assert project.project_id == "omc-ingest"
    assert project.title == "吸收 OMC"
    assert project.project_type == "ingestion"
    assert project.owner == "user"
    assert project.chat_entry["mode"] == "task_card"
    assert project.capability_refs == [
        "cap_claude_code_cli",
        "cap_codex_cli",
        "cap_gemini_cli",
        "cap_gemini_web",
    ]


def test_workspace_project_embeds_external_reference_pool_refs(load_schema_fixture) -> None:
    project = WorkspaceProject.model_validate(load_schema_fixture("omc_workspace_project"))

    assert "source_omc_repo" in project.external_reference_refs
    assert "source_omc_debate_loop_docs" in project.external_reference_refs
    assert project.external_reference_refs
