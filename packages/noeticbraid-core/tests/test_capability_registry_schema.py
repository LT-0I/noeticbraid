from __future__ import annotations

from datetime import datetime, timezone

from noeticbraid_core.schemas import CapabilityHealthResult, CapabilityRegistryEntry


def _entries(load_schema_fixture) -> list[CapabilityRegistryEntry]:
    payload = load_schema_fixture("capability_registry_entries")
    return [CapabilityRegistryEntry.model_validate(item) for item in payload["entries"]]


def test_first_stage_registry_has_four_required_capabilities(load_schema_fixture) -> None:
    entries = _entries(load_schema_fixture)

    assert [entry.display_name for entry in entries] == [
        "Claude Code CLI",
        "Codex CLI",
        "Gemini CLI",
        "Gemini Web",
    ]
    assert all(entry.first_stage for entry in entries)
    assert [entry.end_type for entry in entries] == ["cli", "cli", "cli", "web"]


def test_capability_health_mode_labels_mock_vs_live_opt_in(load_schema_fixture) -> None:
    entries = _entries(load_schema_fixture)
    mock_result = CapabilityHealthResult(
        capability_id=entries[0].capability_id,
        mode="mock",
        status="available",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="mock ok",
    )
    live_result = CapabilityHealthResult(
        capability_id=entries[1].capability_id,
        mode="live_opt_in",
        status="available",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="live opt-in ok",
        artifact_ref=".omx/artifacts/capability-health-cap_codex_cli-20260512T000000Z.json",
    )

    assert entries[0].health_mode == "mock"
    assert mock_result.mode == "mock"
    assert live_result.mode == "live_opt_in"
