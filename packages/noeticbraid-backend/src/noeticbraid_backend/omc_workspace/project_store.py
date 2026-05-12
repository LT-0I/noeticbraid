# SPDX-License-Identifier: Apache-2.0
"""Fixture/state-backed OMC ingestion workspace store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from noeticbraid_core.schemas import CandidateLesson, WorkspaceProject

PROJECT_ID = "omc-ingest"
PROJECT_TITLE = "吸收 OMC"
DEFAULT_UPGRADE_RULE = (
    "explicit user adoption OR reuse >=3 times with at least one independently "
    "checkable ledger run; not rejected is never sufficient"
)


def _default_state() -> dict[str, Any]:
    return {
        "project": {
            "project_id": PROJECT_ID,
            "title": PROJECT_TITLE,
            "project_type": "ingestion",
            "owner": "user",
            "status": "active",
            "chat_entry": {
                "mode": "task_card",
                "label": "吸收 OMC task card",
                "endpoint": "/api/projects/omc-ingest/tasks",
            },
            "external_reference_refs": ["source_omc_repo", "source_omc_debate_loop_docs"],
            "candidate_refs": [],
            "adopted_candidate_refs": [],
            "capability_refs": [
                "cap_claude_code_cli",
                "cap_codex_cli",
                "cap_gemini_cli",
                "cap_gemini_web",
            ],
            "run_refs": [],
        },
        "external_references": [
            {
                "source_ref": "source_omc_repo",
                "title": "oh-my-codex OMC repository",
                "url": "https://github.com/auggie/oh-my-codex",
                "mode": "link-only",
            },
            {
                "source_ref": "source_omc_debate_loop_docs",
                "title": "D2-01 OMC debate-loop public outlet",
                "url": "docs/OMC_DEBATE_LOOP.md",
                "mode": "link-only",
            },
        ],
        "task_card": {
            "task_id": "task_omc_ingest",
            "title": "吸收 OMC `omc help` slash 命令列表 → 写成 NoeticBraid lesson",
            "prompt": "吸收 OMC `omc help` slash 命令列表，写成 NoeticBraid candidate lesson。",
            "source_refs": ["source_project_definition_v3_2", "source_ai_invocation_reference", "source_omc_metadata"],
        },
        "candidates": [],
        "adopted_history": [],
        "run_records": [],
    }


class OMCProjectStore:
    """Small JSON-backed store for demo project state and test fixtures."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / "omc_workspace" / "project_state.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            state = _default_state()
            WorkspaceProject.model_validate(state["project"])
            return state
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = _default_state()
        WorkspaceProject.model_validate(state["project"])
        return state

    def save(self, state: dict[str, Any]) -> None:
        WorkspaceProject.model_validate(state["project"])
        for candidate in state.get("candidates", []):
            CandidateLesson.model_validate(candidate)
        for candidate in state.get("adopted_history", []):
            CandidateLesson.model_validate(candidate)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp_path, self.path)

    def project(self) -> dict[str, Any]:
        return self.load()["project"]

    def task_card(self) -> dict[str, Any]:
        return self.load()["task_card"]

    def candidates(self) -> list[dict[str, Any]]:
        return [candidate for candidate in self.load()["candidates"] if candidate.get("project_id") == PROJECT_ID]

    def adopted_history(self) -> list[dict[str, Any]]:
        return [candidate for candidate in self.load()["adopted_history"] if candidate.get("project_id") == PROJECT_ID]

    def run_records(self) -> list[dict[str, Any]]:
        return list(self.load().get("run_records", []))

    def upsert_candidate(self, candidate: dict[str, Any], run_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        candidate = CandidateLesson.model_validate(candidate).model_dump(mode="json")
        state = self.load()
        candidates = [item for item in state["candidates"] if item["candidate_id"] != candidate["candidate_id"]]
        candidates.append(candidate)
        state["candidates"] = candidates
        project = state["project"]
        project["candidate_refs"] = sorted({*project.get("candidate_refs", []), candidate["candidate_id"]})
        if candidate.get("run_record_ref"):
            project["run_refs"] = sorted({*project.get("run_refs", []), candidate["run_record_ref"]})
        if run_records:
            existing_keys = {(item.get("run_id"), item.get("event_type"), item.get("routing_advice")) for item in state.get("run_records", [])}
            for record in run_records:
                key = (record.get("run_id"), record.get("event_type"), record.get("routing_advice"))
                if key not in existing_keys:
                    state.setdefault("run_records", []).append(record)
                    existing_keys.add(key)
        self.save(state)
        return candidate

    def adopt_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate = CandidateLesson.model_validate(candidate).model_dump(mode="json")
        state = self.load()
        state["candidates"] = [item for item in state["candidates"] if item["candidate_id"] != candidate["candidate_id"]]
        state["candidates"].append(candidate)
        adopted = [item for item in state["adopted_history"] if item["candidate_id"] != candidate["candidate_id"]]
        adopted.append(candidate)
        state["adopted_history"] = adopted
        project = state["project"]
        project["candidate_refs"] = sorted({*project.get("candidate_refs", []), candidate["candidate_id"]})
        project["adopted_candidate_refs"] = sorted({*project.get("adopted_candidate_refs", []), candidate["candidate_id"]})
        if candidate.get("run_record_ref"):
            project["run_refs"] = sorted({*project.get("run_refs", []), candidate["run_record_ref"]})
        self.save(state)
        return candidate

    def find_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        for candidate in self.candidates():
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        return None


def public_artifact_ref(value: str) -> str:
    """Return artifact paths without leaking host-private absolute prefixes."""

    path = Path(value)
    parts = path.parts
    if ".omx" in parts:
        index = parts.index(".omx")
        return str(Path(*parts[index:]))
    return value


def candidate_from_d2_result(result: dict[str, Any]) -> dict[str, Any]:
    d2_candidate = result["candidate"]
    run_ref = result.get("route", {}).get("run_refs", [None])[0] or f"run_{result['task_id'].removeprefix('task_')}"
    artifact_refs = list(dict.fromkeys(d2_candidate.get("artifact_refs", [])))
    markdown_path = result.get("artifact_paths", {}).get("convergence_markdown")
    if markdown_path:
        artifact_refs.append(public_artifact_ref(str(markdown_path)))
    return {
        "candidate_id": d2_candidate["candidate_id"],
        "project_id": PROJECT_ID,
        "source_sdd_ids": ["SDD-D2-01", "SDD-D2-02"],
        "summary": d2_candidate["summary"],
        "status": "candidate",
        "upgrade_rule": result.get("upgrade_rule") or DEFAULT_UPGRADE_RULE,
        "adopted_at": None,
        "adopted_by": None,
        "run_record_ref": run_ref,
        "reuse_evidence_refs": [],
        "artifact_refs": artifact_refs,
        "source_refs": d2_candidate.get("source_refs", []),
    }


__all__ = ["DEFAULT_UPGRADE_RULE", "OMCProjectStore", "PROJECT_ID", "PROJECT_TITLE", "candidate_from_d2_result", "public_artifact_ref"]
