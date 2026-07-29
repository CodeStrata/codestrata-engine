"""Injected services for MCP tools.

Repository-intelligence (RAG) context is provided by Platform when installed.
Community MCP always has knowledge query/assessment services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codestrata.application.knowledge.queries import KnowledgeQueryService
from codestrata.config import CodestrataSettings, McpSettings, McpToolsSettings


@dataclass
class RepositoryIntelligenceContext:
    """Optional RAG DI bundle.

    Community builds leave retriever/answer/embedding/vector fields unset.
    Platform MCP extensions populate them when registered.
    """

    queries: KnowledgeQueryService
    settings: CodestrataSettings | None = None
    mcp: McpSettings = field(default_factory=McpSettings)
    retriever: Any | None = None
    answer_engine: Any | None = None
    answer_provider: Any | None = None
    embedding_provider: Any | None = None
    vector_store: Any | None = None
    vector_store_provider: str = "memory"
    vector_store_persistent: bool = False
    composition_diagnostics: tuple[dict[str, Any], ...] = ()

    @property
    def tools(self) -> McpToolsSettings:
        return self.mcp.tools

    def tool_enabled(self, tool_key: str) -> bool:
        return bool(getattr(self.tools, tool_key, False))
