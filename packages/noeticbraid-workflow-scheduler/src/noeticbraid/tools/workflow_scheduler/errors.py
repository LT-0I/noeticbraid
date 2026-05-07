"""Typed errors for the SP-E workflow scheduler package."""


class WorkflowSchedulerError(Exception):
    """Base class for package-level errors."""


class WorkflowCardError(ValueError, WorkflowSchedulerError):
    """Raised when a workflow card is invalid."""


class LedgerError(RuntimeError, WorkflowSchedulerError):
    """Raised when ledger events cannot be written or read."""


class StateStoreError(RuntimeError, WorkflowSchedulerError):
    """Raised when state cannot be read or atomically updated."""


class ExecutionDeniedError(PermissionError, WorkflowSchedulerError):
    """Raised when a step execution request violates a guard."""


class StepExecutionError(RuntimeError, WorkflowSchedulerError):
    """Raised when a step fails unexpectedly."""


class NotificationError(RuntimeError, WorkflowSchedulerError):
    """Raised when notification input is invalid."""
