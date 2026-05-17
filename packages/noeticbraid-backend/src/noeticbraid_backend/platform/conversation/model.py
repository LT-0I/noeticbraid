# SPDX-License-Identifier: Apache-2.0
"""Persistent Phase-1 conversational task model helpers."""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from noeticbraid_backend.platform.elicitation.capabilities import CapabilityEntry, capability_for
from noeticbraid_backend.platform.tasks.models import validate_task_id
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

REQUIREMENTS_FILENAME = "requirements.json"
CONVERSATION_FILENAME = "conversation.jsonl"
MEMORY_PROFILE_REL = "memory/profile.json"
REQUIREMENTS_SCHEMA_VERSION = 1
MEMORY_SCHEMA_VERSION = 1
VISIBLE_ROLES = frozenset({"user", "assistant"})
VISIBLE_KINDS = frozenset({"message", "question", "answer", "coarse_status"})
REQUIREMENT_STATES = frozenset({"pending", "in_progress", "done", "blocked"})
REQUIREMENT_STATUSES = frozenset({"eliciting", "confirmed"})
_REQUIREMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def now_ts() -> str:
    return datetime.now(UTC).isoformat()


def new_task_id() -> str:
    return f"task_conversation_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"


def requirements_path_for(account: str, task_id: str) -> Path:
    return resolve_user_path(account, f"tasks/{validate_task_id(task_id)}/{REQUIREMENTS_FILENAME}")


def conversation_path_for(account: str, task_id: str) -> Path:
    return resolve_user_path(account, f"tasks/{validate_task_id(task_id)}/{CONVERSATION_FILENAME}")


def memory_profile_path_for(account: str) -> Path:
    return resolve_user_path(account, MEMORY_PROFILE_REL)


def empty_requirements(task_id: str, *, status: str = "eliciting") -> dict[str, Any]:
    validate_task_id(task_id)
    if status not in REQUIREMENT_STATUSES:
        raise ValueError("invalid requirements status")
    return {
        "task_id": task_id,
        "schema_version": REQUIREMENTS_SCHEMA_VERSION,
        "status": status,
        "requirements": [],
    }


def initialize_task_files(account: str, task_id: str) -> None:
    write_requirements(account, task_id, empty_requirements(task_id))
    ensure_conversation_file(account, task_id)


