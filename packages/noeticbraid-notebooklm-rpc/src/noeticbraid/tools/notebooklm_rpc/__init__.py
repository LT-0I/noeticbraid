"""NoeticBraid NotebookLM RPC wrapper + multi-account pool.

Pins notebooklm-py==0.4.1 (MIT).
"""

from __future__ import annotations

# Direct upstream re-export (identity-equal to upstream classes)
from notebooklm import NotebookLMClient, AuthTokens

# NoeticBraid additions
from ._pool import (
    NotebookLMAccountPool, AccountSpec, AccountRuntimeState,
    INELIGIBILITY_REASONS,
)
from ._client import account_op, run_with_pool
from ._errors import (
    NotebookLMPoolError,
    NotebookLMQuotaExceededError,
    NotebookLMAccountUnavailableError,
    NotebookLMPoolStateError,
)
from ._runlog import emit_runlog_event, PoolEventNDJSONSchema
from ._config_schema import POOL_CONFIG_SCHEMA, POOL_STATE_SCHEMA

__all__ = [
    # Upstream re-exports (2)
    "NotebookLMClient",
    "AuthTokens",
    # Pool (4)
    "NotebookLMAccountPool",
    "AccountSpec",
    "AccountRuntimeState",
    "INELIGIBILITY_REASONS",
    # Caller-facing helpers (2)
    "account_op",
    "run_with_pool",
    # Errors (4)
    "NotebookLMPoolError",
    "NotebookLMQuotaExceededError",
    "NotebookLMAccountUnavailableError",
    "NotebookLMPoolStateError",
    # Observability (2)
    "emit_runlog_event",
    "PoolEventNDJSONSchema",
    # Schemas (2)
    "POOL_CONFIG_SCHEMA",
    "POOL_STATE_SCHEMA",
]
assert len(__all__) == 16  # spec-locked
