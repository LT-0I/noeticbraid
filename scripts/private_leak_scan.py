#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tracked-file private marker scan with fail-closed git enumeration.

The scan uses `git ls-files -z` as the source of truth for public repository
files, never reads private/**, skips binary/dependency/cache artifacts, and
prints only path/line/marker redacted findings.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

MARKERS: tuple[str, ...] = (
    "cookie_value",
    "cookie_jar_path",
    "csrf_token",
    "session_token",
    "encrypted_password",
    "browser_session_id",
    "raw_token",
    "token_hash",
    "dpapi_blob",
    "credential_path",
    "profile_path",
    "profile_dir",
    "account_id",
    "profile_id",
    "quota_window",
)

# account_hint is intentionally absent: Phase 1.1 exposes it as a public,
# non-secret hint field by contract design.
MARKER_PATTERNS = {
    marker: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])", re.IGNORECASE)
    for marker in MARKERS
}

SKIP_PATH_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "bower_components",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)

PRIVATE_PATH_PARTS = frozenset(
    {
        "private",
        "browser_profile_state",
        "browser_profiles",
        "credential_cache",
        "credential_store",
        "profile_state",
    }
)

MARKDOWN_ALLOWLIST_HINT_PHRASES = (
    "do not expose private markers",
    "must not expose private markers",
    "public payloads exclude private marker names",
    "public response bodies contain no private marker material",
    "marker-name assertions as review evidence",
    "forbidden marker names for sanitizer assertions",
    "reports only path, line number, and marker name",
    "redacted excerpt",
    "private-leak scan",
)


@dataclass(frozen=True)
class AllowlistRule:
    """A narrow marker-name exception for internal implementation/test files."""

    path_glob: str
    markers: frozenset[str]
    reason: str

    def matches(self, rel_path: str, marker: str) -> bool:
        return marker in self.markers and fnmatch.fnmatch(rel_path, self.path_glob)


@dataclass(frozen=True)
class MarkerLineAllowlistRule:
    """A marker exception bound to one tracked path and one line."""

    rel_path: str
    line_number: int
    marker: str
    reason: str

    def matches(self, rel_path: str, line_number: int, marker: str) -> bool:
        return self.rel_path == rel_path and self.line_number == line_number and self.marker == marker


def _line_rules(
    rel_path: str,
    marker_lines: tuple[tuple[int, str], ...],
    reason: str,
) -> tuple[MarkerLineAllowlistRule, ...]:
    return tuple(
        MarkerLineAllowlistRule(rel_path=rel_path, line_number=line_number, marker=marker, reason=reason)
        for line_number, marker in marker_lines
    )


# Allowlist rationale:
# - This scanner and its tests must contain the marker lexicon and synthetic
#   redaction examples.
# - Backend auth/token storage is the internal auth-bearing implementation from
#   Stage 2.2; it stores hashes at rest and must not expose them publicly.
# - Backend dashboard and read-route tests enumerate marker names only to prove
#   public responses are sanitized.
# - Stage 2.4 smoke enumerates public-forbidden markers in one tuple; every
#   exception is bound below by path, line, and marker.
# - Historical Stage 2 archive prompts/reports may record marker-name assertions
#   as review evidence; contextual markdown hits are limited to specific phrases.
ALLOWLIST_RULES: tuple[AllowlistRule, ...] = (
    AllowlistRule("scripts/private_leak_scan.py", frozenset(MARKERS), "scanner owns the marker lexicon"),
    AllowlistRule("tests/test_private_leak_scan.py", frozenset(MARKERS), "scanner unit tests use synthetic marker names"),
    AllowlistRule(
        "packages/noeticbraid-backend/src/noeticbraid_backend/auth/token_store.py",
        frozenset({"account_id", "raw_token", "token_hash"}),
        "internal token store; raw material is returned once and hashes stay at rest",
    ),
    AllowlistRule(
        "packages/noeticbraid-backend/src/noeticbraid_backend/api/routes/dashboard.py",
        frozenset({"account_id", "raw_token", "token_hash", "dpapi_blob", "credential_path", "profile_path", "profile_dir"}),
        "dashboard sanitizer denies these marker names from public summaries",
    ),
    AllowlistRule(
        "packages/noeticbraid-backend/tests/test_app_contract_routes.py",
        frozenset({"account_id", "token_hash"}),
        "backend auth tests assert secret markers are absent from public responses",
    ),
    AllowlistRule(
        "packages/noeticbraid-backend/tests/test_console_read_api_backend.py",
        frozenset({"account_id", "raw_token", "token_hash", "dpapi_blob", "profile_path", "profile_dir"}),
        "Console read-surface tests seed synthetic forbidden marker names for sanitizer assertions",
    ),
)

LINE_ALLOWLIST_RULES: tuple[MarkerLineAllowlistRule, ...] = (
    *_line_rules(
        "docs/architecture/step5_phase1_1_design.md",
        (
            (116, "cookie_jar_path"),
            (118, "account_id"),
            (119, "quota_window"),
            (120, "profile_id"),
            (120, "profile_dir"),
        ),
        "Phase 1.1 design doc lists fields forbidden from Stage 0 public schema",
    ),
    *_line_rules(
        "packages/noeticbraid-backend/tests/test_auth_startup_token_contract.py",
        (
            (156, "raw_token"),
            (157, "raw_token"),
            (158, "raw_token"),
        ),
        "startup-token contract test proves bearer token is header-only and absent from body",
    ),
    *_line_rules(
        "packages/noeticbraid-backend/tests/test_token_store.py",
        (
            (27, "token_hash"),
            (27, "account_id"),
            (62, "token_hash"),
            (63, "account_id"),
            (153, "token_hash"),
            (154, "account_id"),
            (161, "token_hash"),
            (167, "token_hash"),
            (168, "account_id"),
        ),
        "internal token-store tests assert hashed-token persistence semantics",
    ),
    *_line_rules(
        "packages/noeticbraid-backend/tests/test_stage2_4_integration_smoke.py",
        (
            (40, "cookie_value"),
            (41, "cookie_jar_path"),
            (42, "csrf_token"),
            (43, "session_token"),
            (44, "encrypted_password"),
            (45, "browser_session_id"),
            (46, "raw_token"),
            (47, "token_hash"),
            (48, "dpapi_blob"),
            (49, "credential_path"),
            (50, "profile_path"),
            (51, "profile_dir"),
            (52, "account_id"),
            (53, "profile_id"),
            (54, "quota_window"),
        ),
        "Stage 2.4 smoke public-payload forbidden marker tuple",
    ),
)


@dataclass(frozen=True)
class Finding:
    rel_path: str
    line_number: int
    marker: str

    def render(self) -> str:
        return f"{self.rel_path}:{self.line_number}: marker={self.marker} excerpt=<redacted:marker-name-only>"


@dataclass(frozen=True)
class ScanReport:
    scanned_files: int
    skipped_private_files: int
    skipped_binary_files: int
    findings: tuple[Finding, ...]


def parse_git_ls_files_output(output: bytes) -> tuple[str, ...]:
    """Parse null-delimited git output or raise to fail closed."""

    if output == b"":
        return ()
    if not output.endswith(b"\0"):
        raise RuntimeError("git ls-files output was not null-delimited")
    raw_items = output[:-1].split(b"\0")
    if any(item == b"" for item in raw_items):
        raise RuntimeError("git ls-files output contained an empty path entry")
    try:
        return tuple(item.decode("utf-8") for item in raw_items)
    except UnicodeDecodeError as exc:
        raise RuntimeError("git ls-files output contained a non-UTF-8 path") from exc


def tracked_files(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return tracked paths using required `git ls-files -z`; fail closed."""

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is unavailable; refusing partial private-leak scan") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files -z failed; refusing partial private-leak scan: {stderr}")
    return parse_git_ls_files_output(result.stdout)


def _path_parts(rel_path: str) -> tuple[str, ...]:
    return tuple(part for part in Path(rel_path).parts if part not in {"", "."})


def should_skip_path(rel_path: str) -> bool:
    parts = _path_parts(rel_path)
    if not parts:
        return True
    if parts[0] == "private" or any(part in PRIVATE_PATH_PARTS for part in parts):
        return True
    return any(part in SKIP_PATH_PARTS for part in parts)


def is_private_path(rel_path: str) -> bool:
    parts = _path_parts(rel_path)
    return bool(parts) and (parts[0] == "private" or any(part in PRIVATE_PATH_PARTS for part in parts))


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:4096]


def _is_allowlisted(rel_path: str, line_number: int, marker: str, line_context: str) -> bool:
    for rule in LINE_ALLOWLIST_RULES:
        if rule.matches(rel_path, line_number, marker):
            return True
    for rule in ALLOWLIST_RULES:
        if rule.matches(rel_path, marker):
            return True
    if rel_path.startswith("GPT5_Workflow/archive/phase-1.2/stage-2.") and rel_path.endswith(".md"):
        return _looks_like_allowed_marker_markdown(line_context)
    if rel_path.startswith("docs/reviews/phase1.2/") and rel_path.endswith(".md"):
        return _looks_like_allowed_marker_markdown(line_context)
    return False


def _looks_like_allowed_marker_markdown(line_context: str) -> bool:
    lowered = line_context.lower()
    return any(phrase in lowered for phrase in MARKDOWN_ALLOWLIST_HINT_PHRASES)


def _line_context(lines: Sequence[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(lines), index + 2)
    return "\n".join(lines[start:end])


def scan_text(rel_path: str, text: str) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        context = _line_context(lines, index)
        for marker, pattern in MARKER_PATTERNS.items():
            if pattern.search(line) is None:
                continue
            if _is_allowlisted(rel_path, index + 1, marker, context):
                continue
            findings.append(Finding(rel_path=rel_path, line_number=index + 1, marker=marker))
    return tuple(findings)


def scan_paths(repo_root: Path, paths: Iterable[str]) -> ScanReport:
    scanned_files = 0
    skipped_private_files = 0
    skipped_binary_files = 0
    findings: list[Finding] = []
    for rel_path in paths:
        if is_private_path(rel_path):
            skipped_private_files += 1
            continue
        if should_skip_path(rel_path):
            continue
        path = repo_root / rel_path
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(Finding(rel_path=rel_path, line_number=0, marker="unreadable_file"))
            continue
        if is_binary(data):
            skipped_binary_files += 1
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped_binary_files += 1
            continue
        scanned_files += 1
        findings.extend(scan_text(rel_path, text))
    return ScanReport(
        scanned_files=scanned_files,
        skipped_private_files=skipped_private_files,
        skipped_binary_files=skipped_binary_files,
        findings=tuple(findings),
    )


def run_scan(repo_root: Path = REPO_ROOT) -> ScanReport:
    return scan_paths(repo_root, tracked_files(repo_root))


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        report = run_scan(REPO_ROOT)
    except Exception as exc:
        print("private_leak_scan: FAIL (fail-closed before scanning)")
        print(f"  - {type(exc).__name__}: {exc}")
        return 1
    if report.findings:
        print(f"private_leak_scan: FAIL ({len(report.findings)} finding(s); report is redacted)")
        for finding in report.findings:
            print(f"  - {finding.render()}")
        return 1
    print(
        "private_leak_scan: PASS "
        f"(scanned_files={report.scanned_files}, "
        f"skipped_private_files={report.skipped_private_files}, "
        f"skipped_binary_files={report.skipped_binary_files})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
