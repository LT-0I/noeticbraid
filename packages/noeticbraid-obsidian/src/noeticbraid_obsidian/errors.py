# SPDX-License-Identifier: Apache-2.0
"""Typed exceptions for SP-D Obsidian vault hub."""

from __future__ import annotations


class ObsidianHubError(Exception):
    """Base exception for SP-D package failures."""


class SettingsError(ObsidianHubError):
    """Raised when write-policy settings are invalid."""


class PathPolicyError(ObsidianHubError):
    """Raised when a path fails allowlist, denylist, or traversal policy."""


class RenderError(ObsidianHubError):
    """Raised when a note cannot be rendered safely."""


class WritePolicyViolation(ObsidianHubError):
    """Raised when a vault write violates the configured policy."""
