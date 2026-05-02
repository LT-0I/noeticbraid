from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from noeticbraid_core.user_growth_llmwiki import VaultScanConfig, VaultScanner

FIXED_NOW = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    snapshot: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[path.relative_to(root).as_posix()] = (path.stat().st_size, digest)
    return snapshot


def _fixture_vault(root: Path) -> None:
    _write(
        root / "Daily" / "2026-05-01.md",
        """---
hm_type: user_raw
hm_owner: user
---
Daily note links to [[Projects/Agent Systems/project]].
""",
    )
    _write(root / "Projects" / "Agent Systems" / "project.md", "Project note with no frontmatter.\n")
    _write(root / "Projects" / "agent_systems" / "idea.md", "Idea note with no frontmatter.\n")
    _write(root / "Projects" / "Orphan" / "a.md", "First orphan note.\n")
    _write(root / "Projects" / "Orphan" / "b.md", "Second orphan note.\n")
    _write(root / "Notes" / "AI" / "scratch.md", "AI-ish folder without explicit zone.\n")
    _write(
        root / "HelixMind_Episodic_Memory" / "50_digestion" / "item.md",
        """---
hm_type: digestion_item
hm_owner: noeticbraid
---
Candidate digestion fixture.
""",
    )


def _approved_config(root: Path) -> VaultScanConfig:
    return VaultScanConfig(approved_fixture_roots=(root,))


def test_scanner_default_fixture_only_mode_rejects_unapproved_directory(tmp_path: Path) -> None:
    _write(tmp_path / "Daily" / "2026-05-01.md", "This must not be read without explicit fixture approval.\n")

    with pytest.raises(PermissionError, match="approved fixture"):
        VaultScanner().scan(tmp_path, scanned_at=FIXED_NOW)


def test_scanner_profiles_fixture_without_modifying_files(tmp_path: Path) -> None:
    _fixture_vault(tmp_path)
    before = _snapshot(tmp_path)

    profile = VaultScanner(_approved_config(tmp_path)).scan(tmp_path, scanned_at=FIXED_NOW)

    assert _snapshot(tmp_path) == before
    assert profile.scanned_at == FIXED_NOW
    assert "Daily/" in profile.raw_user_zones
    assert "Projects/Agent Systems/" in profile.raw_user_zones
    assert "Projects/Orphan/" in profile.raw_user_zones
    assert "HelixMind_Episodic_Memory/50_digestion/" in profile.ai_allowed_zones
    assert any(note.path == "Daily/2026-05-01.md" and note.has_frontmatter for note in profile.note_summaries)
    assert any(link.source_path == "Daily/2026-05-01.md" and link.target == "Projects/Agent Systems/project.md" for link in profile.link_hints)
    assert all(not note.path.startswith("/") for note in profile.note_summaries)


def test_scanner_emits_missing_indexes_orphans_duplicate_topics_and_ai_risks(tmp_path: Path) -> None:
    _fixture_vault(tmp_path)

    profile = VaultScanner(_approved_config(tmp_path)).scan(tmp_path, scanned_at=FIXED_NOW)
    risk_codes = {risk.code for risk in profile.risk_flags}

    assert "missing_project_index" in risk_codes
    assert "orphan_cluster" in risk_codes
    assert "duplicate_topic_name" in risk_codes
    assert "missing_frontmatter_template" in risk_codes
    assert "ambiguous_ai_zone" in risk_codes
    assert "Projects/Orphan/_index.md" in profile.missing_indexes
    assert any(cluster.path == "Projects/Orphan/" and cluster.note_count == 2 for cluster in profile.orphan_clusters)
    assert any(topic.normalized_name == "agentsystems" for topic in profile.duplicate_topic_names)
