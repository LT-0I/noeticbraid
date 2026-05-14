from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import notebooklm

from ._errors import NotebookLMSerializationError


# --- 1. NoeticBraid-internal artifact taxonomy ---

class ArtifactKind(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    CINEMATIC_VIDEO = "cinematic_video"
    REPORT = "report"
    STUDY_GUIDE = "study_guide"
    QUIZ = "quiz"
    FLASHCARDS = "flashcards"
    INFOGRAPHIC = "infographic"
    SLIDE_DECK = "slide_deck"
    DATA_TABLE = "data_table"
    MIND_MAP = "mind_map"


ARTIFACT_KIND_TO_TAG: dict[ArtifactKind, str] = {
    ArtifactKind.AUDIO: "noeticbraid/notebooklm/audio",
    ArtifactKind.VIDEO: "noeticbraid/notebooklm/video",
    ArtifactKind.CINEMATIC_VIDEO: "noeticbraid/notebooklm/cinematic-video",
    ArtifactKind.REPORT: "noeticbraid/notebooklm/report",
    ArtifactKind.STUDY_GUIDE: "noeticbraid/notebooklm/study-guide",
    ArtifactKind.QUIZ: "noeticbraid/notebooklm/quiz",
    ArtifactKind.FLASHCARDS: "noeticbraid/notebooklm/flashcards",
    ArtifactKind.INFOGRAPHIC: "noeticbraid/notebooklm/infographic",
    ArtifactKind.SLIDE_DECK: "noeticbraid/notebooklm/slide-deck",
    ArtifactKind.DATA_TABLE: "noeticbraid/notebooklm/data-table",
    ArtifactKind.MIND_MAP: "noeticbraid/notebooklm/mind-map",
}


KIND_TO_DOWNLOAD_METHOD: dict[ArtifactKind, str] = {
    ArtifactKind.AUDIO: "download_audio",
    ArtifactKind.VIDEO: "download_video",
    ArtifactKind.CINEMATIC_VIDEO: "download_video",
    ArtifactKind.REPORT: "download_report",
    ArtifactKind.STUDY_GUIDE: "download_report",
    ArtifactKind.QUIZ: "download_quiz",
    ArtifactKind.FLASHCARDS: "download_flashcards",
    ArtifactKind.INFOGRAPHIC: "download_infographic",
    ArtifactKind.SLIDE_DECK: "download_slide_deck",
    ArtifactKind.DATA_TABLE: "download_data_table",
    ArtifactKind.MIND_MAP: "download_mind_map",
}


# --- 2. Serializer ---

_SOURCE_REF_ID_BODY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^run_[A-Za-z0-9_]+$")
_SOURCE_REF_ID_PREFIX = "source_notebooklm_"
_SOURCE_REF_ID_MAXLEN = 128


def artifact_to_source_record(
    *,
    artifact_id: str,
    kind: ArtifactKind,
    captured_at: datetime,
    title: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
) -> dict[str, Any]:
    """Map a NotebookLM artifact's (id, kind, metadata) to SourceRecord 1.0.0."""
    if not isinstance(artifact_id, str) or not _SOURCE_REF_ID_BODY_RE.fullmatch(artifact_id):
        raise NotebookLMSerializationError(
            error_class="invalid_artifact_id",
            detail=f"artifact_id must match {_SOURCE_REF_ID_BODY_RE.pattern}: {artifact_id!r}",
        )

    source_ref_id = f"{_SOURCE_REF_ID_PREFIX}{artifact_id}"
    if len(source_ref_id) > _SOURCE_REF_ID_MAXLEN:
        raise NotebookLMSerializationError(
            error_class="invalid_artifact_id",
            detail=f"source_ref_id too long: {len(source_ref_id)} > {_SOURCE_REF_ID_MAXLEN}",
        )

    if not isinstance(kind, ArtifactKind):
        raise NotebookLMSerializationError(
            error_class="invalid_kind",
            detail=f"kind must be ArtifactKind, got {type(kind).__name__}",
        )

    if captured_at.tzinfo is None:
        raise NotebookLMSerializationError(
            error_class="naive_captured_at",
            detail="captured_at must be timezone-aware",
        )

    if local_path is not None and (not isinstance(local_path, Path) or not local_path.exists()):
        raise NotebookLMSerializationError(
            error_class="local_path_missing",
            detail=f"local_path must be an existing pathlib.Path: {local_path!r}",
        )

    if content_hash is not None and not _CONTENT_HASH_RE.fullmatch(content_hash):
        raise NotebookLMSerializationError(
            error_class="invalid_content_hash",
            detail=f"content_hash must match {_CONTENT_HASH_RE.pattern}: {content_hash!r}",
        )

    if retrieved_by_run_id is not None and not _RUN_ID_RE.fullmatch(retrieved_by_run_id):
        raise NotebookLMSerializationError(
            error_class="invalid_run_id",
            detail=f"retrieved_by_run_id must match {_RUN_ID_RE.pattern}: {retrieved_by_run_id!r}",
        )

    if title is not None and title.strip() == "":
        raise NotebookLMSerializationError(
            error_class="title_empty",
            detail="title must not be empty when provided",
        )

    record_title = title if title is not None else f"NotebookLM {kind.value} ({artifact_id})"

    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": source_ref_id,
        "source_type": "ai_output",
        "title": record_title[:512],
        "captured_at": captured_at.astimezone(timezone.utc).isoformat(),
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": [ARTIFACT_KIND_TO_TAG[kind]],
    }
    if local_path is not None:
        record["local_path"] = str(local_path)
    if content_hash is not None:
        record["content_hash"] = content_hash
    if retrieved_by_run_id is not None:
        record["retrieved_by_run_id"] = retrieved_by_run_id
    record["source_fingerprint"] = f"notebooklm_artifact:{artifact_id}"
    return record


