# SPDX-License-Identifier: Apache-2.0
"""Verification tier selector ported from oh-my-claudecode."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

TestCoverage = Literal["none", "partial", "full"]
VerificationTier = Literal["LIGHT", "STANDARD", "THOROUGH"]
VerificationModel = Literal["haiku", "sonnet", "opus"]


@dataclass(frozen=True)
class ChangeMetadata:
    """Inputs used to scale verification effort."""

    files_changed: int
    lines_changed: int
    has_architectural_changes: bool
    has_security_implications: bool
    test_coverage: TestCoverage


@dataclass(frozen=True)
class VerificationAgent:
    """Agent and evidence requirements for a tier."""

    agent: str
    model: VerificationModel
    evidence_required: tuple[str, ...]


TIER_AGENTS: dict[VerificationTier, VerificationAgent] = {
    "LIGHT": VerificationAgent(
        agent="architect-low",
        model="haiku",
        evidence_required=("lsp_diagnostics clean",),
    ),
    "STANDARD": VerificationAgent(
        agent="architect-medium",
        model="sonnet",
        evidence_required=("lsp_diagnostics clean", "build pass"),
    ),
    "THOROUGH": VerificationAgent(
        agent="architect",
        model="opus",
        evidence_required=("full architect review", "all tests pass", "no regressions"),
    ),
}

_ARCHITECTURAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"config\.(ts|js|json)$", re.I),
    re.compile(r"schema\.(ts|prisma|sql)$", re.I),
    re.compile(r"definitions\.ts$", re.I),
    re.compile(r"(?:^|/)types\.ts$", re.I),
    re.compile(r"package\.json$", re.I),
    re.compile(r"tsconfig\.json$", re.I),
)
_SECURITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/auth/", re.I),
    re.compile(r"/security/", re.I),
    re.compile(r"(^|[/\-])permissions?\.(ts|js)$", re.I),
    re.compile(r"(^|[/\-])credentials?\.(ts|js|json)$", re.I),
    re.compile(r"(^|[/\-])secrets?\.(ts|js|json|ya?ml)$", re.I),
    re.compile(r"(^|[/\-])tokens?\.(ts|js|json)$", re.I),
    re.compile(r"\.(env|pem|key)(\.|$)", re.I),
    re.compile(r"(^|[/\-])passwords?\.(ts|js|json)$", re.I),
    re.compile(r"(^|[/\-])oauth", re.I),
    re.compile(r"(^|[/\-])jwt", re.I),
)


def select_verification_tier(changes: ChangeMetadata) -> VerificationTier:
    """Select upstream LIGHT/STANDARD/THOROUGH tier from change metadata."""

    if changes.has_security_implications or changes.has_architectural_changes:
        return "THOROUGH"
    if changes.files_changed > 20:
        return "THOROUGH"
    if (
        changes.files_changed < 5
        and changes.lines_changed < 100
        and changes.test_coverage == "full"
    ):
        return "LIGHT"
    return "STANDARD"


def get_verification_agent(tier: VerificationTier) -> VerificationAgent:
    """Return the upstream agent configuration for a tier."""

    return TIER_AGENTS[tier]


def detect_architectural_changes(files: Sequence[str]) -> bool:
    """Detect whether any changed file matches upstream architecture patterns."""

    return any(pattern.search(file) for file in files for pattern in _ARCHITECTURAL_PATTERNS)


def detect_security_implications(files: Sequence[str]) -> bool:
    """Detect whether any changed file matches upstream security patterns."""

    return any(pattern.search(file) for file in files for pattern in _SECURITY_PATTERNS)


def build_change_metadata(
    files: Sequence[str],
    lines_changed: int,
    test_coverage: TestCoverage = "partial",
) -> ChangeMetadata:
    """Build metadata from changed paths and a line-count delta."""

    return ChangeMetadata(
        files_changed=len(files),
        lines_changed=lines_changed,
        has_architectural_changes=detect_architectural_changes(files),
        has_security_implications=detect_security_implications(files),
        test_coverage=test_coverage,
    )


__all__ = [
    "ChangeMetadata",
    "TIER_AGENTS",
    "TestCoverage",
    "VerificationAgent",
    "VerificationTier",
    "build_change_metadata",
    "detect_architectural_changes",
    "detect_security_implications",
    "get_verification_agent",
    "select_verification_tier",
]
