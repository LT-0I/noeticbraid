from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import notebooklm
from notebooklm import Artifact, GenerationStatus

from ._artifacts import ArtifactKind, artifact_to_source_record
from ._errors import NotebookLMArtifactLifecycleError


async def revise_slide_and_serialize(
    client: notebooklm.NotebookLMClient,
    notebook_id: str,
    artifact_id: str,
    slide_index: int,
    prompt: str,
    *,
    captured_at: datetime,
    timeout: float = 300.0,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> tuple[GenerationStatus, Artifact, dict[str, Any]]:
    """Composite: revise_slide → wait_for_completion → get → serialize → 3-tuple."""
    if not notebook_id:
        raise NotebookLMArtifactLifecycleError(error_class="empty_notebook_id")
    if not artifact_id:
        raise NotebookLMArtifactLifecycleError(error_class="empty_artifact_id")

    status = await client.artifacts.revise_slide(notebook_id, artifact_id, slide_index, prompt)
    final = await client.artifacts.wait_for_completion(notebook_id, status.task_id, timeout=timeout)
    if final.is_failed:
        raise NotebookLMArtifactLifecycleError(
            error_class="revision_failed",
            detail=final.error or "",
        )

    artifact = await client.artifacts.get(notebook_id, artifact_id)
    if artifact is None:
        raise NotebookLMArtifactLifecycleError(error_class="artifact_not_found_after_revision")

    record = artifact_to_source_record(
        artifact_id=artifact.id,
        kind=ArtifactKind.SLIDE_DECK,
        captured_at=captured_at,
        title=title_override or artifact.title,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return final, artifact, record
