"""Guard exception hierarchy."""

from __future__ import annotations


class GuardError(Exception):
    """Base for all guard-related exceptions."""


class UnknownActionError(GuardError):
    """Raised when ModeEnforcer.check() receives an action not in the 16 enum."""


class InvalidContextError(GuardError):
    """Raised when context dict is missing required keys for the given action."""


class CliRunnerRegistryError(GuardError):
    """Raised when CliRunnerRegistry encounters duplicate or invalid registrations."""
