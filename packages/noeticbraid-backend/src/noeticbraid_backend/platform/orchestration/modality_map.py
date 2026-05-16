# SPDX-License-Identifier: Apache-2.0
"""Closed modality-to-hub operation map for platform C3 dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat

RouteKind = Literal["route", "blocked"]
ParamKind = Literal["textual", "generate"]


@dataclass(frozen=True, slots=True)
class ModalityRoute:
    """A dispatchable modality route."""

    kind: Literal["route"]
    modality: str
    op: str
    vendor: str
    profile: str
    artifact_extension: str
    prompt_preamble: str
    param_kind: ParamKind


@dataclass(frozen=True, slots=True)
class ModalityBlocked:
    """A fail-closed modality route."""

    kind: Literal["blocked"]
    modality: str
    reason: str


_TEXTUAL_ROUTE = {
    "op": "webai_chatgpt_send_prompt",
    "vendor": "chatgpt",
    "profile": "chatgpt",
    "artifact_extension": "md",
    "param_kind": "textual",
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
        "op": "webai_chatgpt_generate_image",
        "vendor": "chatgpt",
        "profile": "chatgpt",
        "artifact_extension": "png",
        "param_kind": "generate",
        "prompt_preamble": "Generate a production-ready image for this NoeticBraid platform task.",
    },
    "video": {
        "op": "webai_gemini_generate_video",
        # vendor = "gemini" (hub op family); profile = "gemini-9225" is the actual
        # logged-in Gemini browser profile in the hub's profile registry — the
        # vendor/profile asymmetry is intentional, do not "normalize" them.
        "vendor": "gemini",
        "profile": "gemini-9225",
        "artifact_extension": "mp4",
        "param_kind": "generate",
        "prompt_preamble": "Generate a concise video artifact for this NoeticBraid platform task.",
    },
}

_UNREACHABLE_MODALITIES = frozenset({"music"})


def resolve_modality(modality: str) -> ModalityRoute | ModalityBlocked:
    """Return the dispatchable hub route or a structured blocked reason."""

    normalized = str(modality or "").strip().lower()
    if not normalized:
        return ModalityBlocked(kind="blocked", modality="unknown", reason="modality is empty")
    if normalized in _UNREACHABLE_MODALITIES:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason=(
                "modality music is admitted but structurally blocked by posture-甲 "
                "(no operator --confirmed)"
            ),
        )
    route = _MODALITY_ROUTES.get(normalized)
    if route is None:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason=f"modality {normalized} is not mapped to a platform hub route",
        )
    op = route["op"]
    if op not in compat.DISPATCHABLE:
        return ModalityBlocked(
            kind="blocked",
            modality=normalized,
            reason=f"mapped operation {op} is not compat.DISPATCHABLE",
        )
    return ModalityRoute(
        kind="route",
        modality=normalized,
        op=op,
        vendor=route["vendor"],
        profile=route["profile"],
        artifact_extension=route["artifact_extension"],
        prompt_preamble=route["prompt_preamble"],
        param_kind=route["param_kind"],
    )


__all__ = ["ModalityBlocked", "ModalityRoute", "ParamKind", "RouteKind", "resolve_modality"]
