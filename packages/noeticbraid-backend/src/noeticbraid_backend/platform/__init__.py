# SPDX-License-Identifier: Apache-2.0
"""Additive multi-user platform shell for NoeticBraid."""

from __future__ import annotations

from noeticbraid_backend.platform.app import build_platform_app
from noeticbraid_backend.platform.mount import maybe_mount_platform
from noeticbraid_backend.platform.settings import PlatformSettings

__all__ = ["PlatformSettings", "build_platform_app", "maybe_mount_platform"]
