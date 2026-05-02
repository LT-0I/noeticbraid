# SPDX-License-Identifier: Apache-2.0
"""Unit checks for the Stage 2.4 tracked private-leak scanner."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_PATH = REPO_ROOT / "scripts" / "private_leak_scan.py"
_SPEC = importlib.util.spec_from_file_location("private_leak_scan", _SCAN_PATH)
assert _SPEC is not None and _SPEC.loader is not None
private_leak_scan = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = private_leak_scan
_SPEC.loader.exec_module(private_leak_scan)


def test_parse_git_ls_files_requires_null_delimited_output() -> None:
    assert private_leak_scan.parse_git_ls_files_output(b"a.py\0nested/b.py\0") == ("a.py", "nested/b.py")

    try:
        private_leak_scan.parse_git_ls_files_output(b"a.py\nnested/b.py\n")
    except RuntimeError as exc:
        assert "null-delimited" in str(exc)
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("newline-delimited git output was accepted")


def test_scan_skips_private_tracked_paths(tmp_path: Path) -> None:
    rel_path = "private/synthetic_secret.py"
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True)
    path.write_text('raw_token = "synthetic-value"\n', encoding="utf-8")

    report = private_leak_scan.scan_paths(tmp_path, [rel_path])

    assert report.scanned_files == 0
    assert report.skipped_private_files == 1
    assert report.findings == ()


def test_scan_reports_marker_without_secret_value(tmp_path: Path) -> None:
    rel_path = "public_module.py"
    secret_value = "synthetic-secret-value"
    (tmp_path / rel_path).write_text(f'raw_token = "{secret_value}"\n', encoding="utf-8")

    report = private_leak_scan.scan_paths(tmp_path, [rel_path])

    assert len(report.findings) == 1
    rendered = report.findings[0].render()
    assert "public_module.py:1" in rendered
    assert "marker=raw_token" in rendered
    assert secret_value not in rendered
    assert "<redacted" in rendered


def test_contextual_negative_markdown_marker_reference_is_allowed(tmp_path: Path) -> None:
    rel_path = "GPT5_Workflow/archive/phase-1.2/stage-2.4/prompt.md"
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True)
    path.write_text("Do not expose private markers such as raw_token in public payloads.\n", encoding="utf-8")

    report = private_leak_scan.scan_paths(tmp_path, [rel_path])

    assert report.findings == ()


def test_stage2_4_smoke_allowlist_is_not_whole_file_marker_allowance(tmp_path: Path) -> None:
    rel_path = "packages/noeticbraid-backend/tests/test_stage2_4_integration_smoke.py"
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True)
    path.write_text("raw_token = 'synthetic value outside the marker tuple allowlist'\n", encoding="utf-8")

    report = private_leak_scan.scan_paths(tmp_path, [rel_path])

    assert len(report.findings) == 1
    assert report.findings[0].marker == "raw_token"


def test_review_markdown_allowlist_requires_specific_hint_phrase(tmp_path: Path) -> None:
    rel_path = "docs/reviews/phase1.2/stage2_integration_review_template.md"
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True)
    path.write_text("This private implementation detail mentions raw_token.\n", encoding="utf-8")

    report = private_leak_scan.scan_paths(tmp_path, [rel_path])

    assert len(report.findings) == 1
    assert report.findings[0].marker == "raw_token"


def test_tracked_files_fail_closed_when_git_is_unavailable(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        del args, kwargs
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        private_leak_scan.tracked_files(REPO_ROOT)
    except RuntimeError as exc:
        assert "git is unavailable" in str(exc)
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("git-unavailable path did not fail closed")
