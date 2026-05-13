from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from noeticbraid.tools.multimodel_alliance.provider_round_parser import (
    ProviderRoundParseError,
    build_real_rounds,
    parse_provider_artifact,
)


def _artifact(tmp_path: Path, name: str, payload: dict[str, object] | str, *, prefix: str = "prose") -> Path:
    path = tmp_path / name
    body = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(f"{prefix}\n```json\n{body}\n```\n", encoding="utf-8")
    return path


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "objections": [
            {
                "objection_id": "obj_scope",
                "severity": "high",
                "status": "unresolved",
                "summary": "Scope still needs a blocker resolution.",
                "evidence_refs": ["artifact_round_1_codex"],
            }
        ],
        "recommendation": "Do not accept until the blocker is resolved.",
        "summary": "Provider found one blocker.",
    }
    payload.update(overrides)
    return payload


def _parse(path: Path, **overrides: Any) -> dict[str, Any]:
    params = {
        "role": "adversary",
        "round_index": 1,
        "provider": "codex",
        "model_ref": "model_codex_gpt_5_5",
        "source_refs": ["source_task_card"],
    }
    params.update(overrides)
    return parse_provider_artifact(path, **params)


def test_parse_provider_artifact_happy_path(tmp_path: Path) -> None:
    path = _artifact(tmp_path, "codex.md", _payload())

    round_record = _parse(path)

    assert round_record["round_id"] == "round_adversary_1"
    assert round_record["artifact_ref"] == "artifact_round_1_codex"
    assert round_record["role"] == "adversary"
    assert round_record["model_ref"] == "model_codex_gpt_5_5"
    assert round_record["source_refs"] == ["source_task_card"]
    assert round_record["round_type"] == "adversarial_review"
    assert round_record["verdict"] == "concern"
    assert round_record["summary"] == "Provider found one blocker."
    assert round_record["recommendation"] == "Do not accept until the blocker is resolved."
    assert round_record["objections"][0]["objection_id"] == "obj_scope"


def test_parse_provider_artifact_uses_last_json_block(tmp_path: Path) -> None:
    path = tmp_path / "multi.md"
    path.write_text(
        "example\n```json\n"
        + json.dumps(_payload(summary="Wrong example."))
        + "\n```\nreal\n```json\n"
        + json.dumps(_payload(summary="Real answer."))
        + "\n```\n",
        encoding="utf-8",
    )

    round_record = _parse(path)

    assert round_record["summary"] == "Real answer."


def test_parse_provider_artifact_no_json_block_raises(tmp_path: Path) -> None:
    path = tmp_path / "no-json.md"
    path.write_text("no fenced block", encoding="utf-8")

    with pytest.raises(ProviderRoundParseError) as excinfo:
        _parse(path)

    assert excinfo.value.reason == "no_json_block"
    assert excinfo.value.provider == "codex"


def test_parse_provider_artifact_malformed_json_raises(tmp_path: Path) -> None:
    path = _artifact(tmp_path, "bad.md", '{"objections": [}')

    with pytest.raises(ProviderRoundParseError) as excinfo:
        _parse(path)

    assert excinfo.value.reason == "invalid_json"


def test_parse_provider_artifact_missing_required_key_raises(tmp_path: Path) -> None:
    payload = _payload()
    del payload["objections"]
    path = _artifact(tmp_path, "missing.md", payload)

    with pytest.raises(ProviderRoundParseError) as excinfo:
        _parse(path)

    assert excinfo.value.reason == "missing_key:objections"


def test_parse_provider_artifact_invalid_status_raises(tmp_path: Path) -> None:
    payload = _payload(
        objections=[
            {
                "objection_id": "obj_bad",
                "severity": "medium",
                "status": "done",
                "summary": "Bad status.",
                "evidence_refs": [],
            }
        ]
    )
    path = _artifact(tmp_path, "bad-status.md", payload)

    with pytest.raises(ProviderRoundParseError) as excinfo:
        _parse(path)

    assert excinfo.value.reason == "invalid_status"


def test_parse_provider_artifact_forbidden_material_raises(tmp_path: Path) -> None:
    payload = _payload(
        objections=[
            {
                "objection_id": "obj_private",
                "severity": "medium",
                "status": "raised",
                "summary": "This raw_token marker must be rejected.",
                "evidence_refs": [],
            }
        ]
    )
    path = _artifact(tmp_path, "forbidden.md", payload)

    with pytest.raises(ProviderRoundParseError) as excinfo:
        _parse(path)

    assert excinfo.value.reason == "forbidden_material"


def test_build_real_rounds_outputs_fixed_provider_position_order(tmp_path: Path) -> None:
    plan_items = []
    for provider, model_ref in (
        ("codex", "model_codex_gpt_5_5"),
        ("gemini", "model_gemini_3_1_pro"),
        ("claude", "model_claude_opus_4_7"),
    ):
        artifact = _artifact(tmp_path, f"{provider}.md", _payload(objections=[], summary=f"{provider} summary"))
        plan_items.append(
            {
                "provider": provider,
                "model_ref": model_ref,
                "role": provider,
                "artifact_path": str(artifact),
            }
        )
    plan = {"artifact_root": str(tmp_path), "plans": plan_items}

    rounds, provider_artifacts = build_real_rounds(plan, {"task_id": "task_x", "source_refs": ["source_one", "source_one", "source_two"]})

    assert [item["role"] for item in rounds] == ["producer", "adversary", "source_auditor"]
    assert [item["artifact_ref"] for item in rounds] == [
        "artifact_round_0_claude",
        "artifact_round_1_codex",
        "artifact_round_2_gemini",
    ]
    assert [item["provider"] for item in provider_artifacts] == ["claude", "codex", "gemini"]
    assert provider_artifacts[0]["source_refs"] == ["source_one", "source_two"]


def test_build_real_rounds_partial_parse_failure_keeps_provider_context(tmp_path: Path) -> None:
    codex = _artifact(tmp_path, "codex.md", _payload())
    gemini = tmp_path / "gemini.md"
    gemini.write_text("missing json", encoding="utf-8")
    claude = _artifact(tmp_path, "claude.md", _payload(objections=[]))
    plan = {
        "artifact_root": str(tmp_path),
        "plans": [
            {"provider": "codex", "model_ref": "model_codex_gpt_5_5", "artifact_path": str(codex)},
            {"provider": "gemini", "model_ref": "model_gemini_3_1_pro", "artifact_path": str(gemini)},
            {"provider": "claude", "model_ref": "model_claude_opus_4_7", "artifact_path": str(claude)},
        ],
    }

    with pytest.raises(ProviderRoundParseError) as excinfo:
        build_real_rounds(plan, {"task_id": "task_x", "source_refs": ["source_one"]})

    assert excinfo.value.reason == "no_json_block"
    assert excinfo.value.provider == "gemini"
