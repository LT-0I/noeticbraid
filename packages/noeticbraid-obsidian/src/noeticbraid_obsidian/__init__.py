# SPDX-License-Identifier: Apache-2.0
"""NoeticBraid SP-D Obsidian vault hub package."""

from __future__ import annotations

from .dashboard import DashboardContext, DashboardGenerator, preserve_manual_notes
from .frontmatter import extract_frontmatter, render_markdown
from .inbox_watcher import InboxWatcher
from .path_policy import ModeEnforcer, PathPolicyError, resolve_path
from .renderer import MarkdownRenderer, RenderedNote
from .resources import CONTRACT_VERSION, SCHEMA_VERSION, load_schema
from .settings import WritePolicySettings, default_settings
from .writer import VaultWriter, WritePolicyViolation, WriteResult

__version__ = "0.1.0"

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "DashboardContext",
    "DashboardGenerator",
    "InboxWatcher",
    "MarkdownRenderer",
    "ModeEnforcer",
    "PathPolicyError",
    "RenderedNote",
    "VaultWriter",
    "WritePolicySettings",
    "WritePolicyViolation",
    "WriteResult",
    "default_settings",
    "extract_frontmatter",
    "load_schema",
    "preserve_manual_notes",
    "render_markdown",
    "resolve_path",
]
