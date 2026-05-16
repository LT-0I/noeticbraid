# SPDX-License-Identifier: Apache-2.0
"""Planning artifact naming and completeness helpers."""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Sequence

PlanningArtifactKind = Literal[
    "prd",
    "test-spec",
    "deep-interview",
    "deep-interview-autoresearch",
]
PLANNING_ARTIFACT_TIMESTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


@dataclass(frozen=True)
class PlanningArtifactNameInfo:
    """Parsed planning artifact filename information."""

    kind: PlanningArtifactKind
    slug: str
    timestamp: str | None = None


def planning_artifact_timestamp(date: datetime | None = None) -> str:
    """Return upstream timestamp format `YYYYMMDDTHHMMSSZ`."""

    value = date or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _legacy_test_spec_slug(file_name_or_path: str) -> str | None:
    match = re.match(r"^test-?spec-(?P<slug>.+)\.md$", Path(file_name_or_path).name, re.I)
    return match.group("slug") if match else None


def _required_timestamped_test_spec_file_name(
    prd_artifact: PlanningArtifactNameInfo,
) -> str | None:
    if prd_artifact.kind == "prd" and prd_artifact.timestamp:
        return f"test-spec-{prd_artifact.timestamp}-{prd_artifact.slug}.md"
    return None


def _split_timestamp_prefix(raw_slug: str) -> tuple[str, str | None]:
    separator_index = raw_slug.find("-")
    if separator_index == -1:
        return raw_slug, None
    prefix = raw_slug[:separator_index]
    if PLANNING_ARTIFACT_TIMESTAMP_RE.fullmatch(prefix) is None:
        return raw_slug, None
    return raw_slug[separator_index + 1 :], prefix


def parse_planning_artifact_file_name(
    file_name_or_path: str,
) -> PlanningArtifactNameInfo | None:
    """Parse artifact filenames using the upstream prefix and slug rules."""

    file_name = Path(file_name_or_path).name
    patterns: tuple[tuple[PlanningArtifactKind, re.Pattern[str]], ...] = (
        (
            "deep-interview-autoresearch",
            re.compile(r"^deep-interview-autoresearch-(?P<slug>.+)\.md$", re.I),
        ),
        ("deep-interview", re.compile(r"^deep-interview-(?P<slug>.+)\.md$", re.I)),
        ("prd", re.compile(r"^prd-(?P<slug>.+)\.md$", re.I)),
        ("test-spec", re.compile(r"^test-?spec-(?P<slug>.+)\.md$", re.I)),
    )
    for kind, pattern in patterns:
        match = pattern.match(file_name)
        if not match:
            continue
        slug, timestamp = _split_timestamp_prefix(match.group("slug"))
        if not slug:
            return None
        return PlanningArtifactNameInfo(kind=kind, slug=slug, timestamp=timestamp)
    return None


def planning_artifact_slug(
    file_name_or_path: str,
    kind: PlanningArtifactKind,
) -> str | None:
    """Return the slug when the filename parses as the requested kind."""

    parsed = parse_planning_artifact_file_name(file_name_or_path)
    return parsed.slug if parsed and parsed.kind == kind else None


def compare_planning_artifact_paths(left: str, right: str) -> int:
    """Comparator matching upstream timestamp-aware artifact ordering."""

    left_parsed = parse_planning_artifact_file_name(left)
    right_parsed = parse_planning_artifact_file_name(right)
    if (
        left_parsed
        and right_parsed
        and left_parsed.timestamp
        and right_parsed.timestamp
        and left_parsed.timestamp != right_parsed.timestamp
    ):
        return (left_parsed.timestamp > right_parsed.timestamp) - (
            left_parsed.timestamp < right_parsed.timestamp
        )
    if left_parsed and left_parsed.timestamp and not (right_parsed and right_parsed.timestamp):
        return 1
    if not (left_parsed and left_parsed.timestamp) and right_parsed and right_parsed.timestamp:
        return -1
    return (left > right) - (left < right)


def sort_planning_artifact_paths(paths: Sequence[str]) -> list[str]:
    """Sort paths with the upstream comparator."""

    return sorted(paths, key=functools.cmp_to_key(compare_planning_artifact_paths))


def select_matching_test_specs_for_prd(
    prd_path: str | None,
    test_spec_paths: Sequence[str],
) -> list[str]:
    """Select timestamped or legacy test specs matching a PRD artifact."""

    if not prd_path:
        return []
    prd_artifact = parse_planning_artifact_file_name(prd_path)
    if not prd_artifact or prd_artifact.kind != "prd":
        return []
    required = _required_timestamped_test_spec_file_name(prd_artifact)
    if required:
        selected = [path for path in test_spec_paths if Path(path).name == required]
    else:
        selected = [
            path for path in test_spec_paths if _legacy_test_spec_slug(path) == prd_artifact.slug
        ]
    return sort_planning_artifact_paths(selected)


def select_latest_planning_artifact_path(paths: Sequence[str]) -> str | None:
    """Return the last path after upstream artifact sorting."""

    sorted_paths = sort_planning_artifact_paths(paths)
    return sorted_paths[-1] if sorted_paths else None


def get_markdown_section(markdown: str, heading: str) -> str | None:
    """Return non-empty body for a level-2 markdown heading."""

    heading_re = re.compile(rf"^##\s+{re.escape(heading)}[ \t]*$", re.I | re.M)
    match = heading_re.search(markdown)
    if not match:
        return None
    rest = markdown[match.end() :]
    rest = re.sub(r"^\r?\n", "", rest)
    next_heading = re.search(r"\r?\n##\s+", rest)
    body = rest[: next_heading.start()] if next_heading else rest
    body = body.strip()
    return body or None


def has_required_sections(markdown: str, headings: Sequence[str]) -> bool:
    """Return true when all required level-2 headings have non-empty bodies."""

    return all(get_markdown_section(markdown, heading) is not None for heading in headings)


def has_complete_planning_pair(prd_markdown: str, test_spec_markdown: str) -> bool:
    """Validate the required PRD/test-spec quality-gate sections."""

    return has_required_sections(
        prd_markdown,
        ("Acceptance criteria", "Requirement coverage map"),
    ) and has_required_sections(
        test_spec_markdown,
        ("Unit coverage", "Verification mapping"),
    )


__all__ = [
    "PLANNING_ARTIFACT_TIMESTAMP_RE",
    "PlanningArtifactKind",
    "PlanningArtifactNameInfo",
    "compare_planning_artifact_paths",
    "get_markdown_section",
    "has_complete_planning_pair",
    "has_required_sections",
    "parse_planning_artifact_file_name",
    "planning_artifact_slug",
    "planning_artifact_timestamp",
    "select_latest_planning_artifact_path",
    "select_matching_test_specs_for_prd",
    "sort_planning_artifact_paths",
]
