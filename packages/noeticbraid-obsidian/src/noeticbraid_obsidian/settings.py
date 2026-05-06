# SPDX-License-Identifier: Apache-2.0
"""Write-policy settings for the local Obsidian vault hub."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import SettingsError
from .resources import load_json_resource

WriteMode = str


@dataclass(frozen=True)
class WritePolicySettings:
    """Pure settings object mirroring the frozen write-policy schema.

    No vault path is stored in this object. The private vault root is resolved
    from ``vault_root_env`` only when a caller explicitly asks for it.
    """

    schema_version: str
    vault_root_env: str
    namespace: str
    allowlist_relative_roots: tuple[str, ...]
    denylist_relative_globs: tuple[str, ...]
    default_write_mode: WriteMode = "dry_run"
    generated_overwrite_allowed: bool = True
    non_generated_overwrite_allowed: bool = False
    stable_record_write_mode: str = "create_only"
    atomic_write_intent: bool = True
    user_dropzone_read_relative_root: str = "NoeticBraid/80_inbox/user_dropzone/"
    append_only_heading_policy: str = "status_and_decision_notes_only"
    sync_log_relative_path: str = "NoeticBraid/90_system/sync_log.md"
    generated_surface_requires_frontmatter: bool = True
    optional_integrations: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any], *, write_mode: str | None = None) -> "WritePolicySettings":
        """Create settings from a mapping and enforce hard defaults."""

        if "vault_root" in data or "vault_path" in data:
            raise SettingsError("settings must not contain a concrete vault path")
        mode = write_mode or data.get("default_write_mode", "dry_run")
        if mode not in {"dry_run", "live"}:
            raise SettingsError("write_mode must be dry_run or live")
        if data.get("vault_root_env") != "OBSIDIAN_HUB_VAULT_ROOT":
            raise SettingsError("vault_root_env must be OBSIDIAN_HUB_VAULT_ROOT")
        if data.get("default_write_mode") != "dry_run":
            raise SettingsError("default_write_mode must remain dry_run")
        if data.get("non_generated_overwrite_allowed") is not False:
            raise SettingsError("non_generated_overwrite_allowed must remain false")
        if data.get("stable_record_write_mode") != "create_only":
            raise SettingsError("stable_record_write_mode must remain create_only")
        return cls(
            schema_version=str(data["schema_version"]),
            vault_root_env=str(data["vault_root_env"]),
            namespace=str(data["namespace"]),
            allowlist_relative_roots=tuple(data["allowlist_relative_roots"]),
            denylist_relative_globs=tuple(data["denylist_relative_globs"]),
            default_write_mode=mode,
            generated_overwrite_allowed=bool(data.get("generated_overwrite_allowed", True)),
            non_generated_overwrite_allowed=bool(data.get("non_generated_overwrite_allowed", False)),
            stable_record_write_mode=str(data.get("stable_record_write_mode", "create_only")),
            atomic_write_intent=bool(data.get("atomic_write_intent", True)),
            user_dropzone_read_relative_root=str(
                data.get("user_dropzone_read_relative_root", "NoeticBraid/80_inbox/user_dropzone/")
            ),
            append_only_heading_policy=str(
                data.get("append_only_heading_policy", "status_and_decision_notes_only")
            ),
            sync_log_relative_path=str(data.get("sync_log_relative_path", "NoeticBraid/90_system/sync_log.md")),
            generated_surface_requires_frontmatter=bool(data.get("generated_surface_requires_frontmatter", True)),
            optional_integrations=dict(data.get("optional_integrations", {})),
        )

    @classmethod
    def from_json_file(cls, path: Path | str, *, write_mode: str | None = None) -> "WritePolicySettings":
        """Load settings from JSON."""

        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")), write_mode=write_mode)

    def vault_root_from_env(self, environ: dict[str, str] | None = None) -> Path:
        """Resolve the private vault root from the configured environment key."""

        env = environ if environ is not None else os.environ
        raw = env.get(self.vault_root_env)
        if not raw:
            raise SettingsError(f"{self.vault_root_env} is required for live vault access")
        return Path(raw)


def default_settings(*, write_mode: str | None = None) -> WritePolicySettings:
    """Return the embedded default policy settings.

    ``write_mode`` can opt a test or caller into ``live``. The serialized
    settings resource itself remains fail-closed ``dry_run``.
    """

    return WritePolicySettings.from_mapping(
        load_json_resource("config/obsidian_hub.settings.example.json"),
        write_mode=write_mode,
    )