# --- 3. wait_then_download (generic 2-step helper, NOT for mind_map) ---

async def wait_then_download(
    client: "notebooklm.NotebookLMClient",
    *,
    notebook_id: str,
    task_id: str,
    download_method_name: str,
    output_path: Path,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
    download_kwargs: Optional[dict[str, Any]] = None,
) -> Path:
    """Block until task_id completes, then invoke the named download method."""
    final = await client.artifacts.wait_for_completion(
        notebook_id,
        task_id,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    if final.status != "completed":
        raise NotebookLMSerializationError(
            error_class="wait_not_completed",
            detail=f"task {task_id}: status={final.status}, error={getattr(final, 'error', None)}",
        )

    download = getattr(client.artifacts, download_method_name, None)
    if not callable(download):
        raise ValueError(f"client.artifacts has no method {download_method_name!r}")

    forbidden = {"notebook_id", "output_path", "artifact_id"}
    if download_kwargs and (overlap := forbidden & set(download_kwargs)):
        raise NotebookLMSerializationError(
            error_class="forbidden_download_kwarg_override",
            detail=f"keys {sorted(overlap)} reserved",
        )

    kwargs = {
        "notebook_id": notebook_id,
        "output_path": str(output_path),
        "artifact_id": task_id,
    }
    kwargs.update(download_kwargs or {})
    returned = await download(**kwargs)
    return Path(returned)


# --- 4. Composite helpers — 10 via wait_then_download ---

def _without_none(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


async def generate_and_download_audio(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    audio_format: Optional["notebooklm.AudioFormat"] = None,
    audio_length: Optional["notebooklm.AudioLength"] = None,
    timeout: float = 600.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    """generate -> wait -> download -> return (status, path).

    Idempotency: NOT idempotent; each call creates a new NotebookLM audio
    artifact server-side.
    """
    status = await client.artifacts.generate_audio(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
                "audio_format": audio_format,
                "audio_length": audio_length,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.AUDIO],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_video(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    video_format: Optional["notebooklm.VideoFormat"] = None,
    video_style: Optional["notebooklm.VideoStyle"] = None,
    timeout: float = 900.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_video(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
                "video_format": video_format,
                "video_style": video_style,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.VIDEO],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_cinematic_video(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    timeout: float = 1200.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_cinematic_video(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.CINEMATIC_VIDEO],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_report(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    report_format: Optional["notebooklm.ReportFormat"] = None,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    custom_prompt: Optional[str] = None,
    extra_instructions: Optional[str] = None,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_report(
        notebook_id,
        **_without_none(
            {
                "report_format": report_format,
                "source_ids": source_ids,
                "language": language,
                "custom_prompt": custom_prompt,
                "extra_instructions": extra_instructions,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.REPORT],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_study_guide(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    extra_instructions: Optional[str] = None,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_study_guide(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "extra_instructions": extra_instructions,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.STUDY_GUIDE],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_quiz(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    instructions: Optional[str] = None,
    quantity: Optional["notebooklm.QuizQuantity"] = None,
    difficulty: Optional["notebooklm.QuizDifficulty"] = None,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_quiz(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "instructions": instructions,
                "quantity": quantity,
                "difficulty": difficulty,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.QUIZ],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_flashcards(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    instructions: Optional[str] = None,
    quantity: Optional["notebooklm.QuizQuantity"] = None,
    difficulty: Optional["notebooklm.QuizDifficulty"] = None,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_flashcards(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "instructions": instructions,
                "quantity": quantity,
                "difficulty": difficulty,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.FLASHCARDS],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_infographic(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    orientation: Optional["notebooklm.InfographicOrientation"] = None,
    detail_level: Optional["notebooklm.InfographicDetail"] = None,
    style: Optional["notebooklm.InfographicStyle"] = None,
    timeout: float = 600.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_infographic(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
                "orientation": orientation,
                "detail_level": detail_level,
                "style": style,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.INFOGRAPHIC],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_slide_deck(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    slide_format: Optional["notebooklm.SlideDeckFormat"] = None,
    slide_length: Optional["notebooklm.SlideDeckLength"] = None,
    timeout: float = 600.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_slide_deck(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
                "slide_format": slide_format,
                "slide_length": slide_length,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.SLIDE_DECK],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


async def generate_and_download_data_table(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
    timeout: float = 300.0,
    poll_interval: Optional[float] = None,
) -> "tuple[notebooklm.GenerationStatus, Path]":
    status = await client.artifacts.generate_data_table(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
            }
        ),
    )
    path = await wait_then_download(
        client,
        notebook_id=notebook_id,
        task_id=status.task_id,
        download_method_name=KIND_TO_DOWNLOAD_METHOD[ArtifactKind.DATA_TABLE],
        output_path=output_path,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    return (status, path)


# --- 5. Special composite helper for mind_map (separate path) ---

async def generate_and_download_mind_map(
    client: "notebooklm.NotebookLMClient",
    notebook_id: str,
    output_path: Path,
    *,
    source_ids: Optional[list[str]] = None,
    language: str = "en",
    instructions: Optional[str] = None,
) -> "tuple[str, Path]":
    """generate (dict, no wait_for_completion) -> download -> return (note_id, path)."""
    result = await client.artifacts.generate_mind_map(
        notebook_id,
        **_without_none(
            {
                "source_ids": source_ids,
                "language": language,
                "instructions": instructions,
            }
        ),
    )
    if not isinstance(result, dict):
        raise NotebookLMSerializationError(
            error_class="upstream_mind_map_shape_mismatch",
            detail=f"expected dict, got {type(result).__name__}",
        )
    if "note_id" not in result or "mind_map" not in result:
        raise NotebookLMSerializationError(
            error_class="upstream_mind_map_shape_mismatch",
            detail=f"missing keys; got {sorted(result.keys())}",
        )
    note_id = result["note_id"]
    if not isinstance(note_id, str) or not note_id:
        raise NotebookLMSerializationError(
            error_class="mind_map_no_note_id",
            detail=f"note_id missing or empty: {note_id!r}",
        )
    returned = await client.artifacts.download_mind_map(
        notebook_id,
        str(output_path),
        artifact_id=note_id,
    )
    return (note_id, Path(returned))
