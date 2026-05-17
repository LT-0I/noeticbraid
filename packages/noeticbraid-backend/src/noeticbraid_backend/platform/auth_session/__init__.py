# SPDX-License-Identifier: Apache-2.0
"""Development-only platform auth session route package."""

from __future__ import annotations

from noeticbraid_backend.platform.auth_session.endpoint import register_platform_auth_session_routes

__all__ = ["register_platform_auth_session_routes"]
