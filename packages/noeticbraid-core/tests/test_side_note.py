"""SDD-D1-01 SideNote 2.0.0 metadata tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from noeticbraid_core.schemas import SideNote
from noeticbraid_core.schemas.side_note import TONE_CONSTRAINT_LITERAL, USER_RESPONSE_CHANNEL_VALUES


def _valid_side_note_data() -> dict[str, object]:
    return {
        "note_id": "note_sdd_d1_001",
        "created_at": "2026-05-11T12:00:00Z",
        "linked_source_refs": ["source_sdd_d1_001"],
        "evidence_source": ["source_sdd_d1_001"],
        "note_type": "fact",
        "claim": "过去 14 天的笔记中提到此项目 4 次但未记录进展。",
        "confidence": "medium",
        "user_response": "unread",
        "tone_constraint": TONE_CONSTRAINT_LITERAL,
        "user_response_channel": list(USER_RESPONSE_CHANNEL_VALUES),
        "follow_up_ref": None,
    }


@pytest.mark.parametrize(
    "metadata_field",
    ["evidence_source", "note_type", "confidence", "tone_constraint", "user_response_channel"],
)
def test_metadata_required_fields(metadata_field: str) -> None:
    data = _valid_side_note_data()
    data.pop(metadata_field)

    with pytest.raises(ValidationError):
        SideNote.model_validate(data)


@pytest.mark.parametrize("legacy_note_type", ["challenge", "action"])
def test_note_type_enum_regression(legacy_note_type: str) -> None:
    data = _valid_side_note_data()
    data["note_type"] = legacy_note_type

    with pytest.raises(ValidationError):
        SideNote.model_validate(data)


def test_tone_constraint_literal() -> None:
    assert SideNote.model_validate(_valid_side_note_data()).tone_constraint == TONE_CONSTRAINT_LITERAL

    data = _valid_side_note_data()
    data["tone_constraint"] = "不审判 / 不羞辱 / 不替用户解释自己"

    with pytest.raises(ValidationError):
        SideNote.model_validate(data)


def test_evidence_source_must_mirror_linked_source_refs() -> None:
    data = _valid_side_note_data()
    data["evidence_source"] = ["source_other_001"]

    with pytest.raises(ValidationError):
        SideNote.model_validate(data)
