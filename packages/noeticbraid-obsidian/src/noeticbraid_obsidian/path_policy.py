# SPDX-License-Identifier: Apache-2.0
"""Path resolution and write-mode enforcement for Obsidian vault writes."""

from __future__ import annotations

import fnmatch
import re
from datetime import date
from pathlib import Path, PurePosixPath

from .errors import PathPolicyError
from .settings import WritePolicySettings, default_settings

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_:-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def has_absolute_path_shape(value: str) -> bool:
    """Return True for Windows, POSIX, or home-relative absolute path shapes."""

    if re.search(r"\b[A-Za-z]:[\\/][A-Za-z0-9]", value):
        return True
    normalized = value.replace("\\", "/")
    return normalized.startswith("/") or normalized.startswith("~/")


def normalize_relative_path(path: str) -> str | None:
    """Normalize a model/caller supplied relative path or return None."""

    if not isinstance(path, str) or not path.strip():
        return None
    candidate = path.replace("\\", "/").strip()
    if has_absolute_path_shape(candidate):
        return None
    parts = candidate.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _validate_id(obj_id: str) -> str:
    if not _SAFE_ID_RE.fullmatch(obj_id):
        raise PathPolicyError(f"unsafe object id: {obj_id!r}")
    return obj_id


def _date_parts(value: str) -> tuple[str, str]:
    if not _DATE_RE.fullmatch(value):
        raise PathPolicyError("date must be YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    return f"{parsed.year:04d}", f"{parsed.month:02d}"


def resolve_path(
    nb_type: str,
    obj_id: str,
    *,
    date: str,
    namespace: str = "NoeticBraid",
    project: str = "default",
) -> str:
    """Resolve a note object to a policy-controlled vault-relative path.

    The caller supplies stable IDs only; free-form path fragments are rejected.
    """

    safe_id = _validate_id(obj_id)
    safe_project = _validate_id(project)
    year, month = _date_parts(date)
    if nb_type == "dashboard":
        return f"{namespace}/00_dashboard/{safe_id}.md"
    if nb_type == "task":
        return f"{namespace}/20_episodic_memory/40_projects/{safe_project}/plans/{safe_id}.md"
    if nb_type == "run_record":
        return f"{namespace}/30_run_ledger/10_runs/{year}/{month}/{safe_id}.md"
    if nb_type == "source_record":
        return f"{namespace}/30_run_ledger/20_sources/{year}/{month}/{safe_id}.md"
    if nb_type == "side_note":
        return f"{namespace}/20_episodic_memory/20_ai_observations/side_notes/{year}/{month}/{safe_id}.md"
    if nb_type == "digestion_item":
        return f"{namespace}/20_episodic_memory/50_digestion/active/{safe_id}.md"
    raise PathPolicyError(f"unsupported nb_type: {nb_type!r}")


class ModeEnforcer:
    """Allowlist/denylist/path-traversal gate for every vault write."""

    def __init__(self, settings: WritePolicySettings | None = None) -> None:
        self.settings = settings or default_settings()

    def is_allowed_write_path(self, path: str) -> bool:
        """Return whether a vault-relative path passes write policy."""

        normalized = normalize_relative_path(path)
        if normalized is None:
            return False
        namespace = self.settings.namespace.rstrip("/") + "/"
        if not normalized.startswith(namespace):
            return False
        segments = normalized.split("/")
        if ".obsidian" in segments or ".git" in segments:
            return False
        protected_raw = namespace + "20_episodic_memory/10_user_raw/"
        if normalized == protected_raw.rstrip("/") or normalized.startswith(protected_raw):
            return False
        if not any(
            normalized == root.rstrip("/") or normalized.startswith(root)
            for root in self.settings.allowlist_relative_roots
        ):
            return False
        return not any(fnmatch.fnmatch(normalized, pattern) for pattern in self.settings.denylist_relative_globs)

    def require_allowed_write_path(self, path: str) -> str:
        """Return normalized path or raise a typed policy error."""

        normalized = normalize_relative_path(path)
        if normalized is None or not self.is_allowed_write_path(normalized):
            raise PathPolicyError(f"write path denied by policy: {path!r}")
        return normalized

    def resolve_under_vault(self, vault_root: Path | str, relative_path: str) -> Path:
        """Resolve a policy-allowed relative path under a concrete vault root."""

        normalized = self.require_allowed_write_path(relative_path)
        root = Path(vault_root).resolve()
        target = root.joinpath(*PurePosixPath(normalized).parts).resolve()
        if target != root and root not in target.parents:
            raise PathPolicyError(f"resolved path escapes vault root: {relative_path!r}")
        return target
