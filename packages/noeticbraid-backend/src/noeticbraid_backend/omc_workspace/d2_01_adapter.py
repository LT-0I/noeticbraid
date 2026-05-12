# SPDX-License-Identifier: Apache-2.0
"""D2-01 public outlet adapter for SDD-D2-02 OMC ingestion tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run_omc_debate_loop(
    task_card: dict[str, Any],
    *,
    state_root: Path,
    artifact_root: Path,
    mock_invocations: bool = True,
) -> dict[str, Any]:
    """Call the D2-01 public API without modifying SP-B internals."""

    from noeticbraid.tools.multimodel_alliance import run_debate_loop

    return run_debate_loop(
        task_card,
        state_root=state_root,
        artifact_root=artifact_root,
        mock_invocations=mock_invocations,
        provider_mode=False,
    )


__all__ = ["run_omc_debate_loop"]
