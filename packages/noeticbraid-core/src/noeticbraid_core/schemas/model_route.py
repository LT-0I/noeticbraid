"""ModelRoute schema for contract 1.2.0."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import (
    COMMON_MODEL_CONFIG,
    empty_str_to_none,
    validate_optional_prefixed_identifier,
    validate_ref_list,
)

ModelRouteRole = Literal[
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


class SelectedModel(BaseModel):
    """A selected model and its invocation role."""

    model_config = COMMON_MODEL_CONFIG

    model_ref: str = Field(..., max_length=128, pattern=r"^model_[A-Za-z0-9_]+$")
    role: ModelRouteRole
    invocation: Literal["local_session", "codex_cli", "chatgpt_web", "subagent", "manual"]
    reason: str = Field(..., min_length=1, max_length=2048)


class RejectedModel(BaseModel):
    """A model considered but rejected for this route."""

    model_config = COMMON_MODEL_CONFIG

    model_ref: str = Field(..., max_length=128, pattern=r"^model_[A-Za-z0-9_]+$")
    reason: str = Field(..., min_length=1, max_length=2048)


class ModelRoute(BaseModel):
    """Contract 1.2.0 record for deciding model alliance routes."""

    model_config = COMMON_MODEL_CONFIG

    route_id: str = Field(..., max_length=128, pattern=r"^route_[A-Za-z0-9_]+$")
    task_id: str = Field(..., max_length=128, pattern=r"^task_[A-Za-z0-9_]+$")
    workflow_id: Optional[str] = Field(default=None, max_length=128)
    route_type: Literal[
        "single_model",
        "producer_reviewer",
        "dual_review",
        "multi_review",
        "manual_convergence",
    ]
    trigger: Literal["user_request", "task_card", "workflow_step", "review_gate", "failure_recovery"]
    risk_level: Literal["low", "medium", "high", "disputed"]
    required_capabilities: list[
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
        ]
    ] = Field(..., min_length=1, max_length=32)
    selected_models: list[SelectedModel] = Field(..., min_length=1, max_length=16)
    rejected_models: list[RejectedModel] = Field(..., max_length=32)
    run_refs: list[str] = Field(..., max_length=100)
    artifact_refs: list[str] = Field(..., max_length=100)
    source_refs: list[str] = Field(..., max_length=100)
    status: Literal["draft", "selected", "invoked", "superseded", "failed"]
    rationale: str = Field(..., min_length=1, max_length=4096)

    @field_validator("workflow_id", mode="before")
    @classmethod
    def _validate_workflow_id(cls, value: object) -> object:
        value = empty_str_to_none(value)
        if value is None:
            return None
        return validate_optional_prefixed_identifier(
            value, prefix="workflow_", field_name="workflow_id"
        )

    @field_validator("run_refs")
    @classmethod
    def _validate_run_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="run_", field_name="run_refs")

    @field_validator("artifact_refs")
    @classmethod
    def _validate_artifact_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="artifact_", field_name="artifact_refs")

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="source_", field_name="source_refs")
