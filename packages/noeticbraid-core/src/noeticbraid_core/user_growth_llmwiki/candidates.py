"""Growth-facing candidate generation for the LLMwiki mirror module."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Iterable, Optional

from noeticbraid_core.schemas._common import ensure_utc_datetime, utc_now

from .models import (
    DigestionCandidate,
    GrowthReportInput,
    LLMWikiSourceRecord,
    NoteType,
    OrphanCluster,
    RiskFlag,
    SideNoteCandidate,
    StructureSuggestion,
    VaultProfile,
    normalize_relative_path,
    stable_id,
)


def generate_structure_suggestions(
    profile: VaultProfile,
    *,
    created_at: Optional[datetime] = None,
    source_refs: Optional[Iterable[str]] = None,
    materialized_source_records: Optional[list[LLMWikiSourceRecord]] = None,
) -> list[StructureSuggestion]:
    """Translate scanner risks into deterministic, candidate-only structure actions."""

    timestamp = ensure_utc_datetime(created_at or utc_now())
    refs = _normalize_source_refs(source_refs)
    if not refs:
        profile_record = vault_profile_source_record(profile, ingested_at=timestamp)
        refs = [profile_record.record_id]
        if materialized_source_records is not None and all(
            record.record_id != profile_record.record_id for record in materialized_source_records
        ):
            materialized_source_records.append(profile_record)
    suggestions: list[StructureSuggestion] = []
    for risk in profile.risk_flags:
        action = _action_for_risk(risk)
        if action is None:
            continue
        target_path = _target_path_for_risk(risk, action)
        evidence = _risk_evidence_paths(risk)
        suggestions.append(
            StructureSuggestion(
                suggestion_id=stable_id("suggestion_", risk.code, target_path, *evidence),
                severity=risk.severity,
                target_path=target_path,
                action_type=action,
                rationale=_rationale_for_risk(risk, action),
                source_refs=refs,
                evidence_paths=evidence,
                confidence="medium" if risk.severity != "strong" else "high",
                owner="noeticbraid",
                status="candidate",
                created_at=timestamp,
                proposed_markdown=_proposed_markdown_for_risk(risk, action, evidence),
            )
        )
    return sorted(suggestions, key=lambda item: (item.target_path, item.action_type, item.suggestion_id))


def vault_profile_source_record(
    profile: VaultProfile,
    *,
    ingested_at: Optional[datetime] = None,
) -> LLMWikiSourceRecord:
    """Materialize the profile snapshot as a raw/source provenance record."""

    snapshot_json = profile.to_deterministic_json()
    content_hash = "sha256:" + hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
    return LLMWikiSourceRecord(
        record_id=profile.profile_source_ref(),
        origin=f"vault_profile:{profile.vault_root_hash}",
        content_hash=content_hash,
        layer="source",
        ingested_at=ensure_utc_datetime(ingested_at or utc_now()),
        relative_path=None,
        title="VaultProfile structural snapshot",
        provenance={"vault_root_hash": profile.vault_root_hash},
        owner="noeticbraid",
    )


def generate_side_note_candidates(
    profile: VaultProfile,
    source_records: Iterable[LLMWikiSourceRecord] = (),
    *,
    created_at: Optional[datetime] = None,
) -> list[SideNoteCandidate]:
    """Create evidence-bound side-note candidates from structural evidence only."""

    timestamp = ensure_utc_datetime(created_at or utc_now())
    refs = _source_refs_for_profile(profile, source_records)
    candidates: list[SideNoteCandidate] = []

    for zone in sorted(profile.raw_user_zones):
        evidence = [zone]
        claim = f"Fact: {zone} is profiled as a raw-user zone by path/config/frontmatter evidence."
        candidates.append(_side_note("fact", claim, evidence, refs, timestamp, confidence="high"))

    for orphan in sorted(profile.orphan_clusters, key=lambda item: (item.path, item.topic)):
        evidence = list(orphan.evidence_paths)
        claim = (
            f"Hypothesis: {orphan.path} may benefit from an index or linking pass because "
            f"{orphan.note_count} notes have no detected internal links."
        )
        candidates.append(_side_note("hypothesis", claim, evidence, refs, timestamp, confidence="medium"))

    for risk in sorted(profile.risk_flags, key=lambda item: (item.path, item.code)):
        evidence = _risk_evidence_paths(risk)
        if risk.code == "ambiguous_ai_zone":
            claim = (
                f"Challenge: {risk.path} looks AI-related by name but lacks explicit AI-allowed zone evidence; "
                "review before any writer handoff."
            )
            candidates.append(_side_note("challenge", claim, evidence, refs, timestamp, confidence="medium"))
        elif risk.code in {"missing_index", "missing_project_index"}:
            claim = f"Action: review an _index.md candidate for {risk.path} before any vault write."
            candidates.append(_side_note("action", claim, evidence, refs, timestamp, confidence="medium"))
        elif risk.code == "missing_frontmatter_template":
            claim = f"Action: consider a frontmatter template candidate for {risk.path}; do not auto-tag user notes."
            candidates.append(_side_note("action", claim, evidence, refs, timestamp, confidence="medium"))

    return _dedupe_side_notes(candidates)


def generate_digestion_candidates(
    side_notes: Iterable[SideNoteCandidate],
    *,
    created_at: Optional[datetime] = None,
) -> list[DigestionCandidate]:
    """Create open digestion candidates linked to side-note candidates."""

    timestamp = ensure_utc_datetime(created_at or utc_now())
    result: list[DigestionCandidate] = []
    for note in sorted(side_notes, key=lambda item: item.candidate_id):
        result.append(
            DigestionCandidate(
                digestion_id=stable_id("digestion_", note.candidate_id, *note.evidence_refs),
                side_note_candidate_id=note.candidate_id,
                source_refs=list(note.source_refs),
                evidence_refs=list(note.evidence_refs),
                c_status="c0",
                status="open",
                confidence=note.confidence,
                owner="noeticbraid",
                created_at=timestamp,
                next_review_at=None,
            )
        )
    return result


def build_growth_report_input(
    period: str,
    side_notes: Iterable[SideNoteCandidate],
    digestion_candidates: Iterable[DigestionCandidate],
    *,
    created_at: Optional[datetime] = None,
    source_refs: Optional[Iterable[str]] = None,
) -> GrowthReportInput:
    """Group candidates for daily, weekly, or monthly report assembly."""

    if period not in {"daily", "weekly", "monthly"}:
        raise ValueError("period must be daily, weekly, or monthly")
    timestamp = ensure_utc_datetime(created_at or utc_now())
    grouped: dict[NoteType, list[SideNoteCandidate]] = defaultdict(list)
    ordered_notes = sorted(side_notes, key=lambda item: item.candidate_id)
    for note in ordered_notes:
        grouped[note.note_type].append(note)
    digestion_refs = sorted({candidate.digestion_id for candidate in digestion_candidates})
    refs = _normalize_source_refs(source_refs)
    if not refs:
        refs = sorted({ref for note in ordered_notes for ref in note.source_refs})
    if not refs:
        raise ValueError("report input requires at least one source ref")
    return GrowthReportInput(
        report_input_id=stable_id("report_input_", period, timestamp.isoformat(), *[note.candidate_id for note in ordered_notes]),
        period=period,
        facts=grouped["fact"],
        hypotheses=grouped["hypothesis"],
        challenges=grouped["challenge"],
        actions=grouped["action"],
        digestion_refs=digestion_refs,
        source_refs=refs,
        owner="noeticbraid",
        status="candidate",
        created_at=timestamp,
    )


def build_report_inputs(
    side_notes: Iterable[SideNoteCandidate],
    digestion_candidates: Iterable[DigestionCandidate],
    *,
    created_at: Optional[datetime] = None,
    periods: Iterable[str] = ("daily", "weekly", "monthly"),
    source_refs: Optional[Iterable[str]] = None,
) -> list[GrowthReportInput]:
    """Build deterministic report inputs for the requested periods."""

    notes = list(side_notes)
    digestion = list(digestion_candidates)
    return [
        build_growth_report_input(
            period,
            notes,
            digestion,
            created_at=created_at,
            source_refs=source_refs,
        )
        for period in periods
    ]


def _side_note(
    note_type: NoteType,
    claim: str,
    evidence_refs: list[str],
    source_refs: list[str],
    created_at: datetime,
    *,
    confidence: str,
) -> SideNoteCandidate:
    return SideNoteCandidate(
        candidate_id=stable_id("note_", note_type, claim, *evidence_refs),
        note_type=note_type,
        claim=claim,
        evidence_refs=evidence_refs,
        source_refs=source_refs,
        confidence=confidence,
        strength="normal",
        owner="noeticbraid",
        status="unread",
        created_at=created_at,
    )


def _dedupe_side_notes(candidates: list[SideNoteCandidate]) -> list[SideNoteCandidate]:
    by_id: dict[str, SideNoteCandidate] = {}
    for candidate in candidates:
        by_id[candidate.candidate_id] = candidate
    return sorted(by_id.values(), key=lambda item: (item.note_type, item.candidate_id))


def _source_refs_for_profile(
    profile: VaultProfile,
    source_records: Iterable[LLMWikiSourceRecord],
) -> list[str]:
    refs = _normalize_source_refs(record.record_id for record in source_records)
    if refs:
        return refs
    return [vault_profile_source_record(profile).record_id]


def _normalize_source_refs(source_refs: Optional[Iterable[str]]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for ref in source_refs or []:
        text = str(ref).strip()
        if not text:
            continue
        if not text.startswith("source_"):
            raise ValueError("source refs must use source_ identifiers")
        if text not in seen:
            refs.append(text)
            seen.add(text)
    return refs


def _action_for_risk(risk: RiskFlag) -> str | None:
    if risk.code in {"missing_index", "missing_project_index", "orphan_cluster"}:
        return "create_index"
    if risk.code == "missing_frontmatter_template":
        return "add_frontmatter_template"
    if risk.code == "ambiguous_ai_zone":
        return "split_ai_zone"
    return None


def _target_path_for_risk(risk: RiskFlag, action: str) -> str:
    if action == "create_index":
        folder = normalize_relative_path(risk.path, directory=risk.path != ".")
        return f"{folder}_index.md" if folder != "." else "_index.md"
    if action == "add_frontmatter_template":
        folder = normalize_relative_path(risk.path, directory=risk.path != ".")
        return f"{folder}.frontmatter_template.md" if folder != "." else ".frontmatter_template.md"
    return normalize_relative_path(risk.path, allow_dot=False)


def _risk_evidence_paths(risk: RiskFlag) -> list[str]:
    evidence = list(risk.evidence_paths) or [risk.path]
    return sorted(dict.fromkeys(evidence))


def _rationale_for_risk(risk: RiskFlag, action: str) -> str:
    suffix = " Final writes must go through the existing Obsidian writer boundary after review."
    if action == "create_index":
        return f"{risk.rationale} Propose an index candidate only; do not create or edit user notes.{suffix}"
    if action == "add_frontmatter_template":
        return f"{risk.rationale} Propose a template candidate only; do not auto-tag existing notes.{suffix}"
    if action == "split_ai_zone":
        return f"{risk.rationale} Propose explicit zone review only; do not infer AI write permission.{suffix}"
    return risk.rationale + suffix


def _proposed_markdown_for_risk(risk: RiskFlag, action: str, evidence: list[str]) -> str:
    evidence_lines = "\n".join(f"- {path}" for path in evidence)
    if action == "create_index":
        return (
            "---\n"
            "hm_type: structure_candidate\n"
            "hm_owner: noeticbraid\n"
            "hm_status: candidate\n"
            "---\n\n"
            f"# Index candidate for {risk.path}\n\n"
            "Candidate only. Review before any writer handoff.\n\n"
            "## Evidence paths\n"
            f"{evidence_lines}\n"
        )
    if action == "add_frontmatter_template":
        return (
            "---\n"
            "hm_type: structure_candidate\n"
            "hm_owner: noeticbraid\n"
            "hm_status: candidate\n"
            "---\n\n"
            f"# Frontmatter template candidate for {risk.path}\n\n"
            "Do not rewrite existing user notes. Use only as a reviewed template proposal.\n\n"
            "## Evidence paths\n"
            f"{evidence_lines}\n"
        )
    if action == "split_ai_zone":
        return (
            "---\n"
            "hm_type: structure_candidate\n"
            "hm_owner: noeticbraid\n"
            "hm_status: candidate\n"
            "---\n\n"
            f"# AI zone review candidate for {risk.path}\n\n"
            "Clarify whether this folder is raw-user, AI-allowed, or mixed before any write handoff.\n\n"
            "## Evidence paths\n"
            f"{evidence_lines}\n"
        )
    return ""
