# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    REPO_ROOT / "packages" / "noeticbraid-multimodel-alliance" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace import omc_knowledge_extractor as extractor
from noeticbraid_backend.omc_workspace.omc_knowledge_extractor import (
    LIVE_ENV,
    OMCKnowledgeExtractionError,
    OMCLiveEnrichmentError,
    extract_omc_knowledge,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE_PATHS = [
    FIXTURES / "omc_source_claude_md_sample.md",
    FIXTURES / "omc_source_rtk_md_sample.md",
]
FIXED_NOW = datetime(2026, 5, 13, tzinfo=timezone.utc)


def _artifact_path(ref: str) -> Path:
    return Path(ref.rsplit(":", 1)[0])


def test_extract_any_missing_source_raises(tmp_path: Path) -> None:
    existing = tmp_path / "exists.md"
    existing.write_text("# Present\n", encoding="utf-8")
    missing = tmp_path / "missing.md"

    with pytest.raises(OMCKnowledgeExtractionError) as exc_info:
        extract_omc_knowledge([existing, missing], live=False, artifact_root=tmp_path / "artifacts")

    assert exc_info.value.missing == [missing]
    assert str(missing) in str(exc_info.value)


def test_extract_deterministic_golden(tmp_path: Path) -> None:
    first = extract_omc_knowledge(SOURCE_PATHS, live=False, artifact_root=tmp_path / "first", extracted_at=FIXED_NOW)
    second = extract_omc_knowledge(SOURCE_PATHS, live=False, artifact_root=tmp_path / "second", extracted_at=FIXED_NOW)
    golden = (FIXTURES / "omc_narrative_artifact_golden.md").read_text(encoding="utf-8")

    first_text = _artifact_path(first.narrative_artifact_ref).read_text(encoding="utf-8")
    second_text = _artifact_path(second.narrative_artifact_ref).read_text(encoding="utf-8")

    assert first_text == second_text
    assert first_text == golden
    assert first.summary == (
        "Extracted 15 sections from 2 OMC source files "
        "(sha256: omc_source_claude_md_sample.md=cc266f5bcbbfacc9, "
        "omc_source_rtk_md_sample.md=9fe007d9d7ca790f); covers: "
        "oh-my-claudecode - Intelligent Multi-Agent Orchestration, "
        "operating_principles, delegation_rules, ..."
    )


def test_extract_section_titles_cover_known_omc_headers(tmp_path: Path) -> None:
    result = extract_omc_knowledge(SOURCE_PATHS, live=False, artifact_root=tmp_path, extracted_at=FIXED_NOW)
    titles = [section.title for section in result.outline]

    assert any("operating_principles" in title for title in titles)
    assert any("delegation_rules" in title for title in titles)
    assert any("model_routing" in title for title in titles)
    assert any("Meta Commands" in title for title in titles)


def test_live_mode_skipped_without_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("subprocess.run must not be called when live env is unset")

    monkeypatch.setattr(extractor.subprocess, "run", fail_if_called)

    result = extract_omc_knowledge(
        SOURCE_PATHS,
        live=os.getenv(LIVE_ENV) == "1",
        artifact_root=tmp_path,
        extracted_at=FIXED_NOW,
    )

    assert result.live_artifact_ref is None


def test_live_mode_subprocess_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_run(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(2, ["omx", "exec"])

    monkeypatch.setattr(extractor.subprocess, "run", fail_run)

    with pytest.raises(OMCLiveEnrichmentError) as exc_info:
        extract_omc_knowledge(SOURCE_PATHS, live=True, artifact_root=tmp_path, extracted_at=FIXED_NOW)

    assert "returned non-zero exit status 2" in str(exc_info.value)
    assert not list(tmp_path.glob("omc-knowledge-extraction-*.md"))
