# SPDX-License-Identifier: Apache-2.0
"""Generated dashboard bodies for the Obsidian vault hub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MANUAL_NOTES_HEADING = "## Manual notes"


@dataclass(frozen=True)
class DashboardContext:
    """Minimal data needed to generate the main daily dashboard body."""

    date: str
    active_tasks: list[dict[str, Any]] = field(default_factory=list)
    digestion_items: list[dict[str, Any]] = field(default_factory=list)
    recent_runs: list[dict[str, Any]] = field(default_factory=list)


class DashboardGenerator:
    """Generate deterministic Markdown surfaces while preserving manual sections."""

    def generate_today(self, ctx: DashboardContext) -> str:
        lines = [
            f"# NoeticBraid Today - {ctx.date}",
            "",
            "## Active tasks",
            *_bullet_rows(ctx.active_tasks, "task_id", "status"),
            "",
            "## Digestion queue",
            *_bullet_rows(ctx.digestion_items, "digestion_id", "status"),
            "",
            "## Recent runs",
            *_bullet_rows(ctx.recent_runs, "run_id", "status"),
            "",
            MANUAL_NOTES_HEADING,
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"

    def generate_digestion_queue(self, items: list[dict[str, Any]]) -> str:
        lines = ["# Digestion Queue", "", *_bullet_rows(items, "digestion_id", "status"), "", MANUAL_NOTES_HEADING, ""]
        return "\n".join(lines).rstrip() + "\n"

    def generate_account_pool(self, pool_status: list[dict[str, Any]]) -> str:
        lines = ["# Account Pool", "", *_bullet_rows(pool_status, "alias", "status"), "", MANUAL_NOTES_HEADING, ""]
        return "\n".join(lines).rstrip() + "\n"

    def generate_this_week(self, records: list[dict[str, Any]], *, week_start: str) -> str:
        lines = [
            f"# NoeticBraid Week - {week_start}",
            "",
            "## Weekly records",
            *_mixed_record_rows(records),
            "",
            MANUAL_NOTES_HEADING,
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"


def preserve_manual_notes(generated_body: str, existing_body: str | None) -> str:
    """Merge generated body with an existing Manual notes section."""

    if not existing_body or MANUAL_NOTES_HEADING not in existing_body:
        return generated_body
    manual = existing_body[existing_body.index(MANUAL_NOTES_HEADING) :].rstrip()
    prefix = generated_body[: generated_body.index(MANUAL_NOTES_HEADING)].rstrip()
    return prefix + "\n\n" + manual + "\n"


def _bullet_rows(rows: list[dict[str, Any]], id_key: str, status_key: str) -> list[str]:
    if not rows:
        return ["- _none_"]
    rendered = []
    for row in rows:
        ident = row.get(id_key, "unknown")
        status = row.get(status_key, "unknown")
        title = row.get("title")
        suffix = f" - {title}" if title else ""
        rendered.append(f"- `{ident}` [{status}]{suffix}")
    return rendered


def _mixed_record_rows(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["- _none_"]
    rows: list[str] = []
    for record in records:
        ident = record.get("task_id") or record.get("run_id") or record.get("digestion_id") or "unknown"
        status = record.get("status", "unknown")
        title = record.get("title")
        suffix = f" - {title}" if title else ""
        rows.append(f"- `{ident}` [{status}]{suffix}")
    return rows
