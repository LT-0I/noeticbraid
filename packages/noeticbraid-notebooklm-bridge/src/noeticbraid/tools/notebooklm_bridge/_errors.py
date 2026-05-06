"""Typed exceptions for the NotebookLM bridge."""

from __future__ import annotations


class NotebookLMBridgeError(Exception):
    """Base class for all NotebookLM bridge failures."""


class NotebookLMInputError(NotebookLMBridgeError, ValueError):
    """Raised when public API input is invalid."""


class NotebookLMSessionContractError(NotebookLMBridgeError, TypeError):
    """Raised when the supplied BrowserSession does not satisfy SP-C2 expectations."""


class NotebookLMSelectorError(NotebookLMBridgeError, LookupError):
    """Raised when selector configuration is missing or malformed."""


class NotebookLMLoginRequiredError(NotebookLMBridgeError):
    """Raised when NotebookLM asks the user for login, MFA, CAPTCHA, or terms action."""


class NotebookLMTimeoutError(NotebookLMBridgeError, TimeoutError):
    """Raised when NotebookLM UI generation/readiness exceeds the configured timeout."""


class NotebookLMUnexpectedStateError(NotebookLMBridgeError):
    """Raised when the visible UI state does not match the expected operation flow."""


class NotebookLMExtractionError(NotebookLMBridgeError):
    """Raised when generated NotebookLM content cannot be extracted or parsed."""


class NotebookLMSerializationError(NotebookLMBridgeError):
    """Raised when frozen-contract serialization cannot be satisfied."""
