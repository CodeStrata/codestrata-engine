"""Settings builder for MVP acceptance (Phase 5.13)."""

from __future__ import annotations

from pathlib import Path

from codestrata.config import load_settings
from codestrata.config.settings import CodestrataSettings


def build_acceptance_settings(
    *,
    repository_path: Path,
    work_root: Path,
    config_path: Path | None = None,
    base: CodestrataSettings | None = None,
) -> CodestrataSettings:
    """Build isolated settings for live onboard + MCP + grounded answers.

    Enables knowledge retrieval/answering and MCP without mutating codestrata.toml.
    Uses deterministic embedding/answer providers and an in-memory vector store.
    """

    loaded = base if base is not None else load_settings(config_path or Path("codestrata.toml"))
    knowledge_dir = work_root / "knowledge"
    workspace_dir = work_root / "workspace"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    knowledge = loaded.knowledge.model_copy(deep=True)
    knowledge = knowledge.model_copy(
        update={
            "enabled": True,
            "directory": str(knowledge_dir),
            "projection": knowledge.projection.model_copy(
                update={
                    "enabled": True,
                    "write_corpus_artifact": True,
                }
            ),
            "chunking": knowledge.chunking.model_copy(update={"enabled": True}),
            "embedding": knowledge.embedding.model_copy(
                update={
                    "enabled": True,
                    "provider": "deterministic",
                }
            ),
            "indexing": knowledge.indexing.model_copy(
                update={
                    "enabled": True,
                    "write_manifest": True,
                }
            ),
            "retrieval": knowledge.retrieval.model_copy(update={"enabled": True}),
            "answering": knowledge.answering.model_copy(
                update={
                    "enabled": True,
                    "provider": "deterministic_extractive",
                    "fail_on_insufficient_evidence": False,
                }
            ),
            "vector_store": knowledge.vector_store.model_copy(update={"provider": "memory"}),
        }
    )
    ai = loaded.ai.model_copy(
        update={
            "embedding_provider": "deterministic",
            "answer_provider": "deterministic_extractive",
        }
    )
    mcp = loaded.mcp.model_copy(
        update={
            "enabled": True,
            "transport": "stdio",
        }
    )
    static_analysis = loaded.static_analysis.model_copy(update={"enabled": False})
    report = loaded.report.model_copy(deep=True)
    report = report.model_copy(
        update={
            "sections": report.sections.model_copy(
                update={"roadmap": report.sections.roadmap.model_copy(update={"enabled": True})}
            )
        }
    )
    return loaded.model_copy(
        update={
            "repository": loaded.repository.model_copy(update={"path": str(repository_path)}),
            "workspace": loaded.workspace.model_copy(update={"directory": str(workspace_dir)}),
            "knowledge": knowledge,
            "ai": ai,
            "mcp": mcp,
            "static_analysis": static_analysis,
            "report": report,
        }
    )
