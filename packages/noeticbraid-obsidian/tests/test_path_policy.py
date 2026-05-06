from __future__ import annotations

from pathlib import Path

import pytest

from noeticbraid_obsidian.path_policy import ModeEnforcer, PathPolicyError, resolve_path
from noeticbraid_obsidian.settings import default_settings


def test_mode_enforcer_matches_allowlist_and_denies_escape_paths() -> None:
    settings = default_settings()
    enforcer = ModeEnforcer(settings)

    assert enforcer.is_allowed_write_path("NoeticBraid/00_dashboard/today.md") is True
    assert enforcer.is_allowed_write_path("NoeticBraid/30_run_ledger/10_runs/2026/05/run_1.md") is True

    for unsafe in [
        "../NoeticBraid/00_dashboard/today.md",
        "NoeticBraid/00_dashboard/../../outside.md",
        "NoeticBraid/.obsidian/plugins/noeticbraid/main.js",
        "NoeticBraid/project/.git/config",
        "NoeticBraid/20_episodic_memory/10_user_raw/daily_notes/2026-05-02.md",
        "OtherNamespace/00_dashboard/today.md",
        "C:/Users/alice/Vault/NoeticBraid/00_dashboard/today.md",
    ]:
        assert enforcer.is_allowed_write_path(unsafe) is False


def test_resolve_path_generates_contract_relative_paths() -> None:
    assert resolve_path("dashboard", "today", date="2026-05-06") == "NoeticBraid/00_dashboard/today.md"
    assert resolve_path("run_record", "run_20260506_001", date="2026-05-06") == (
        "NoeticBraid/30_run_ledger/10_runs/2026/05/run_20260506_001.md"
    )
    assert resolve_path("side_note", "note_20260506_001", date="2026-05-06") == (
        "NoeticBraid/20_episodic_memory/20_ai_observations/side_notes/2026/05/note_20260506_001.md"
    )


def test_resolve_path_rejects_model_supplied_path_fragments() -> None:
    with pytest.raises(PathPolicyError):
        resolve_path("run_record", "../escape", date="2026-05-06")
    with pytest.raises(PathPolicyError):
        resolve_path("unknown", "item_1", date="2026-05-06")


def test_enforcer_resolves_absolute_path_inside_vault(tmp_path: Path) -> None:
    enforcer = ModeEnforcer(default_settings())

    resolved = enforcer.resolve_under_vault(tmp_path, "NoeticBraid/00_dashboard/today.md")

    assert resolved == tmp_path / "NoeticBraid" / "00_dashboard" / "today.md"
    with pytest.raises(PathPolicyError):
        enforcer.resolve_under_vault(tmp_path, "../outside.md")
