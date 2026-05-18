# SPDX-License-Identifier: Apache-2.0
"""Additive Web-AI modality routes for SDD-D22 cross-model review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat

RouteKind = Literal["route", "blocked"]
ParamKind = Literal["textual", "generate", "generate_async"]
ReviewerInputKind = Literal["text", "file"]


@dataclass(frozen=True, slots=True)
class ModalityRoute:
    """A dispatchable Web-AI generate→review route."""

    kind: Literal["route"]
    modality: str
    generator_op: str
    generator_vendor: str
    generator_profile: str
    reviewer_op: str
    reviewer_vendor: str
    reviewer_profile: str
    artifact_extension: str
    prompt_preamble: str
    param_kind: ParamKind
    reviewer_input_kind: ReviewerInputKind

    @property
    def op(self) -> str:
        """Compatibility alias for the generator operation."""

        return self.generator_op


@dataclass(frozen=True, slots=True)
class ModalityBlocked:
    """A fail-closed route decision."""

    kind: Literal["blocked"]
    modality: str
    reason: str


_TEXTUAL_ROUTE = {
    "generator_op": "webai_chatgpt_send_prompt",
    "generator_vendor": "chatgpt",
    "generator_profile": "chatgpt",
    "reviewer_op": "webai_claude_upload_and_query",
    "reviewer_vendor": "claude",
    "reviewer_profile": "claude",
    "artifact_extension": "md",
    "param_kind": "textual",
    "reviewer_input_kind": "text",
}

_MODALITY_ROUTES: dict[str, dict[str, str]] = {
    "text": {
        **_TEXTUAL_ROUTE,
        "prompt_preamble": "Produce a concise text answer for this NoeticBraid platform task.",
    },
    "document": {
        **_TEXTUAL_ROUTE,
        "prompt_preamble": "Produce a structured document draft for this NoeticBraid platform task.",
    },
    "slides": {
        **_TEXTUAL_ROUTE,
        "prompt_preamble": "Produce a slide-by-slide deck outline for this NoeticBraid platform task.",
    },
    "poster": {
        **_TEXTUAL_ROUTE,
        "prompt_preamble": "Produce poster copy and layout guidance for this NoeticBraid platform task.",
    },
    "image": {
        "generator_op": "webai_chatgpt_generate_image",
        "generator_vendor": "chatgpt",
        "generator_profile": "chatgpt",
        "reviewer_op": "webai_claude_upload_and_query",
        "reviewer_vendor": "claude",
        "reviewer_profile": "claude",
        "artifact_extension": "png",
        "param_kind": "generate",
        "reviewer_input_kind": "file",
        "prompt_preamble": "Generate a production-ready image for this NoeticBraid platform task.",
    },
    "video": {
        "generator_op": "webai_gemini_generate_video",
        "generator_vendor": "gemini",
        "generator_profile": "gemini-9225",
        "reviewer_op": "webai_claude_upload_and_query",
        "reviewer_vendor": "claude",
        "reviewer_profile": "claude",
        "artifact_extension": "mp4",
        "param_kind": "generate_async",
        "reviewer_input_kind": "file",
        "prompt_preamble": "Generate a concise video artifact for this NoeticBraid platform task.",
    },
}

_UNREACHABLE_MODALITIES = frozenset({"music"})
_REQUIRED_DISPATCH_OPS = frozenset(
    op for route in _MODALITY_ROUTES.values() for op in (route["generator_op"], route["reviewer_op"])
)
_UNDISPATCHABLE_OPS = frozenset(op for op in _REQUIRED_DISPATCH_OPS if op not in compat.DISPATCHABLE)


def resolve_web_modality(modality: str) -> ModalityRoute | ModalityBlocked:
    """Return the SDD-D22 route or a structured fail-closed block."""

    normalized = str(modality or "").strip().lower()
    if not normalized:
        return ModalityBlocked(kind="blocked", modality="unknown", reason="modality is empty")
    if normalized in _UNREACHABLE_MODALITIES:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason="modality music is structurally blocked by posture-甲",
        )
    route = _MODALITY_ROUTES.get(normalized)
    if route is None:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason=f"modality {normalized} is not mapped to a Web-AI route",
        )
    missing = [op for op in (route["generator_op"], route["reviewer_op"]) if op in _UNDISPATCHABLE_OPS]
    if missing:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason=f"mapped operation {missing[0]} is not compat.DISPATCHABLE",
        )
    if route["generator_vendor"] == route["reviewer_vendor"]:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason="generator and reviewer vendors must differ",
        )
    return ModalityRoute(
        kind="route",
        modality=normalized,
        generator_op=route["generator_op"],
        generator_vendor=route["generator_vendor"],
        generator_profile=route["generator_profile"],
        reviewer_op=route["reviewer_op"],
        reviewer_vendor=route["reviewer_vendor"],
        reviewer_profile=route["reviewer_profile"],
        artifact_extension=route["artifact_extension"],
        prompt_preamble=route["prompt_preamble"],
        param_kind=route["param_kind"],
        reviewer_input_kind=route["reviewer_input_kind"],
    )


__all__ = [
    "ModalityBlocked",
    "ModalityRoute",
    "ParamKind",
    "ReviewerInputKind",
    "RouteKind",
    "resolve_web_modality",
]
