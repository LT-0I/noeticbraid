"""Write policy settings schema for contract 1.3.0."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG

RELATIVE_ROOT_RE = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*//)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/$"
)
RELATIVE_GLOB_RE = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*//)[A-Za-z0-9_./*?\[\]{}!-]+$"
)
RELATIVE_PATH_RE = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*//)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$"
)

RelativeRoot = Annotated[str, Field()]
RelativeGlob = Annotated[str, Field()]
RelativePath = Annotated[str, Field(max_length=1024)]


class WritePolicy(BaseModel):
    """Obsidian hub write policy settings without contract_version or nb_type."""

    model_config = COMMON_MODEL_CONFIG

    schema_version: Literal["obsidian-hub-settings-0.1"] = Field(
        ..., description="Obsidian hub settings schema family version."
    )
    vault_root_env: Literal["OBSIDIAN_HUB_VAULT_ROOT"] = Field(
        ..., description="Private vault root environment variable placeholder."
    )
    # NO-LEAK: namespace is a label, not a path or credential value.
    namespace: str = Field(..., pattern=r"^[A-Za-z0-9_-]+$")
    allowlist_relative_roots: list[RelativeRoot] = Field(..., min_length=1)
    denylist_relative_globs: list[RelativeGlob] = Field(..., min_length=1)
    default_write_mode: Literal["dry_run"]
    generated_overwrite_allowed: Literal[True]
    non_generated_overwrite_allowed: Literal[False]
    stable_record_write_mode: Literal["create_only"]
    atomic_write_intent: Literal[True]
    user_dropzone_read_relative_root: Optional[RelativeRoot] = None
    append_only_heading_policy: Optional[Literal["status_and_decision_notes_only"]] = None
    # NO-LEAK: sync log paths are relative vault paths, not absolute credential paths.
    sync_log_relative_path: Optional[RelativePath] = None
    generated_surface_requires_frontmatter: Optional[Literal[True]] = None
    optional_integrations: Optional[dict[str, Any]] = None

    @field_validator("allowlist_relative_roots")
    @classmethod
    def _validate_allowlist_relative_roots(cls, value: list[str]) -> list[str]:
        for item in value:
            if RELATIVE_ROOT_RE.fullmatch(item) is None:
                raise ValueError("allowlist_relative_roots items must be safe relative roots")
        return value

    @field_validator("denylist_relative_globs")
    @classmethod
    def _validate_denylist_relative_globs(cls, value: list[str]) -> list[str]:
        for item in value:
            if RELATIVE_GLOB_RE.fullmatch(item) is None:
                raise ValueError("denylist_relative_globs items must be safe relative globs")
        return value

    @field_validator("user_dropzone_read_relative_root")
    @classmethod
    def _validate_user_dropzone_read_relative_root(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and RELATIVE_ROOT_RE.fullmatch(value) is None:
            raise ValueError("user_dropzone_read_relative_root must be a safe relative root")
        return value

    @field_validator("sync_log_relative_path")
    @classmethod
    def _validate_sync_log_relative_path(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and RELATIVE_PATH_RE.fullmatch(value) is None:
            raise ValueError("sync_log_relative_path must be a safe relative path")
        return value
