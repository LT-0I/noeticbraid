# SPDX-License-Identifier: Apache-2.0
"""Frozen SDD-D17 deliverable plan constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Modality = Literal["document", "slides", "poster", "image", "video", "music"]
SourceKind = Literal["ledger", "ledger_to_convert", "on_disk_unledgered", "not_attempted"]


@dataclass(frozen=True, slots=True)
class DeliverablePlanItem:
    modality: Modality
    source_task_id: str | None
    source_kind: SourceKind


_DELIVERABLE_PLAN: dict[Modality, DeliverablePlanItem] = {
    "document": DeliverablePlanItem(
        modality="document",
        source_task_id="task_promo_smoke_1778967211",
        source_kind="ledger",
    ),
    "slides": DeliverablePlanItem(
        modality="slides",
        source_task_id="task_promo_chatgpt_1778967273",
        source_kind="ledger_to_convert",
    ),
    "poster": DeliverablePlanItem(
        modality="poster",
        source_task_id="task_promo_chatgpt_1778967273",
        source_kind="ledger_to_convert",
    ),
    "image": DeliverablePlanItem(
        modality="image",
        source_task_id="task_promo_image_1778991545",
        source_kind="on_disk_unledgered",
    ),
    "video": DeliverablePlanItem(
        modality="video",
        source_task_id="task_promo_gemini_1778968111",
        source_kind="on_disk_unledgered",
    ),
    "music": DeliverablePlanItem(
        modality="music",
        source_task_id=None,
        source_kind="not_attempted",
    ),
}

_FILENAMES: dict[Modality, tuple[str, str]] = {
    "document": ("NoeticBraid Promo Document", "NoeticBraid-Promo-Document.md"),
    "slides": ("NoeticBraid Promo Deck", "NoeticBraid-Promo-Deck.pptx"),
    "poster": ("NoeticBraid Promo Poster", "NoeticBraid-Promo-Poster.png"),
    "image": ("NoeticBraid Promo Image", "NoeticBraid-Promo-Image.png"),
    "video": ("NoeticBraid Promo Video", "NoeticBraid-Promo-Video.mp4"),
    "music": ("NoeticBraid Promo Music", "NoeticBraid-Promo-Music.mp3"),
}

_MODALITIES: tuple[Modality, ...] = ("document", "slides", "poster", "image", "video", "music")
_DOWNLOAD_MODALITIES: tuple[Modality, ...] = ("document", "slides", "poster", "image", "video")
_MATERIALIZATION_TASK_ID = "task_promo_chatgpt_1778967273"
_MATERIALIZATION_SIDECAR = ".deliverable_materialization.json"
_SOURCE_MARKDOWN_SHA256: dict[Modality, str] = {
    "slides": "282fdb946334e729c836295db3ec7c404819ba6f556c8a936bf3a358953210fa",
    "poster": "b78920b5fe4d4b60db7635cac92c943124dcb2318013c1192e1052a68bf3123c",
}

_CONTENT_TYPES: dict[Modality, str] = {
    "document": "text/markdown; charset=utf-8",
    "slides": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "poster": "image/png",
    "image": "image/png",
    "video": "video/mp4",
    "music": "audio/mpeg",
}

_NOT_MATERIALIZED_REASON = (
    "Local .pptx/poster conversion has not been materialized yet "
    "(run: noeticbraid platform materialize-deliverable)."
)
_NOT_ATTEMPTED_REASON = "Music generation was not attempted for this deliverable."
_UNLEDGERED_NOTES: dict[Modality, str] = {
    "image": (
        "A real PNG exists on disk for the planned source task, but no "
        "artifact_produced ledger row exists for it; ledgered:false and status remains blocked."
    ),
    "video": (
        "A real MP4 exists on disk for the planned source task, but no "
        "artifact_produced ledger row exists for it; ledgered:false and status remains blocked."
    ),
}
_FALLBACK_BLOCKED_REASONS: dict[Modality, str] = {
    "image": "hub dispatch timed out",
    "video": "artifact path governance violation",
}

__all__ = [
    "_CONTENT_TYPES",
    "_DELIVERABLE_PLAN",
    "_DOWNLOAD_MODALITIES",
    "_FALLBACK_BLOCKED_REASONS",
    "_FILENAMES",
    "_MATERIALIZATION_SIDECAR",
    "_MATERIALIZATION_TASK_ID",
    "_MODALITIES",
    "_NOT_ATTEMPTED_REASON",
    "_NOT_MATERIALIZED_REASON",
    "_SOURCE_MARKDOWN_SHA256",
    "_UNLEDGERED_NOTES",
    "DeliverablePlanItem",
    "Modality",
]
