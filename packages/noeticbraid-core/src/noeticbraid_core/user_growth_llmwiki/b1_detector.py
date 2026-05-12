"""SDD-D1-02 b-1 detector implementation.

Detects confirmed projects that were mentioned on at least three distinct days
inside a shared 14-day sliding window while showing no progress signals. Output
is candidate-only JSON; the detector never writes Obsidian vault files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from noeticbraid_core.schemas.side_note import SideNote, TONE_CONSTRAINT_LITERAL, USER_RESPONSE_CHANNEL_VALUES

from .mention_scanner import ProjectMention, scan_mentions
from .progress_detector import ProgressCheckResult, candidate_queue_path, progress_checks
from .tracked_project import ProjectCandidate, auto_discover, load_registry, normalize_project_ref

DETECTOR_POLICY_VERSION = "b1_detector_v1"
WINDOW_DAYS = 14
TRIGGER_THRESHOLD = 3


class CandidateB1SideNote(BaseModel):
    """Candidate queue shape for a b-1 SideNote candidate."""

    candidate_type: Literal["b1_sidenote"] = "b1_sidenote"
    candidate_id: str = Field(..., pattern=r"^note_[A-Za-z0-9_]+$", max_length=128)
    project_ref: str = Field(..., min_length=1, max_length=1024)
    window_id: str = Field(..., min_length=1, max_length=128)
    detector_policy_version: Literal["b1_detector_v1"] = DETECTOR_POLICY_VERSION
    evidence_source: list[str] = Field(..., min_length=1, max_length=100)
    note_type: Literal["hypothesis", "action_suggestion"] = "hypothesis"
    claim: str = Field(..., min_length=1, max_length=4096)
    confidence: Literal["low", "medium", "high"] = "medium"
    tone_constraint: Literal["不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"] = TONE_CONSTRAINT_LITERAL
    user_response_channel: list[Literal["accept", "rebut", "mark_inaccurate", "disable_this_type"]] = Field(
        default_factory=lambda: list(USER_RESPONSE_CHANNEL_VALUES)
    )
    user_response: Literal["unread", "accepted", "rejected", "modified"] = "unread"
    created_at: str
    mention_count_same_day_dedup: int = Field(..., ge=TRIGGER_THRESHOLD)
    progress_checks: dict[str, bool]
    cooldown_decision: Literal["not_existing_in_window"] = "not_existing_in_window"
    source_refs_only: Literal[True] = True

    @field_validator("evidence_source")
    @classmethod
    def _path_line_refs_only(cls, values: list[str]) -> list[str]:
        clean: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or "\n" in text or not text.rsplit(":", 1)[-1].isdigit():
                raise ValueError("evidence_source must contain only path:line refs")
            clean.append(text)
        return clean

    @field_validator("user_response_channel")
    @classmethod
    def _all_response_channels(cls, values: list[str]) -> list[str]:
        if set(values) != set(USER_RESPONSE_CHANNEL_VALUES) or len(values) != len(USER_RESPONSE_CHANNEL_VALUES):
            raise ValueError("user_response_channel must include all four SideNote response actions")
        return values

    def to_sidenote(
        self,
        note_id: str,
        *,
        claim: str | None = None,
        created_at: str | datetime | None = None,
        user_response: Literal["unread", "accepted", "rejected", "modified"] | None = None,
        follow_up_ref: str | None = None,
    ) -> SideNote:
        """Schema-level transformer from an in-memory b-1 candidate to ``SideNote``.

        This method performs schema conversion only. It does not write vault
        markdown or materialize backing source records; callers own ``note_id``
        derivation and any later materialization step.
        """

        return SideNote(
            note_id=note_id,
            created_at=created_at if created_at is not None else self.created_at,
            evidence_source=self.evidence_source,
            linked_source_refs=self.evidence_source,
            note_type=self.note_type,
            claim=claim if claim is not None else self.claim,
            confidence=self.confidence,
            user_response=user_response if user_response is not None else self.user_response,
            tone_constraint=self.tone_constraint,
            user_response_channel=self.user_response_channel,
            follow_up_ref=follow_up_ref,
        )


@dataclass(frozen=True)
class B1DetectorReport:
    candidates: list[CandidateB1SideNote]
    skip_reasons: dict[str, str] = field(default_factory=dict)
    discovered_candidates: list[str] = field(default_factory=list)
    queue_path: str | None = None

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def run_b1_detector(vault_path: str | Path, run_timestamp_utc: datetime | None = None) -> list[CandidateB1SideNote]:
    """Run the b-1 detector and return candidates written to the queue."""

    return run_b1_detector_with_report(vault_path, run_timestamp_utc=run_timestamp_utc).candidates


def run_b1_detector_with_report(vault_path: str | Path, run_timestamp_utc: datetime | None = None) -> B1DetectorReport:
    """Run the detector and include CLI-friendly skip/discovery metadata."""

    root = Path(vault_path)
    run_at = _ensure_utc(run_timestamp_utc or datetime.now(timezone.utc))
    window_start = run_at - timedelta(days=WINDOW_DAYS)
    window_id = _window_id(window_start, run_at)

    before_registry = load_registry()
    discovered: list[str] = []
    if not before_registry:
        discovered_items = auto_discover(root)
        discovered = [item.project_ref for item in discovered_items]
    projects = load_registry()
    confirmed = [item for item in projects if item.status == "confirmed"]

    skip_reasons: dict[str, str] = {}
    if not confirmed:
        for project in projects:
            skip_reasons[project.project_ref] = "not_confirmed"
        return B1DetectorReport([], skip_reasons, discovered, str(candidate_queue_path(root)))

    mentions = scan_mentions(root, confirmed, window_start=window_start)
    queue = candidate_queue_path(root)
    existing_rows = _read_queue(queue)
    new_candidates: list[CandidateB1SideNote] = []

    for project in sorted(confirmed, key=lambda item: item.project_ref.casefold()):
        project_mentions = mentions.get(project.project_ref, [])
        deduped = _same_day_dedup(project_mentions)
        if len(deduped) < TRIGGER_THRESHOLD:
            skip_reasons[project.project_ref] = f"below_threshold:{len(deduped)}/{TRIGGER_THRESHOLD}"
            continue
        checks = progress_checks(project.project_ref, window_start, root)
        if not checks.is_stagnant:
            skip_reasons[project.project_ref] = "not_stagnant:" + ",".join(
                key for key, value in checks.to_record().items() if value is False
            )
            continue
        if _has_cooldown(existing_rows, project.project_ref, window_start, run_at, window_id):
            skip_reasons[project.project_ref] = "cooldown"
            continue
        candidate = _build_candidate(project, deduped, checks, run_at, window_id)
        new_candidates.append(candidate)

    if new_candidates:
        _append_candidates(queue, new_candidates)
    return B1DetectorReport(new_candidates, skip_reasons, discovered, str(queue))


def _build_candidate(
    project: ProjectCandidate,
    mentions: list[ProjectMention],
    checks: ProgressCheckResult,
    run_at: datetime,
    window_id: str,
) -> CandidateB1SideNote:
    refs = [mention.source_ref for mention in mentions]
    candidate_id = _candidate_id(project.project_ref, window_id, refs)
    count = len(mentions)
    claim = (
        f"Hypothesis: 过去 14 天的笔记中有 {count} 个日期提到 {project.project_name}，"
        "但未记录项目文件更新、完成项或旁注回应变化；可检查是否需要保留、调整或暂停该项目。"
    )
    return CandidateB1SideNote(
        candidate_id=candidate_id,
        project_ref=project.project_ref,
        window_id=window_id,
        evidence_source=refs,
        note_type="hypothesis",
        claim=claim,
        confidence="medium" if count >= TRIGGER_THRESHOLD else "low",
        created_at=_iso(run_at),
        mention_count_same_day_dedup=count,
        progress_checks=checks.to_record(),
    )


def _same_day_dedup(mentions: list[ProjectMention]) -> list[ProjectMention]:
    by_day: dict[str, ProjectMention] = {}
    for mention in sorted(mentions, key=lambda item: (item.mention_date.isoformat(), item.path, item.line)):
        by_day.setdefault(mention.mention_date.isoformat(), mention)
    return [by_day[key] for key in sorted(by_day)]


def _has_cooldown(
    rows: list[dict[str, Any]],
    project_ref: str,
    window_start: datetime,
    run_at: datetime,
    window_id: str,
) -> bool:
    ref = normalize_project_ref(project_ref)
    for row in rows:
        if row.get("candidate_type") != "b1_sidenote":
            continue
        if normalize_project_ref(str(row.get("project_ref", ""))) != ref:
            continue
        if row.get("window_id") == window_id:
            return True
        created = _parse_datetime(row.get("created_at"))
        if created is not None and window_start <= created <= run_at:
            return True
    return False


def _read_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, dict)]


def _append_candidates(path: Path, candidates: list[CandidateB1SideNote]) -> None:
    rows = _read_queue(path)
    by_id: dict[str, dict[str, Any]] = {str(row.get("candidate_id")): row for row in rows if row.get("candidate_id")}
    for candidate in candidates:
        by_id[candidate.candidate_id] = candidate.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [by_id[key] for key in sorted(by_id)]
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_id(project_ref: str, window_id: str, refs: list[str]) -> str:
    h = hashlib.sha256()
    for part in [DETECTOR_POLICY_VERSION, project_ref, window_id, *refs]:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return "note_" + h.hexdigest()[:16]


def _window_id(window_start: datetime, run_at: datetime) -> str:
    return f"{window_start.date().isoformat()}..{run_at.date().isoformat()}"


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")
