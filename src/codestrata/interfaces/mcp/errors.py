"""Translate application errors into safe MCP ToolError messages."""

from __future__ import annotations

import logging
from typing import NoReturn

from mcp.server.fastmcp.exceptions import ToolError

from codestrata.application.agents.errors import (
    AgentConfigurationError,
    AgentDependencyError,
    AgentError,
    AgentEvidenceError,
    AgentExecutionError,
    AgentStepError,
    AgentValidationError,
    AgentWorkflowBlockedError,
)
from codestrata.application.assessment import AssessmentCommandError
from codestrata.application.incremental.errors import IncrementalPlanningError
from codestrata.application.knowledge.errors import (
    KnowledgeStoreError,
    RepositoryIdentityError,
)
from codestrata.application.knowledge.queries.errors import KnowledgeQueryError
from codestrata.application.rules.errors import RuleApplicationError
from codestrata.interfaces.mcp.security import sanitize_error_message

logger = logging.getLogger("codestrata.interfaces.mcp")


def _is_platform_application_error(error: BaseException) -> bool:
    """Treat Platform application errors as safe client-facing failures."""

    module = type(error).__module__
    return module.startswith("codestrata_platform.")


def raise_tool_error(error: BaseException, *, tool_name: str) -> NoReturn:
    """Raise a sanitized ToolError for MCP clients."""

    if isinstance(
        error,
        (
            KnowledgeQueryError,
            AssessmentCommandError,
            KnowledgeStoreError,
            RepositoryIdentityError,
            AgentConfigurationError,
            AgentDependencyError,
            AgentExecutionError,
            AgentStepError,
            AgentValidationError,
            AgentEvidenceError,
            AgentWorkflowBlockedError,
            AgentError,
            IncrementalPlanningError,
            RuleApplicationError,
            ValueError,
        ),
    ) or _is_platform_application_error(error):
        message = sanitize_error_message(str(error) or error.__class__.__name__)
        logger.info("mcp_tool_error tool=%s type=%s", tool_name, type(error).__name__)
        raise ToolError(message) from None

    logger.exception("mcp_internal_error tool=%s", tool_name)
    raise ToolError("Internal CodeStrata error") from None


def call_tool(tool_name: str, operation: object) -> object:
    """Execute a tool body and translate failures."""

    try:
        return operation()  # type: ignore[operator]
    except ToolError:
        raise
    except Exception as error:  # noqa: BLE001 - MCP boundary
        raise_tool_error(error, tool_name=tool_name)
