"""Typed helpers for NotebookLM bridge internals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["url", "text"]
OperationStatus = Literal["started", "succeeded", "failed"]
OperationName = Literal["push_sources", "pull_briefing", "pull_faq"]


@dataclass(frozen=True)
class NormalizedSource:
    """Validated source accepted by ``push_sources``."""

    kind: SourceKind
    content: str
    title: str | None = None


@dataclass(frozen=True)
class OperationEvent:
    """Internal operation event before conversion to a RunRecord-compatible dict."""

    operation: OperationName
    status: OperationStatus
    notebook_id: str
    run_id: str | None = None
    task_id: str | None = None
    message: str | None = None
    source_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    routing_advice: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", tuple(self.source_refs))
        object.__setattr__(self, "artifact_refs", tuple(self.artifact_refs))
