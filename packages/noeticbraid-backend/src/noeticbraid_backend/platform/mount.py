# SPDX-License-Identifier: Apache-2.0
"""Feature-flagged mounting for the additive platform shell."""

from __future__ import annotations

from fastapi import FastAPI

from noeticbraid_backend.platform.app import build_platform_app
from noeticbraid_backend.platform.settings import PlatformSettings


def maybe_mount_platform(app: FastAPI, settings: PlatformSettings | None = None) -> None:
    """Mount the platform sub-app only when explicitly enabled."""

    resolved = settings or PlatformSettings.from_env()
    if not resolved.enabled:
        return
    app.mount("/platform", build_platform_app())


__all__ = ["maybe_mount_platform"]
