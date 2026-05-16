# SPDX-License-Identifier: Apache-2.0
"""Approval one-way-door classifier ported from gstack."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence


class DoorType(StrEnum):
    """Safety classification declared by an approval definition."""

    ONE_WAY = "one-way"
    TWO_WAY = "two-way"


QuestionCategory = str
StandardOption = str
ClassificationReason = str


@dataclass(frozen=True)
class ApprovalDefinition:
    """Stable registry entry for an approval/clarification question."""

    id: str
    skill: str
    category: QuestionCategory
    door_type: DoorType
    description: str
    options: tuple[StandardOption, ...] = field(default_factory=tuple)
    signal_key: str | None = None


@dataclass(frozen=True)
class ApprovalClassification:
    """Result of classifying an approval request."""

    one_way: bool
    reason: ClassificationReason
    matched: str | None = None
    definition_id: str | None = None


_DESTRUCTIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\bdelete\b", re.I),
    re.compile(r"\bremove\s+(directory|folder|files?)\b", re.I),
    re.compile(r"\bwipe\b", re.I),
    re.compile(r"\bpurge\b", re.I),
    re.compile(r"\btruncate\b", re.I),
    re.compile(r"\bdrop\s+(table|database|schema|index|column)\b", re.I),
    re.compile(r"\bdelete\s+from\b", re.I),
    re.compile(r"\bforce[- ]push\b", re.I),
    re.compile(r"\bpush\s+--force\b", re.I),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
    re.compile(r"\bcheckout\s+--\b", re.I),
    re.compile(r"\brestore\s+\.\b", re.I),
    re.compile(r"\bclean\s+-f\b", re.I),
    re.compile(r"\bbranch\s+-D\b", re.I),
    re.compile(r"\bkubectl\s+delete\b", re.I),
    re.compile(r"\bterraform\s+destroy\b", re.I),
    re.compile(r"\brollback\b", re.I),
    re.compile(r"\brevoke\s+[\w\s]*\b(api key|token|credential|access key|password)\b", re.I),
    re.compile(r"\breset\s+[\w\s]*\b(api key|token|password|credential)\b", re.I),
    re.compile(r"\brotate\s+[\w\s]*\b(api key|token|secret|credential|access key)\b", re.I),
    re.compile(r"\barchitectur(e|al)\s+(change|fork|shift|decision)\b", re.I),
    re.compile(r"\bdata\s+model\s+change\b", re.I),
    re.compile(r"\bschema\s+migration\b", re.I),
    re.compile(r"\bbreaking\s+change\b", re.I),
)
_ONE_WAY_SKILL_CATEGORIES: frozenset[str] = frozenset(
    {
        "cso:approval",
        "land-and-deploy:approval",
    }
)


def _normalize_definition(value: ApprovalDefinition | Mapping[str, object]) -> ApprovalDefinition:
    if isinstance(value, ApprovalDefinition):
        return value
    options_raw = value.get("options", ())
    options: tuple[str, ...]
    if isinstance(options_raw, Sequence) and not isinstance(options_raw, str):
        options = tuple(str(item) for item in options_raw)
    else:
        options = ()
    return ApprovalDefinition(
        id=str(value["id"]),
        skill=str(value["skill"]),
        category=str(value["category"]),
        door_type=DoorType(str(value["door_type"])),
        description=str(value.get("description", "")),
        options=options,
        signal_key=str(value["signal_key"]) if value.get("signal_key") is not None else None,
    )


def classify_approval(
    *,
    question_id: str | None = None,
    skill: str | None = None,
    category: str | None = None,
    summary: str | None = None,
    registry: Mapping[str, ApprovalDefinition | Mapping[str, object]] | None = None,
    definition: ApprovalDefinition | Mapping[str, object] | None = None,
) -> ApprovalClassification:
    """Classify an approval as one-way or two-way.

    Registry/definition door_type is primary; skill-category and destructive
    keyword matches are conservative fallbacks for ad-hoc approvals.
    """

    registered = definition
    if registered is None and question_id and registry:
        registered = registry.get(question_id)
    if registered is not None:
        resolved = _normalize_definition(registered)
        return ApprovalClassification(
            one_way=resolved.door_type == DoorType.ONE_WAY,
            reason="registry",
            definition_id=resolved.id,
        )

    if skill and category and f"{skill}:{category}" in _ONE_WAY_SKILL_CATEGORIES:
        return ApprovalClassification(one_way=True, reason="skill-category")

    if summary:
        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(summary):
                return ApprovalClassification(
                    one_way=True,
                    reason="keyword",
                    matched=pattern.pattern,
                )

    return ApprovalClassification(one_way=False, reason="default-two-way")


def is_one_way_door(**kwargs: object) -> bool:
    """Convenience wrapper returning only the boolean classification."""

    return classify_approval(**kwargs).one_way


DESTRUCTIVE_PATTERN_LIST = _DESTRUCTIVE_PATTERNS
ONE_WAY_SKILL_CATEGORY_SET = _ONE_WAY_SKILL_CATEGORIES

__all__ = [
    "DESTRUCTIVE_PATTERN_LIST",
    "ONE_WAY_SKILL_CATEGORY_SET",
    "ApprovalClassification",
    "ApprovalDefinition",
    "ClassificationReason",
    "DoorType",
    "QuestionCategory",
    "StandardOption",
    "classify_approval",
    "is_one_way_door",
]
