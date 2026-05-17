# SPDX-License-Identifier: Apache-2.0
"""Frozen Phase-1 capability registry for conversational task elicitation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityStatus = Literal["supported", "unavailable", "deferred"]


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    modality: str
    capability_status: CapabilityStatus
    reason_zh: str | None = None
    reason_en: str | None = None

    @property
    def blocked_reason(self) -> str | None:
        return self.reason_zh or self.reason_en

    def to_json_dict(self) -> dict[str, str | None]:
        return {
            "modality": self.modality,
            "capability_status": self.capability_status,
            "reason_zh": self.reason_zh,
            "reason_en": self.reason_en,
        }


CAPABILITY_REGISTRY: dict[str, CapabilityEntry] = {
    "text": CapabilityEntry(modality="text", capability_status="supported"),
    "document": CapabilityEntry(modality="document", capability_status="supported"),
    "research": CapabilityEntry(modality="research", capability_status="supported"),
    "code": CapabilityEntry(modality="code", capability_status="supported"),
    "image": CapabilityEntry(
        modality="image",
        capability_status="unavailable",
        reason_zh="图像生成目前还达不到，这部分我们暂时做不了。",
        reason_en="Image generation is not good enough yet, so we cannot do this part for now.",
    ),
    "video": CapabilityEntry(
        modality="video",
        capability_status="unavailable",
        reason_zh="视频生成目前还达不到。",
        reason_en="Video generation is not good enough yet.",
    ),
    "music": CapabilityEntry(
        modality="music",
        capability_status="unavailable",
        reason_zh="音乐生成目前还达不到。",
        reason_en="Music generation is not good enough yet.",
    ),
    "slides": CapabilityEntry(
        modality="slides",
        capability_status="deferred",
        reason_zh="幻灯片生成将在后续阶段接入，本阶段暂不执行。",
        reason_en="Slides generation will be connected in a later phase and is not available in this phase.",
    ),
    "ppt": CapabilityEntry(
        modality="ppt",
        capability_status="deferred",
        reason_zh="PPT 生成将在后续阶段接入，本阶段暂不执行。",
        reason_en="PPT generation will be connected in a later phase and is not available in this phase.",
    ),
    "web_ai": CapabilityEntry(
        modality="web_ai",
        capability_status="deferred",
        reason_zh="Web AI 将在后续阶段接入，本阶段暂不执行。",
        reason_en="Web AI will be connected in a later phase and is not available in this phase.",
    ),
}


SUPPORTED_MODALITIES = tuple(
    modality for modality, entry in CAPABILITY_REGISTRY.items() if entry.capability_status == "supported"
)
UNAVAILABLE_MODALITIES = tuple(
    modality for modality, entry in CAPABILITY_REGISTRY.items() if entry.capability_status == "unavailable"
)
DEFERRED_MODALITIES = tuple(
    modality for modality, entry in CAPABILITY_REGISTRY.items() if entry.capability_status == "deferred"
)


def capability_for(modality: str) -> CapabilityEntry:
    key = str(modality or "").strip().lower()
    if key == "pptx":
        key = "ppt"
    return CAPABILITY_REGISTRY.get(key, CAPABILITY_REGISTRY["text"])


def serialize_capabilities() -> list[dict[str, str | None]]:
    return [entry.to_json_dict() for entry in CAPABILITY_REGISTRY.values()]


__all__ = [
    "CAPABILITY_REGISTRY",
    "DEFERRED_MODALITIES",
    "SUPPORTED_MODALITIES",
    "UNAVAILABLE_MODALITIES",
    "CapabilityEntry",
    "CapabilityStatus",
    "capability_for",
    "serialize_capabilities",
]
