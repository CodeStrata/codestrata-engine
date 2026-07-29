"""Transport-neutral Agent Framework errors."""

from __future__ import annotations


class AgentError(Exception):
    """Base error for the Agent Framework."""


class AgentConfigurationError(AgentError):
    """Raised when agent policy or composition is invalid."""


class AgentExecutionError(AgentError):
    """Raised when a workflow fails during execution."""


class AgentStepError(AgentExecutionError):
    """Raised when a single agent step fails."""


class AgentValidationError(AgentError):
    """Raised when validation cannot complete."""


class AgentDependencyError(AgentError):
    """Raised when a required application dependency is unavailable."""


class AgentEvidenceError(AgentError):
    """Raised when evidence cannot be grounded or assembled."""


class AgentWorkflowBlockedError(AgentError):
    """Raised when blocking validation issues stop a workflow."""