def load_requirements(account: str, task_id: str) -> dict[str, Any]:
    path = requirements_path_for(account, task_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        legacy = empty_requirements(task_id, status="confirmed")
        legacy["legacy"] = True
        return legacy
    if not isinstance(payload, dict):
        raise ValueError("requirements must be an object")
    return validate_requirements_payload(payload, expected_task_id=task_id)


def validate_requirements_payload(payload: dict[str, Any], *, expected_task_id: str | None = None) -> dict[str, Any]:
    task_id = validate_task_id(str(payload["task_id"]))
    if expected_task_id is not None and task_id != validate_task_id(expected_task_id):
        raise ValueError("requirements task mismatch")
    if int(payload.get("schema_version")) != REQUIREMENTS_SCHEMA_VERSION:
        raise ValueError("unsupported requirements schema")
    status = str(payload["status"])
    if status not in REQUIREMENT_STATUSES:
        raise ValueError("invalid requirements status")
    requirements_raw = payload.get("requirements")
    if not isinstance(requirements_raw, list):
        raise ValueError("requirements must be a list")
    requirements = [validate_requirement_item(item) for item in requirements_raw]
    validated: dict[str, Any] = {
        "task_id": task_id,
        "schema_version": REQUIREMENTS_SCHEMA_VERSION,
        "status": status,
        "requirements": requirements,
    }
    confirmed_at = payload.get("confirmed_at")
    if confirmed_at is not None:
        if not isinstance(confirmed_at, str) or not confirmed_at:
            raise ValueError("confirmed_at must be a non-empty string")
        validated["confirmed_at"] = confirmed_at
    if payload.get("legacy") is True:
        validated["legacy"] = True
    return validated


def validate_requirement_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("requirement must be an object")
    req_id = str(item.get("id") or "").strip()
    if _REQUIREMENT_ID_RE.fullmatch(req_id) is None:
        raise ValueError("invalid requirement id")
    text = str(item.get("text") or "").strip()
    if not text:
        raise ValueError("requirement text must be non-empty")
    modality = str(item.get("modality") or "text").strip().lower()
    if not modality:
        modality = "text"
    capability_status = str(item.get("capability_status") or "supported")
    if capability_status not in {"supported", "unavailable", "deferred"}:
        raise ValueError("invalid capability status")
    coarse_state = str(item.get("coarse_state") or "pending")
    if coarse_state not in REQUIREMENT_STATES:
        raise ValueError("invalid coarse state")
    validated: dict[str, Any] = {
        "id": req_id,
        "text": text,
        "modality": modality,
        "capability_status": capability_status,
        "coarse_state": coarse_state,
    }
    blocked_reason = item.get("blocked_reason")
    if blocked_reason is not None:
        reason = str(blocked_reason).strip()
        if reason:
            validated["blocked_reason"] = reason
    return validated


def write_requirements(account: str, task_id: str, payload: dict[str, Any]) -> None:
    path = requirements_path_for(account, task_id)
    validated = validate_requirements_payload(payload, expected_task_id=task_id)
    _atomic_write_json(path, validated)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        parsed = json.loads(temp_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("atomic payload must be an object")
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def ensure_conversation_file(account: str, task_id: str) -> None:
    path = conversation_path_for(account, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.close(descriptor)
    path.chmod(0o600)


def append_conversation_row(
    account: str,
    task_id: str,
    *,
    role: str,
    kind: str,
    text: str,
    requirement_id: str | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    row = conversation_row(role=role, kind=kind, text=text, requirement_id=requirement_id, ts=ts)
    path = conversation_path_for(account, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    json.loads(line)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return row


def conversation_row(
    *,
    role: str,
    kind: str,
    text: str,
    requirement_id: str | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    if role not in VISIBLE_ROLES:
        raise ValueError("conversation role is not user-visible")
    if kind not in VISIBLE_KINDS:
        raise ValueError("conversation kind is not user-visible")
    body = str(text or "").strip()
    if not body:
        raise ValueError("conversation text must be non-empty")
    row: dict[str, Any] = {
        "ts": ts or now_ts(),
        "role": role,
        "kind": kind,
        "text": body,
    }
    if requirement_id is not None:
        req_id = str(requirement_id).strip()
        if _REQUIREMENT_ID_RE.fullmatch(req_id) is None:
            raise ValueError("invalid requirement id")
        row["requirement_id"] = req_id
    return row


def load_conversation(account: str, task_id: str) -> list[dict[str, Any]]:
    path = conversation_path_for(account, task_id)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("conversation row must be an object")
        rows.append(payload)
    return rows


def serialize_visible_conversation(account: str, task_id: str) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for row in load_conversation(account, task_id):
        role = row.get("role")
        kind = row.get("kind")
        text = row.get("text")
        ts = row.get("ts")
        if role not in VISIBLE_ROLES or kind not in VISIBLE_KINDS:
            continue
        if not isinstance(text, str) or not text:
            continue
        item: dict[str, Any] = {"ts": str(ts or ""), "role": role, "kind": kind, "text": text}
        requirement_id = row.get("requirement_id")
        if isinstance(requirement_id, str) and requirement_id:
            item["requirement_id"] = requirement_id
        visible.append(item)
    return visible


def candidate_requirements_from_probe(raw_requirement: str, probe: dict[str, Any]) -> list[dict[str, Any]]:
    raw_reqs = probe.get("requirements")
    if isinstance(raw_reqs, list) and raw_reqs:
        candidates = raw_reqs
    else:
        candidates = _requirements_from_interpretations(raw_requirement, probe.get("interpretations"))
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("deliverable") or raw_requirement).strip()
        if not text:
            continue
        modality = str(item.get("modality") or infer_modality(text)).strip().lower()
        req_id = str(item.get("id") or f"req_{index}").strip()
        if _REQUIREMENT_ID_RE.fullmatch(req_id) is None:
            req_id = f"req_{index}"
        normalized.append(
            {
                "id": req_id,
                "text": text,
                "modality": modality,
                "capability_status": "supported",
                "coarse_state": "pending",
            }
        )
    if normalized:
        return normalized
    return [
        {
            "id": "req_1",
            "text": str(raw_requirement).strip() or "Clarify the requested deliverable.",
            "modality": infer_modality(raw_requirement),
            "capability_status": "supported",
            "coarse_state": "pending",
        }
    ]


def _requirements_from_interpretations(raw_requirement: str, interpretations: Any) -> list[dict[str, Any]]:
    if not isinstance(interpretations, list):
        return []
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(interpretations, start=1):
        if not isinstance(item, dict):
            continue
        modality = str(item.get("modality") or infer_modality(str(item.get("deliverable") or raw_requirement))).strip().lower()
        deliverable = str(item.get("deliverable") or raw_requirement).strip()
        key = (modality, deliverable)
        if key in seen:
            continue
        seen.add(key)
        requirements.append({"id": f"req_{index}", "text": deliverable, "modality": modality})
    return requirements


def infer_modality(text: str) -> str:
    lowered = str(text or "").lower()
    checks = (
        ("image", ("image", "picture", "logo", "poster", "图像", "图片", "海报")),
        ("video", ("video", "mp4", "视频")),
        ("music", ("music", "song", "audio", "音乐", "歌曲")),
        ("slides", ("slides", "slide deck", "ppt", "pptx", "幻灯片")),
        ("code", ("code", "bug", "repo", "代码", "修复")),
        ("research", ("research", "analyze", "analysis", "调研", "研究", "分析")),
        ("document", ("document", "doc", "report", "brief", "文档", "报告")),
    )
    for modality, needles in checks:
        if any(needle in lowered for needle in needles):
            return modality
    return "text"


def questions_from_probe(raw_requirement: str, probe: dict[str, Any]) -> list[dict[str, str]]:
    raw_questions = probe.get("questions")
    questions: list[dict[str, str]] = []
    if isinstance(raw_questions, list):
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if not question:
                continue
            questions.append(
                {
                    "axis": str(item.get("axis") or "requirement").strip() or "requirement",
                    "question": question,
                    "suggested_answer": str(item.get("suggested_answer") or raw_requirement).strip(),
                }
            )
    if questions:
        return questions[:1]
    interpretations = probe.get("interpretations")
    if material_divergence(interpretations):
        return [
            {
                "axis": "deliverable_or_modality",
                "question": "I see multiple possible deliverables. Which modality and final output should I prioritize?",
                "suggested_answer": str(raw_requirement).strip()[:600],
            }
        ]
    return []


def material_divergence(interpretations: Any) -> bool:
    if not isinstance(interpretations, list) or len(interpretations) < 2:
        return False
    modalities: set[str] = set()
    deliverables: set[str] = set()
    for item in interpretations:
        if not isinstance(item, dict):
            continue
        modality = str(item.get("modality") or "").strip().lower()
        deliverable = str(item.get("deliverable") or "").strip().lower()
        if modality:
            modalities.add(modality)
        if deliverable:
            deliverables.add(deliverable)
    return len(modalities) > 1 or len(deliverables) > 1


def stamp_confirmed_requirements(task_id: str, requirements: Iterable[dict[str, Any]]) -> dict[str, Any]:
    stamped: list[dict[str, Any]] = []
    for index, item in enumerate(requirements, start=1):
        if not isinstance(item, dict):
            raise ValueError("requirement must be an object")
        req_id = str(item.get("id") or f"req_{index}").strip()
        if _REQUIREMENT_ID_RE.fullmatch(req_id) is None:
            raise ValueError("invalid requirement id")
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("requirement text must be non-empty")
        modality = str(item.get("modality") or infer_modality(text)).strip().lower()
        capability = capability_for(modality)
        stamped.append(_stamp_requirement(req_id, text, capability))
    return {
        "task_id": validate_task_id(task_id),
        "schema_version": REQUIREMENTS_SCHEMA_VERSION,
        "status": "confirmed",
        "requirements": stamped,
        "confirmed_at": now_ts(),
    }


def _stamp_requirement(req_id: str, text: str, capability: CapabilityEntry) -> dict[str, Any]:
    if capability.capability_status in {"unavailable", "deferred"}:
        return {
            "id": req_id,
            "text": text,
            "modality": capability.modality,
            "capability_status": capability.capability_status,
            "coarse_state": "blocked",
            "blocked_reason": capability.blocked_reason,
        }
    return {
        "id": req_id,
        "text": text,
        "modality": capability.modality,
        "capability_status": capability.capability_status,
        "coarse_state": "pending",
    }


def serialize_coarse_status(requirements_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in requirements_payload.get("requirements", []):
        if not isinstance(item, dict):
            continue
        row: dict[str, Any] = {
            "requirement_id": str(item.get("id") or ""),
            "text": str(item.get("text") or ""),
            "coarse_state": str(item.get("coarse_state") or "pending"),
            "capability_status": str(item.get("capability_status") or "supported"),
        }
        blocked_reason = item.get("blocked_reason")
        if isinstance(blocked_reason, str) and blocked_reason:
            row["blocked_reason"] = blocked_reason
        rows.append(row)
    return rows


def capability_notices(requirements_payload: dict[str, Any]) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in requirements_payload.get("requirements", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("capability_status") or "supported")
        if status not in {"unavailable", "deferred"}:
            continue
        modality = str(item.get("modality") or "text")
        if modality in seen:
            continue
        seen.add(modality)
        capability = capability_for(modality)
        notices.append(
            {
                "modality": capability.modality,
                "capability_status": capability.capability_status,
                "reason": capability.blocked_reason,
                "reason_zh": capability.reason_zh,
                "reason_en": capability.reason_en,
            }
        )
    return notices


def load_memory_profile(account: str) -> dict[str, Any] | None:
    path = memory_profile_path_for(account)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("schema_version", 0)) != MEMORY_SCHEMA_VERSION:
        return None
    prefs = payload.get("prefs")
    gaps = payload.get("declared_capability_gaps")
    if not isinstance(prefs, list) or not isinstance(gaps, list):
        return None
    return {"schema_version": MEMORY_SCHEMA_VERSION, "prefs": prefs, "declared_capability_gaps": gaps}


def persist_memory_from_confirm(account: str, requirements_payload: dict[str, Any], conversation: list[dict[str, Any]]) -> None:
    current = load_memory_profile(account) or {"schema_version": MEMORY_SCHEMA_VERSION, "prefs": [], "declared_capability_gaps": []}
    evidence = _latest_conversation_ref(conversation)
    prefs = list(current.get("prefs", []))
    gaps = list(current.get("declared_capability_gaps", []))
    gap_keys = {str(item.get("modality")) for item in gaps if isinstance(item, dict)}
    pref_by_key = {str(item.get("key")): item for item in prefs if isinstance(item, dict)}

    for item in requirements_payload.get("requirements", []):
        if not isinstance(item, dict):
            continue
        modality = str(item.get("modality") or "")
        status_value = str(item.get("capability_status") or "supported")
        if status_value in {"unavailable", "deferred"} and modality not in gap_keys:
            gaps.append(
                {
                    "modality": modality,
                    "capability_status": status_value,
                    "reason": str(item.get("blocked_reason") or ""),
                    "evidence_conversation_ref": evidence,
                }
            )
            gap_keys.add(modality)
        pref = _stable_pref_from_requirement(item, evidence)
        if pref is not None:
            pref_by_key[str(pref["key"])] = pref

    payload = {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "prefs": list(pref_by_key.values()),
        "declared_capability_gaps": gaps,
    }
    _atomic_write_json(memory_profile_path_for(account), payload)


def _latest_conversation_ref(conversation: list[dict[str, Any]]) -> str:
    for row in reversed(conversation):
        ts = row.get("ts")
        kind = row.get("kind")
        role = row.get("role")
        if isinstance(ts, str) and isinstance(kind, str) and isinstance(role, str):
            return f"{ts}:{role}:{kind}"
    return f"{now_ts()}:system:confirm"


def _stable_pref_from_requirement(item: dict[str, Any], evidence: str) -> dict[str, Any] | None:
    text = str(item.get("text") or "")
    lowered = text.lower()
    if not any(marker in lowered for marker in ("prefer", "always", "以后", "总是", "偏好")):
        return None
    req_id = str(item.get("id") or "unknown")
    return {
        "key": f"confirmed_preference:{req_id}",
        "value": text[:500],
        "confidence": 0.7,
        "evidence_conversation_ref": evidence,
    }


__all__ = [
    "CONVERSATION_FILENAME",
    "MEMORY_PROFILE_REL",
    "REQUIREMENTS_FILENAME",
    "append_conversation_row",
    "candidate_requirements_from_probe",
    "capability_notices",
    "conversation_path_for",
    "empty_requirements",
    "ensure_conversation_file",
    "initialize_task_files",
    "infer_modality",
    "load_conversation",
    "load_memory_profile",
    "load_requirements",
    "material_divergence",
    "new_task_id",
    "now_ts",
    "persist_memory_from_confirm",
    "questions_from_probe",
    "requirements_path_for",
    "serialize_coarse_status",
    "serialize_visible_conversation",
    "stamp_confirmed_requirements",
    "validate_requirement_item",
    "write_requirements",
]
