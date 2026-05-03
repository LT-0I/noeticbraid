"""VaultLayoutMinimum schema for contract 1.2.0."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from ._common import COMMON_MODEL_CONFIG


class RootDir(BaseModel):
    """One top-level vault directory and its role."""

    model_config = COMMON_MODEL_CONFIG

    path: str = Field(..., pattern=r"^[0-9]{2}_[a-z_]+/$")
    role: Literal[
        "dashboard_workbench",
        "program_memory",
        "episodic_memory",
        "run_ledger_mirror",
        "templates",
        "bases",
        "inbox",
        "system_metadata",
    ]


class PathPolicy(BaseModel):
    """Minimal write-kind policy for the vault layout."""

    model_config = COMMON_MODEL_CONFIG

    allow_write_kinds: list[
        Literal[
            "generated_dashboard",
            "stable_record_create_only",
            "inbox_staging",
            "candidate_proposal",
            "sync_log_append_only",
        ]
    ] = Field(..., min_length=1, max_length=32)
    deny_write_kinds: list[
        Literal[
            "protected_user_raw",
            "plugin_or_config",
            "git_metadata",
            "outside_namespace",
            "path_traversal",
        ]
    ] = Field(..., min_length=1, max_length=32)


class VaultLayoutMinimum(BaseModel):
    """Minimum vault layout object frozen into contract 1.2.0."""

    model_config = COMMON_MODEL_CONFIG

    layout_id: str = Field(..., max_length=128, pattern=r"^layout_[A-Za-z0-9_]+$")
    namespace_default: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]*/$")
    root_dirs: list[RootDir] = Field(..., min_length=8, max_length=8)
    path_policy: PathPolicy
    max_depth: int = Field(..., ge=4, le=12)
    traversal_check: Literal["strict_no_parent"]
    test_cases_ref: Optional[
        Literal["noeticbraid/docs/contracts/fixtures/path_policy_cases.json"]
    ] = None
