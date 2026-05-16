# SPDX-License-Identifier: Apache-2.0
"""Environment-backed settings for the additive platform shell."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PLATFORM_ENABLED_ENV = "NOETICBRAID_PLATFORM_ENABLED"
PLATFORM_DATA_ROOT_ENV = "NOETICBRAID_PLATFORM_DATA_ROOT"
PLATFORM_STT_MODEL_DIR_ENV = "NOETICBRAID_PLATFORM_STT_MODEL_DIR"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_DEFAULT_DATA_ROOT = Path("~/.noeticbraid-platform")


@dataclass(frozen=True, slots=True)
class PlatformSettings:
    """Resolved platform settings that do not mutate backend settings."""

    enabled: bool = False
    data_root: Path = _DEFAULT_DATA_ROOT.expanduser()
    stt_model_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "PlatformSettings":
        """Build platform settings from environment variables without I/O."""

        raw_enabled = os.environ.get(PLATFORM_ENABLED_ENV, "")
        data_root = Path(os.environ.get(PLATFORM_DATA_ROOT_ENV, str(_DEFAULT_DATA_ROOT))).expanduser()
        raw_stt_model_dir = os.environ.get(PLATFORM_STT_MODEL_DIR_ENV)
        stt_model_dir = Path(raw_stt_model_dir).expanduser() if raw_stt_model_dir else None
        return cls(
            enabled=raw_enabled.strip().lower() in _TRUE_VALUES,
            data_root=data_root,
            stt_model_dir=stt_model_dir,
        )


__all__ = [
    "PLATFORM_DATA_ROOT_ENV",
    "PLATFORM_ENABLED_ENV",
    "PLATFORM_STT_MODEL_DIR_ENV",
    "PlatformSettings",
]
