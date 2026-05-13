"""Parse provider markdown artifacts into D2-01 debate round inputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .candidate_store import CandidateStoreError, scan_forbidden_material

JSON_BLOCK_RE = re.compile(r"```json\s*(?P<body>.*?)\s*```", re.DOTALL)
PROVIDER_TO_ROUND_POSITION = {
    "claude": 0,
    "codex": 1,
    "gemini": 2,
}
PROVIDER_TO_ROLE = {
    "claude": "producer",
    "codex": "adversary",
    "gemini": "source_auditor",
}
ROLE_TO_ROUND_TYPE = {
    "producer": "production",
    "adversary": "adversarial_review",
    "source_auditor": "review",
}
REQUIRED_PAYLOAD_KEYS = {"objections", "recommendation", "summary"}
REQUIRED_OBJECTION_KEYS = {"objection_id", "severity", "status", "summary", "evidence_refs"}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_STATUSES = {"raised", "unresolved", "needs_user_decision", "accepted", "rejected"}


class ProviderRoundParseError(ValueError):
    """Raised when provider markdown cannot become a structured debate round."""

    def __init__(self, reason: str, artifact_path: Path, provider: str | None = None) -> None:
        self.reason = reason
        self.artifact_path = artifact_path
        self.provider = provider
        prefix = f"{provider}:" if provider else ""
        super().__init__(f"{prefix}{reason}: {artifact_path}")


def _stable_hash(*parts: object, length: int = 12) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _slug(value: object, *, default: str = "item", max_length: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not slug:
        slug = f"{default}_{_stable_hash(value)}"
    if len(slug) > max_length:
        slug = f"{slug[: max_length - 13].rstrip('_')}_{_stable_hash(slug)}"
    return slug


def _prefixed(prefix: str, value: object, *, default: str = "item", max_length: int = 128) -> str:
    slug = _slug(value, default=default, max_length=max_length - len(prefix) - 1)
    candidate = slug if slug.startswith(prefix + "_") else f"{prefix}_{slug}"
    if len(candidate) > max_length:
        candidate = f"{candidate[: max_length - 13].rstrip('_')}_{_stable_hash(candidate)}"
    return candidate


def _source_refs(task_card: dict[str, Any], artifact_path: Path) -> list[str]:
    refs = task_card.get("source_refs") or task_card.get("sp_h_source_refs") or []
    if not isinstance(refs, list):
        raise ProviderRoundParseError("invalid_source_refs", artifact_path)
    normalized = [str(ref) for ref in refs] or ["source_task_card"]
    for ref in normalized:
        if not re.fullmatch(r"source_[A-Za-z0-9_]+", ref):
            raise ProviderRoundParseError(f"invalid_source_ref:{ref}", artifact_path)
    return list(dict.fromkeys(normalized))


def _loads_last_json_block(text: str, artifact_path: Path, provider: str) -> dict[str, Any]:
    matches = list(JSON_BLOCK_RE.finditer(text))
    if not matches:
        raise ProviderRoundParseError("no_json_block", artifact_path, provider)
    body = matches[-1].group("body")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderRoundParseError("invalid_json", artifact_path, provider) from exc
    if not isinstance(payload, dict):
        raise ProviderRoundParseError("json_not_object", artifact_path, provider)
    return payload


def _validate_payload(payload: dict[str, Any], artifact_path: Path, provider: str) -> None:
    for key in sorted(REQUIRED_PAYLOAD_KEYS):
        if key not in payload:
            raise ProviderRoundParseError(f"missing_key:{key}", artifact_path, provider)
    extra_keys = sorted(set(payload) - REQUIRED_PAYLOAD_KEYS)
    if extra_keys:
        raise ProviderRoundParseError(f"extra_key:{extra_keys[0]}", artifact_path, provider)
    if not isinstance(payload["objections"], list):
        raise ProviderRoundParseError("invalid_objections", artifact_path, provider)
    if not isinstance(payload["recommendation"], str):
        raise ProviderRoundParseError("invalid_recommendation", artifact_path, provider)
    if not isinstance(payload["summary"], str):
        raise ProviderRoundParseError("invalid_summary", artifact_path, provider)
    for index, objection in enumerate(payload["objections"]):
        _validate_objection(objection, index, artifact_path, provider)


def _validate_objection(objection: Any, index: int, artifact_path: Path, provider: str) -> None:
    if not isinstance(objection, dict):
        raise ProviderRoundParseError(f"invalid_objection:{index}", artifact_path, provider)
    for key in sorted(REQUIRED_OBJECTION_KEYS):
        if key not in objection:
            raise ProviderRoundParseError(f"missing_objection_key:{key}", artifact_path, provider)
    extra_keys = sorted(set(objection) - REQUIRED_OBJECTION_KEYS)
    if extra_keys:
        raise ProviderRoundParseError(f"extra_objection_key:{extra_keys[0]}", artifact_path, provider)
    if not isinstance(objection["objection_id"], str) or not re.fullmatch(r"obj_[A-Za-z0-9_]+", objection["objection_id"]):
        raise ProviderRoundParseError("invalid_objection_id", artifact_path, provider)
    if objection["severity"] not in ALLOWED_SEVERITIES:
        raise ProviderRoundParseError("invalid_severity", artifact_path, provider)
    if objection["status"] not in ALLOWED_STATUSES:
        raise ProviderRoundParseError("invalid_status", artifact_path, provider)
    if not isinstance(objection["summary"], str) or not objection["summary"].strip():
        raise ProviderRoundParseError("invalid_objection_summary", artifact_path, provider)
    if not isinstance(objection["evidence_refs"], list) or not all(isinstance(ref, str) for ref in objection["evidence_refs"]):
        raise ProviderRoundParseError("invalid_evidence_refs", artifact_path, provider)
    for ref in objection["evidence_refs"]:
        if not re.fullmatch(r"artifact_[A-Za-z0-9_]+", ref):
            raise ProviderRoundParseError("invalid_evidence_ref", artifact_path, provider)


def _round_verdict(objections: list[dict[str, Any]]) -> str:
    return "concern" if objections else "informational"


def parse_provider_artifact(
    artifact_path: Path,
    *,
    role: str,
    round_index: int,
    provider: str,
    model_ref: str,
    source_refs: list[str],
) -> dict[str, Any]:
    try:
        text = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProviderRoundParseError("missing_artifact", artifact_path, provider) from exc
    payload = _loads_last_json_block(text, artifact_path, provider)
    _validate_payload(payload, artifact_path, provider)
    artifact_ref = _prefixed("artifact", f"round_{round_index}_{provider}", default="artifact")
    objections = [dict(objection) for objection in payload["objections"]]
    round_record: dict[str, Any] = {
        "round_id": _prefixed("round", f"{role}_{round_index}", default="round"),
        "artifact_ref": artifact_ref,
        "role": role,
        "model_ref": model_ref,
        "source_refs": list(source_refs),
        "round_type": ROLE_TO_ROUND_TYPE.get(role, "review"),
        "verdict": _round_verdict(objections),
        "summary": payload["summary"],
        "recommendation": payload["recommendation"],
        "objections": objections,
    }
    try:
        scan_forbidden_material(round_record, f"provider_round:{provider}")
    except CandidateStoreError as exc:
        raise ProviderRoundParseError("forbidden_material", artifact_path, provider) from exc
    return round_record


def build_real_rounds(plan: dict[str, Any], task_card: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parsed_rounds: dict[int, dict[str, Any]] = {}
    provider_artifacts: dict[int, dict[str, Any]] = {}
    plans = plan.get("plans")
    if not isinstance(plans, list):
        raise ProviderRoundParseError("invalid_plan", Path(str(plan.get("artifact_root", "."))))

    for item in plans:
        if not isinstance(item, dict):
            raise ProviderRoundParseError("invalid_plan_item", Path(str(plan.get("artifact_root", "."))))
        provider = str(item.get("provider", ""))
        if provider not in PROVIDER_TO_ROUND_POSITION:
            raise ProviderRoundParseError(f"unknown_provider:{provider}", Path(str(item.get("artifact_path", plan.get("artifact_root", ".")))))
        artifact_path = Path(str(item.get("artifact_path", "")))
        round_index = PROVIDER_TO_ROUND_POSITION[provider]
        role = PROVIDER_TO_ROLE[provider]
        refs = _source_refs(task_card, artifact_path)
        round_record = parse_provider_artifact(
            artifact_path,
            role=role,
            round_index=round_index,
            provider=provider,
            model_ref=str(item.get("model_ref", "")),
            source_refs=refs,
        )
        parsed_rounds[round_index] = round_record
        provider_artifacts[round_index] = {
            "artifact_ref": round_record["artifact_ref"],
            "provider": provider,
            "model_ref": round_record["model_ref"],
            "role": round_record["role"],
            "summary": round_record["summary"],
            "source_refs": round_record["source_refs"],
        }

    ordered_positions = sorted(PROVIDER_TO_ROUND_POSITION.values())
    missing = [position for position in ordered_positions if position not in parsed_rounds]
    if missing:
        raise ProviderRoundParseError(f"missing_provider_position:{missing[0]}", Path(str(plan.get("artifact_root", "."))))
    return [parsed_rounds[position] for position in ordered_positions], [provider_artifacts[position] for position in ordered_positions]
