from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

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


def test_capability_health_result_schema_includes_error_msg_optional() -> None:
    result = CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="live_opt_in",
        status="unhealthy",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="failed safely",
        error_msg="codex executable not found",
    )

    assert result.error_msg == "codex executable not found"
    assert CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="mock",
        status="available",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="mock ok",
    ).error_msg is None
    try:
        CapabilityHealthResult(
            capability_id="cap_codex_cli",
            mode="live_opt_in",
            status="unhealthy",
            checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
            summary="failed safely",
            error_msg="x" * 257,
        )
    except ValidationError:
        pass
    else:  # pragma: no cover - explicit assertion branch for pytest output
        raise AssertionError("error_msg longer than 256 chars was accepted")


def test_capability_health_result_schema_includes_last_checked() -> None:
    result = CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="live_opt_in",
        status="healthy",
        checked_at=datetime(2026, 5, 12, 12, 0, 0),
        summary="live ok",
        last_checked=datetime(2026, 5, 12, 12, 0, 0),
    )

    assert result.last_checked == datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_capability_health_result_schema_includes_version_optional() -> None:
    result = CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="live_opt_in",
        status="healthy",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="live ok",
        version="codex 5.5",
    )

    assert result.version == "codex 5.5"
    assert CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="mock",
        status="available",
        checked_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        summary="mock ok",
    ).version is None


def test_capability_health_status_accepts_healthy_unhealthy_not_implemented() -> None:
    checked_at = datetime(2026, 5, 12, tzinfo=timezone.utc)

    assert CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="live_opt_in",
        status="healthy",
        checked_at=checked_at,
        summary="live ok",
    ).status == "healthy"
    assert CapabilityHealthResult(
        capability_id="cap_codex_cli",
        mode="live_opt_in",
        status="unhealthy",
        checked_at=checked_at,
        summary="failed safely",
    ).status == "unhealthy"
    assert CapabilityHealthResult(
        capability_id="cap_gemini_web",
        mode="live_opt_in",
        status="not_implemented",
        checked_at=checked_at,
        summary="deferred",
    ).status == "not_implemented"
