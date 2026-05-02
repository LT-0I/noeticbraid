# SPDX-License-Identifier: Apache-2.0
"""Environment-backed settings for the NoeticBraid backend."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATE_DIR_ENV = "NOETICBRAID_STATE_DIR"
DPAPI_BLOB_PATH_ENV = "NOETICBRAID_DPAPI_BLOB_PATH"


class Settings(BaseModel):
    """Resolved backend settings.

    `state_dir` defaults to `state/`. `dpapi_blob_path` is optional and is
    resolved only from an explicit `NOETICBRAID_DPAPI_BLOB_PATH` value.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    state_dir: Path = Field(default_factory=lambda: Path("state"))
    dpapi_blob_path: Path | None = None

    @field_validator("state_dir", mode="before")
    @classmethod
    def _coerce_state_dir(cls, value: str | Path) -> Path:
        return Path(value)

    @field_validator("dpapi_blob_path", mode="before")
    @classmethod
    def _coerce_dpapi_blob_path(cls, value: str | Path | None) -> Path | None:
        if value in (None, ""):
            return None
        return Path(value)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables without touching secrets."""

        state_dir = Path(os.environ.get(STATE_DIR_ENV, "state"))
        explicit_blob = os.environ.get(DPAPI_BLOB_PATH_ENV)
        if explicit_blob:
            dpapi_blob_path: Path | None = Path(explicit_blob)
        else:
            dpapi_blob_path = None
        return cls(state_dir=state_dir, dpapi_blob_path=dpapi_blob_path)

    @property
    def token_store_path(self) -> Path:
        """Return `{state_dir}/auth/tokens.sqlite`."""

        return self.state_dir / "auth" / "tokens.sqlite"

    @property
    def approval_queue_path(self) -> Path:
        """Return `{state_dir}/approval/queue.jsonl`."""

        return self.state_dir / "approval" / "queue.jsonl"

    @property
    def account_quota_dir(self) -> Path:
        """Return `{state_dir}/account_quota`."""

        return self.state_dir / "account_quota"
