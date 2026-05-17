# SPDX-License-Identifier: Apache-2.0
"""Phase-2 workflow library."""

from __future__ import annotations

from noeticbraid_backend.platform.workflows.loader import discover_specs
from noeticbraid_backend.platform.workflows.schema import WorkflowSpec

__all__ = ["WorkflowSpec", "discover_specs"]
