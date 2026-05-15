from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "noeticbraid-core" / "src"))

from noeticbraid_core.user_growth_llmwiki.b1_detector import CandidateB1SideNote
from noeticbraid_obsidian import ingest_side_note
from noeticbraid_obsidian.errors import RenderError, WritePolicyViolation
from noeticbraid_obsidian.settings import default_settings


def valid_candidate(**overrides: object) -> CandidateB1SideNote:
    kwargs: dict[str, object] = {
        "candidate_id": "note_bcc_001",
        "project_ref": "proj/x",
        "window_id": "w1",
        "evidence_source": ["notes.md:42"],
        "claim": "你提到项目 X 已多次未推进，原因？",
        "created_at": "2026-05-15T09:00:00+00:00",
        "mention_count_same_day_dedup": 5,
        "progress_checks": {"committed": False},
    }
    kwargs.update(overrides)
    return CandidateB1SideNote(**kwargs)


def test_full_chain_dry_run_default_r3_path(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    res = ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

    assert res.dry_run is True
    assert res.written is False
    assert "20_episodic_memory/20_ai_observations/side_notes/2026/05/" in res.relative_path
    assert PurePosixPath(res.relative_path).stem == c.candidate_id
    assert not res.relative_path.startswith("NoeticBraid/20_episodic_memory/10_user_raw/")
    assert "20_episodic_memory/10_user_raw" not in res.relative_path


def test_created_at_json_mode_is_iso_string_python_mode_is_datetime(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

    assert isinstance(sn.model_dump(mode="python")["created_at"], datetime)
    assert isinstance(sn.model_dump(mode="json")["created_at"], str)
    assert sn.model_dump(mode="json")["created_at"][:10] == "2026-05-15"


def test_evidence_source_equals_linked_source_refs_through_chain(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

    assert rec["evidence_source"] == rec["linked_source_refs"]

    mutated = dict(rec)
    mutated["evidence_source"] = ["notes.md:43"]
    with pytest.raises(RenderError):
        ingest_side_note(mutated, vault_root=tmp_path, body=sn.claim)


def test_claim_flows_to_body_preview(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    res = ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

    assert sn.claim in res.preview_text


def test_all_note_types_chain_and_path_invariant(tmp_path) -> None:
    for note_type in ("fact", "hypothesis", "action_suggestion"):
        c = valid_candidate(note_type=note_type)
        sn = c.to_sidenote(c.candidate_id)
        rec = sn.model_dump(mode="json")
        res = ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

        assert res.dry_run is True
        assert "20_episodic_memory/20_ai_observations/side_notes/" in res.relative_path
        assert "20_episodic_memory/10_user_raw" not in res.relative_path


def test_model_dump_json_keys_superset_of_render_required(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    ingest_side_note(rec, vault_root=tmp_path, body=sn.claim)

    assert {
        "note_id",
        "created_at",
        "linked_source_refs",
        "evidence_source",
        "note_type",
        "confidence",
        "tone_constraint",
        "user_response_channel",
        "user_response",
    } <= set(rec)


def test_live_mode_writes_file_via_real_delegation(tmp_path) -> None:
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    res = ingest_side_note(
        rec,
        vault_root=tmp_path,
        body=sn.claim,
        settings=default_settings(write_mode="live"),
    )

    assert res.written is True
    assert res.dry_run is False
    assert "20_episodic_memory/20_ai_observations/side_notes/2026/05/" in res.relative_path
    assert res.absolute_path == tmp_path / res.relative_path
    assert res.absolute_path.exists()
    assert sn.claim in res.absolute_path.read_text(encoding="utf-8")


def test_create_only_second_chain_ingest_raises(tmp_path) -> None:
    settings = default_settings(write_mode="live")
    c = valid_candidate()
    sn = c.to_sidenote(c.candidate_id)
    rec = sn.model_dump(mode="json")
    first = ingest_side_note(rec, vault_root=tmp_path, body=sn.claim, settings=settings)
    before = first.absolute_path.read_text(encoding="utf-8")

    with pytest.raises(WritePolicyViolation):
        ingest_side_note(rec, vault_root=tmp_path, body=sn.claim, settings=settings)

    assert first.absolute_path.read_text(encoding="utf-8") == before
