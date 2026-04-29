"""Cross-module Protocol definitions for guard.

This module is the GPT-C / GPT-B decoupling boundary. GPT-C does NOT import
the GPT-B ledger package. GPT-B's RunLedger satisfies LedgerSink via structural
subtyping (no inheritance). Stage 3 integration injects a RunLedger instance
into ModeEnforcer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from noeticbraid_core.schemas import RunRecord


@runtime_checkable
class LedgerSink(Protocol):
    """Append-only ledger sink Protocol.

    Phase 1.1 default = _NoOpLedgerSink (in-package).
    Stage 3 integration: local main session injects GPT-B RunLedger.
    """

    def append(self, record: RunRecord) -> None: ...


class _NoOpLedgerSink:
    """Default no-op LedgerSink. Stage 3 replaces with real RunLedger.

    Satisfies LedgerSink Protocol via structural subtyping.
    """

    def append(self, record: RunRecord) -> None:  # noqa: ARG002
        return None
