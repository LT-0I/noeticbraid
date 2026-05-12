# SPDX-License-Identifier: Apache-2.0
"""Markdown rendering for frozen Obsidian Hub 1.3.0 note wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import RenderError
from .frontmatter import render_markdown
from .resources import CONTRACT_VERSION, SCHEMA_VERSION, load_schema

SIDE_NOTE_CONTRACT_VERSION = "2.0.0"
SIDE_NOTE_TONE_CONSTRAINT = "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"
SIDE_NOTE_NOTE_TYPES = ("fact", "hypothesis", "action_suggestion")
SIDE_NOTE_USER_RESPONSES = ("unread", "accepted", "rejected", "modified")
SIDE_NOTE_RESPONSE_CHANNELS = ("accept", "rebut", "mark_inaccurate", "disable_this_type")


@dataclass(frozen=True)
class RenderedNote:
    """Rendered vault note in structured and text form."""

    frontmatter: dict[str, Any]
    body: str

    def to_markdown(self) -> str:
        return render_markdown(self.frontmatter, self.body)


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data or data[key] is None or data[key] == "":
        raise RenderError(f"missing required field {key}")
    return data[key]


def _tags(*values: str) -> list[str]:
    return list(dict.fromkeys(values))


def _schema_enum(schema_name: str, field_name: str) -> tuple[str, ...]:
    prop = load_schema(schema_name)["properties"][field_name]
    if "enum" in prop:
        return tuple(prop["enum"])
    values: list[str] = []
    for option in prop.get("anyOf", []):
        if isinstance(option, dict) and option.get("type") == "string" and "enum" in option:
            values.extend(option["enum"])
    return tuple(values)


def _validate_enum(value: Any, allowed: tuple[str, ...], field_name: str) -> Any:
    if value is None:
        return value
    if value not in allowed:
        raise RenderError(f"{field_name} must be one of {', '.join(allowed)}")
    return value


def _schema_enum_value(schema_name: str, field_name: str, value: Any) -> Any:
    return _validate_enum(value, _schema_enum(schema_name, field_name), field_name)


def _require_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = _require(data, key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise RenderError(f"{key} must be a non-empty list of strings")
    return value


def _require_exact_string(value: Any, expected: str, field_name: str) -> str:
    if value != expected:
        raise RenderError(f"{field_name} must exactly match the contract literal")
    return value


def _require_all_response_channels(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RenderError("user_response_channel must be a list of response actions")
    if len(set(value)) != len(value) or set(value) != set(SIDE_NOTE_RESPONSE_CHANNELS):
        raise RenderError("user_response_channel must include accept, rebut, mark_inaccurate, disable_this_type")
    return value


class MarkdownRenderer:
    """Render backend objects into portable Markdown notes with YAML frontmatter."""

    def render_dashboard(
        self,
        *,
        dashboard_id: str,
        title: str,
        date: str,
        generated_at: str,
        body: str,
        source_run_id: str | None = None,
    ) -> RenderedNote:
        return RenderedNote(
            {
                "nb_type": "dashboard",
                "schema_version": SCHEMA_VERSION,
                "contract_version": CONTRACT_VERSION,
                "dashboard_id": dashboard_id,
                "title": title,
                "date": date,
                "generated": True,
                "generated_at": generated_at,
                "tags": ["noeticbraid/dashboard"],
                "source_run_id": source_run_id,
            },
            body,
        )

    def render_task(self, task: dict[str, Any], *, body: str) -> RenderedNote:
        frontmatter = {
            "nb_type": "task",
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "task_id": _require(task, "task_id"),
            "task_type": _schema_enum_value("task_note", "task_type", _require(task, "task_type")),
            "risk_level": _schema_enum_value("task_note", "risk_level", _require(task, "risk_level")),
            "approval_level": _schema_enum_value("task_note", "approval_level", _require(task, "approval_level")),
            "status": _schema_enum_value("task_note", "status", _require(task, "status")),
            "source_channel": _schema_enum_value("task_note", "source_channel", _require(task, "source_channel")),
            "created_at": _require(task, "created_at"),
            "tags": _tags("noeticbraid/task", *task.get("tags", [])),
            "account_hint": task.get("account_hint"),
            "project_ref": task.get("project_ref"),
        }
        title = task.get("title") or frontmatter["task_id"]
        note_body = f"# {title}\n\n## Request\n{body.strip()}\n\n## Status Notes\n"
        return RenderedNote(frontmatter, note_body)

    def render_run_record(self, run: dict[str, Any], *, body: str) -> RenderedNote:
        frontmatter = {
            "nb_type": "run_record",
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "run_id": _require(run, "run_id"),
            "task_id": _require(run, "task_id"),
            "event_type": _schema_enum_value("run_record_note", "event_type", _require(run, "event_type")),
            "actor": _schema_enum_value("run_record_note", "actor", _require(run, "actor")),
            "status": _schema_enum_value("run_record_note", "status", _require(run, "status")),
            "created_at": _require(run, "created_at"),
            "tags": _tags("noeticbraid/run", *run.get("tags", [])),
            "model_refs": run.get("model_refs", []),
            "source_refs": run.get("source_refs", []),
            "artifact_refs": run.get("artifact_refs", []),
        }
        return RenderedNote(frontmatter, f"# Run {frontmatter['run_id']}\n\n{body.strip()}\n\n## Decision Notes\n")

    def render_source_record(self, source: dict[str, Any], *, body: str) -> RenderedNote:
        frontmatter = {
            "nb_type": "source_record",
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "source_ref_id": _require(source, "source_ref_id"),
            "source_type": _schema_enum_value("source_record_note", "source_type", _require(source, "source_type")),
            "title": _require(source, "title"),
            "captured_at": _require(source, "captured_at"),
            "quality_score": _schema_enum_value("source_record_note", "quality_score", _require(source, "quality_score")),
            "relevance_score": _schema_enum_value(
                "source_record_note", "relevance_score", _require(source, "relevance_score")
            ),
            "tags": _tags("noeticbraid/source", *source.get("tags", [])),
            "canonical_url": source.get("canonical_url"),
            "local_path": source.get("local_path"),
            "source_ref": source.get("source_ref"),
            "external_url": source.get("external_url"),
            "author": source.get("author"),
            "retrieved_by_run_id": source.get("retrieved_by_run_id"),
            "content_hash": source.get("content_hash"),
            "source_fingerprint": source.get("source_fingerprint"),
            "evidence_role": _schema_enum_value(
                "source_record_note", "evidence_role", source.get("evidence_role")
            ),
            "used_for_purpose": _schema_enum_value(
                "source_record_note", "used_for_purpose", source.get("used_for_purpose")
            ),
        }
        return RenderedNote(frontmatter, f"# {frontmatter['title']}\n\n{body.strip()}\n")

    def render_side_note(self, note: dict[str, Any], *, body: str) -> RenderedNote:
        linked_source_refs = _require_string_list(note, "linked_source_refs")
        evidence_source = _require_string_list(note, "evidence_source")
        if evidence_source != linked_source_refs:
            raise RenderError("evidence_source must match linked_source_refs")
        user_response_channel = _require_all_response_channels(
            _require(note, "user_response_channel")
        )
        frontmatter = {
            "nb_type": "side_note",
            "schema_version": SCHEMA_VERSION,
            "contract_version": SIDE_NOTE_CONTRACT_VERSION,
            "note_id": _require(note, "note_id"),
            "created_at": _require(note, "created_at"),
            "linked_source_refs": linked_source_refs,
            "evidence_source": evidence_source,
            "note_type": _validate_enum(_require(note, "note_type"), SIDE_NOTE_NOTE_TYPES, "note_type"),
            "confidence": _schema_enum_value("side_note", "confidence", _require(note, "confidence")),
            "tone_constraint": _require_exact_string(
                _require(note, "tone_constraint"),
                SIDE_NOTE_TONE_CONSTRAINT,
                "tone_constraint",
            ),
            "user_response_channel": user_response_channel,
            "user_response": _validate_enum(
                _require(note, "user_response"), SIDE_NOTE_USER_RESPONSES, "user_response"
            ),
            "tags": _tags("noeticbraid/side-note", *note.get("tags", [])),
            "follow_up_ref": note.get("follow_up_ref"),
            "project_ref": note.get("project_ref"),
        }
        metadata_body = (
            f"# Side note {frontmatter['note_id']}\n\n"
            f"{body.strip()}\n\n"
            "## Safety metadata\n"
            f"- evidence_source: {', '.join(evidence_source)}\n"
            f"- note_type: {frontmatter['note_type']}\n"
            f"- confidence: {frontmatter['confidence']}\n"
            f"- tone_constraint: {SIDE_NOTE_TONE_CONSTRAINT}\n"
            f"- user_response_channel: {', '.join(user_response_channel)}\n\n"
            "## User response options\n"
            "- accept\n"
            "- rebut\n"
            "- mark_inaccurate\n"
            "- 可关闭此类旁注 / disable_this_type\n\n"
            "## Decision Notes\n"
        )
        return RenderedNote(frontmatter, metadata_body)

    def render_digestion_item(self, item: dict[str, Any], *, body: str) -> RenderedNote:
        frontmatter = {
            "nb_type": "digestion_item",
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "digestion_id": _require(item, "digestion_id"),
            "side_note_id": _require(item, "side_note_id"),
            "created_at": _require(item, "created_at"),
            "c_status": _schema_enum_value("digestion_item", "c_status", _require(item, "c_status")),
            "status": _schema_enum_value("digestion_item", "status", _require(item, "status")),
            "tags": _tags("noeticbraid/digestion", *item.get("tags", [])),
            "user_response_ref": item.get("user_response_ref"),
            "next_review_at": item.get("next_review_at"),
        }
        return RenderedNote(frontmatter, f"# Digestion {frontmatter['digestion_id']}\n\n{body.strip()}\n")
