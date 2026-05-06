from __future__ import annotations

import pytest

from noeticbraid.tools.notebooklm_bridge import NotebookLMInputError, to_source_records


def test_to_source_records_normalizes_non_contract_run_id() -> None:
    record = to_source_records("notebook-abc", "Briefing", "run-123")[0]
    assert record["retrieved_by_run_id"] == "run_run_123"
    assert record["local_path"].startswith("notebooklm://notebook/notebook_abc/")


@pytest.mark.parametrize("args", [("", "briefing", "run_1"), ("nb", "", "run_1"), ("nb", "briefing", "")])
def test_to_source_records_rejects_empty_inputs(args) -> None:
    with pytest.raises(NotebookLMInputError):
        to_source_records(*args)


def test_serializer_rejects_invalid_enum() -> None:
    from noeticbraid.tools.notebooklm_bridge import NotebookLMSerializationError
    from noeticbraid.tools.notebooklm_bridge._serializer import _validate_enum

    with pytest.raises(NotebookLMSerializationError):
        _validate_enum("evidence_role", "invalid_value", {"source_grounding"})
