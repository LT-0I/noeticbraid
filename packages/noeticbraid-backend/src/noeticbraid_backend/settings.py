# SPDX-License-Identifier: Apache-2.0
"""Environment-backed settings for the NoeticBraid backend."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

STATE_DIR_ENV = "NOETICBRAID_STATE_DIR"
DPAPI_BLOB_PATH_ENV = "NOETICBRAID_DPAPI_BLOB_PATH"
OMC_SOURCES_ENV = "NOETICBRAID_OMC_SOURCES"


def _default_omc_sources() -> list[tuple[Path, str]]:
    return [
        (Path.home() / ".claude" / "CLAUDE.md", "~/.claude/CLAUDE.md"),
        (Path.home() / ".claude" / "RTK.md", "~/.claude/RTK.md"),
    ]


class Settings(BaseModel):
    """Resolved backend settings.

    `state_dir` defaults to `state/`. `dpapi_blob_path` is optional and is
    resolved only from an explicit `NOETICBRAID_DPAPI_BLOB_PATH` value.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    state_dir: Path = Field(default_factory=lambda: Path("state"))
    dpapi_blob_path: Path | None = None
    omc_sources: list[tuple[Path, str]] = Field(default_factory=_default_omc_sources)

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

    @field_validator("omc_sources", mode="before")
    @classmethod
    def _coerce_omc_sources(cls, value: object) -> list[tuple[Path, str]]:
        return _coerce_omc_sources_value(value)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables without touching secrets."""

        state_dir = Path(os.environ.get(STATE_DIR_ENV, "state"))
        explicit_blob = os.environ.get(DPAPI_BLOB_PATH_ENV)
        if explicit_blob:
            dpapi_blob_path: Path | None = Path(explicit_blob)
        else:
            dpapi_blob_path = None
        kwargs: dict[str, object] = {"state_dir": state_dir, "dpapi_blob_path": dpapi_blob_path}
        if OMC_SOURCES_ENV in os.environ:
            kwargs["omc_sources"] = _parse_omc_sources(os.environ[OMC_SOURCES_ENV])
        return cls(**kwargs)

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


def _parse_omc_sources(value: str) -> list[tuple[Path, str]]:
    if not value:
        raise ValueError(f"{OMC_SOURCES_ENV} must contain colon-separated path=ref entries")
    sources: list[tuple[Path, str]] = []
    for entry in value.split(":"):
        if not entry or "=" not in entry:
            raise ValueError(f"Malformed {OMC_SOURCES_ENV} entry: {entry!r}; expected path=ref")
        path_text, source_ref = entry.split("=", 1)
        if not path_text or not source_ref:
            raise ValueError(f"Malformed {OMC_SOURCES_ENV} entry: {entry!r}; expected path=ref")
        sources.append((Path(path_text), source_ref))
    return sources


def _coerce_omc_sources_value(value: object) -> list[tuple[Path, str]]:
    if isinstance(value, str):
        return _parse_omc_sources(value)
    try:
        entries = list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError("omc_sources must be a list of (path, ref) pairs") from exc

    sources: list[tuple[Path, str]] = []
    for entry in entries:
        try:
            path, source_ref = entry
        except (TypeError, ValueError) as exc:
            raise ValueError("omc_sources entries must be (path, ref) pairs") from exc
        if not str(path) or not str(source_ref):
            raise ValueError("omc_sources entries must include non-empty path and ref")
        sources.append((Path(path), str(source_ref)))
    return sources
