"""NoeticBraid SP-H NotebookLM Bridge public API."""

from __future__ import annotations

from ._browser_ops import parse_faq, pull_briefing, pull_faq, push_sources
from ._errors import (
    NotebookLMBridgeError,
    NotebookLMExtractionError,
    NotebookLMInputError,
    NotebookLMLoginRequiredError,
    NotebookLMSelectorError,
    NotebookLMSerializationError,
    NotebookLMSessionContractError,
    NotebookLMTimeoutError,
    NotebookLMUnexpectedStateError,
)
from ._protocols import BrowserSession
from ._runlog import redact_str
from ._serializer import to_source_records

import warnings
warnings.warn(
    "noeticbraid-notebooklm-bridge is deprecated and will be removed in 0.5.0 (SDD-D5-04). "
    "Migrate to noeticbraid-notebooklm-rpc.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "BrowserSession",
    "NotebookLMBridgeError",
    "NotebookLMExtractionError",
    "NotebookLMInputError",
    "NotebookLMLoginRequiredError",
    "NotebookLMSelectorError",
    "NotebookLMSerializationError",
    "NotebookLMSessionContractError",
    "NotebookLMTimeoutError",
    "NotebookLMUnexpectedStateError",
    "parse_faq",
    "push_sources",
    "pull_briefing",
    "pull_faq",
    "redact_str",
    "to_source_records",
]
