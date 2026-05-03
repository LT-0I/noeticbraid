"""Workflow schema for contract 1.2.0."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, validate_ref_list

WorkflowRole = Literal[
    "orchestrator",
    "planner",
    "researcher",
    "producer",
    "writer",
    "coder",
    "reviewer",
    "adversary",
    "source_auditor",
    "verifier",
    "convergence_editor",
    "human_decision",
]


class WorkflowStep(BaseModel):
    """One ordered step in a workflow definition."""

    model_config = COMMON_MODEL_CONFIG

    step_id: str = Field(..., max_length=64, pattern=r"^step_[A-Za-z0-9_]+$")
    step_order: int = Field(..., ge=1, le=50)
    role: WorkflowRole
    capability: Optional[
        Literal[
            "planning",
            "research",
            "writing",
            "coding",
            "code_review",
            "adversary",
            "source_audit",
            "browser",
            "file_io",
            "verification",
            "security_review",
            "convergence",
            "human_review",
        ]
    ] = None
    input_kind: Optional[
        Literal[
            "task_card",
            "source_record",
            "run_record",
            "artifact",
            "prior_step_output",
            "user_input",
        ]
    ] = None
    output_kind: Optional[
        Literal[
            "artifact",
            "run_record",
            "approval_request",
            "side_note",
            "digestion_item",
            "convergence_decision",
        ]
    ] = None
    gate_policy: Literal["none", "dual_review", "multi_review", "human_required"] = "none"


class Workflow(BaseModel):
    """Workflow definition frozen into contract 1.2.0."""

    model_config = COMMON_MODEL_CONFIG

    workflow_id: str = Field(..., max_length=128, pattern=r"^workflow_[A-Za-z0-9_]+$")
    workflow_type: Literal[
        "information_radar",
        "idea_to_project",
        "literature_review",
        "code_generation_review",
        "weekly_reflection",
        "custom",
    ]
    title: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=4096)
    steps: list[WorkflowStep] = Field(..., min_length=1, max_length=50)
    related_routes: list[str] = Field(default_factory=list, max_length=32)
    related_runs: list[str] = Field(default_factory=list, max_length=100)
    status: Literal["draft", "active", "deprecated", "candidate"]

    @field_validator("description", mode="before")
    @classmethod
    def _blank_description_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    @field_validator("related_routes")
    @classmethod
    def _validate_related_routes(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="route_", field_name="related_routes")

    @field_validator("related_runs")
    @classmethod
    def _validate_related_runs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="run_", field_name="related_runs")
