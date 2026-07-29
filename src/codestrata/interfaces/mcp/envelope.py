"""MCP envelope models and schemas (Phase 5.7).

Kept in the interface layer so MCP SDK types never leak into domain packages.
Schema *names* are versioned independently from application DTOs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.graph.validation import as_tuple, optional_nonblank, require_nonblank
from codestrata.domain.knowledge.identifiers import fingerprint_payload
from codestrata.domain.knowledge.schemas import (
    MCP_HEALTH_RESPONSE_SCHEMA_NAME,
    MCP_HEALTH_RESPONSE_SCHEMA_VERSION,
    MCP_SERVER_MANIFEST_SCHEMA_NAME,
    MCP_SERVER_MANIFEST_SCHEMA_VERSION,
    MCP_TOOL_RESPONSE_SCHEMA_NAME,
    MCP_TOOL_RESPONSE_SCHEMA_VERSION,
)


class McpToolStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    DISABLED = "disabled"
    FAILED = "failed"


class McpDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    severity: str = "info"

    @field_validator("code", "message", "severity", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="mcp diagnostic field")


class McpCoverage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result_count: int = Field(default=0, ge=0)
    result_characters: int = Field(default=0, ge=0)
    truncated: bool = False
    excluded_count: int = Field(default=0, ge=0)
    extras: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extras", mode="before")
    @classmethod
    def normalize_extras(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("extras must be a mapping")
        return dict(value)


class McpToolResponse(BaseModel):
    """Common structured envelope for repository-intelligence MCP tools."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = MCP_TOOL_RESPONSE_SCHEMA_NAME
    schema_version: str = MCP_TOOL_RESPONSE_SCHEMA_VERSION
    request_id: str
    tool_name: str
    status: McpToolStatus
    data: dict[str, Any] = Field(default_factory=dict)
    coverage: McpCoverage = Field(default_factory=McpCoverage)
    diagnostics: tuple[McpDiagnostic, ...] = ()
    limitations: tuple[str, ...] = ()
    generated_at: str = "deterministic"
    fingerprint: str

    @field_validator("request_id", "tool_name", "fingerprint", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="mcp tool response field")

    @field_validator("diagnostics", mode="before")
    @classmethod
    def normalize_diagnostics(cls, value: object) -> tuple[McpDiagnostic, ...]:
        if value is None:
            return ()
        items = as_tuple(value)
        return tuple(
            item if isinstance(item, McpDiagnostic) else McpDiagnostic.model_validate(item)
            for item in items
        )

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item) for item in as_tuple(value))

    @field_validator("data", mode="before")
    @classmethod
    def normalize_data(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("data must be a mapping")
        return dict(value)


class McpHealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = MCP_HEALTH_RESPONSE_SCHEMA_NAME
    schema_version: str = MCP_HEALTH_RESPONSE_SCHEMA_VERSION
    status: McpToolStatus
    server_name: str
    server_version: str
    transport: str
    retrieval_available: bool = False
    answering_available: bool = False
    vector_store_provider: str | None = None
    vector_store_healthy: bool | None = None
    vector_store_persistent: bool = False
    embedding_provider: dict[str, Any] = Field(default_factory=dict)
    answer_provider: dict[str, Any] = Field(default_factory=dict)
    enabled_capabilities: tuple[str, ...] = ()
    disabled_capabilities: tuple[str, ...] = ()
    diagnostics: tuple[McpDiagnostic, ...] = ()
    fingerprint: str

    @field_validator(
        "server_name",
        "server_version",
        "transport",
        "fingerprint",
        mode="before",
    )
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="mcp health field")


class McpServerManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = MCP_SERVER_MANIFEST_SCHEMA_NAME
    schema_version: str = MCP_SERVER_MANIFEST_SCHEMA_VERSION
    server_name: str
    server_version: str
    transport: str
    tools: tuple[str, ...] = ()
    tool_versions: dict[str, str] = Field(default_factory=dict)
    fingerprint: str

    @field_validator("server_name", "server_version", "transport", "fingerprint", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="mcp manifest field")

    @field_validator("tools", mode="before")
    @classmethod
    def normalize_tools(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(str(item) for item in as_tuple(value))


def build_request_id(*, tool_name: str, payload: Mapping[str, Any]) -> str:
    return "mcp:" + fingerprint_payload({"tool": tool_name, "payload": dict(payload)})[:24]


def build_response_fingerprint(
    *,
    tool_name: str,
    status: McpToolStatus,
    data: Mapping[str, Any],
    coverage: McpCoverage,
) -> str:
    return fingerprint_payload(
        {
            "tool": tool_name,
            "status": status.value,
            "data": dict(data),
            "coverage": coverage.model_dump(mode="json"),
        }
    )


def envelope(
    *,
    tool_name: str,
    status: McpToolStatus,
    data: Mapping[str, Any] | None = None,
    coverage: McpCoverage | None = None,
    diagnostics: Sequence[McpDiagnostic] = (),
    limitations: Sequence[str] = (),
    request_payload: Mapping[str, Any] | None = None,
) -> McpToolResponse:
    payload = dict(data or {})
    cov = coverage or McpCoverage()
    request_id = build_request_id(tool_name=tool_name, payload=request_payload or payload)
    fingerprint = build_response_fingerprint(
        tool_name=tool_name,
        status=status,
        data=payload,
        coverage=cov,
    )
    return McpToolResponse(
        request_id=request_id,
        tool_name=tool_name,
        status=status,
        data=payload,
        coverage=cov,
        diagnostics=tuple(diagnostics),
        limitations=tuple(limitations),
        fingerprint=fingerprint,
    )


def optional_scope_field(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    return optional_nonblank(str(value), label=label)
