"""Effective non-secret configuration views (Phase 5.20)."""

from __future__ import annotations

import os
from typing import Any

from codestrata.config.profiles import (
    PROFILE_ENV_VAR,
    ProfileSource,
    _resolved_bedrock_region,
)
from codestrata.config.settings import CodestrataSettings
from codestrata.security.database_url import redact_database_url
from codestrata.security.redaction import redact_secrets


def _api_key_present(env_name: str, *, environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else dict(os.environ)
    return bool(str(env.get(env_name, "") or "").strip())


def build_effective_settings(
    settings: CodestrataSettings,
    *,
    profile: str | None = None,
    profile_source: ProfileSource | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable effective settings view with secrets redacted.

    Never includes API key values, AWS secret keys, or raw database URLs.
    """

    env = environ if environ is not None else dict(os.environ)
    active_profile = profile or settings.profile
    api_key_env = settings.ai.openai.api_key_env
    connection_env = settings.knowledge.vector_store.connection_string_env
    raw_connection = settings.knowledge.vector_store.connection_string
    connection_present = bool(raw_connection.strip()) or _api_key_present(
        connection_env, environ=env
    )

    payload: dict[str, Any] = {
        "profile": {
            "name": active_profile,
            "source": profile_source or "configuration",
            "selection_env": PROFILE_ENV_VAR,
        },
        "edition": {
            "community": not settings.enterprise.enabled,
            "enterprise_enabled": settings.enterprise.enabled,
        },
        "repository": {
            "path": settings.repository.path,
            "url": str(settings.repository.url) if settings.repository.url else None,
            "branch": settings.repository.branch,
            "authentication_type": (
                str(settings.repository.authentication.type)
                if settings.repository.authentication
                else None
            ),
            "token_env": (
                settings.repository.authentication.token_env
                if settings.repository.authentication
                else None
            ),
        },
        "workspace": {
            "directory": str(settings.workspace.directory),
            "clean_before_clone": settings.workspace.clean_before_clone,
        },
        "aws": {
            "profile": settings.aws.profile,
            "region": settings.aws.region,
            "resolved_region": _resolved_bedrock_region(settings, environ=env),
            "credentials": "default_chain",
        },
        "ai": {
            "provider": settings.ai.provider,
            "embedding_provider": settings.ai.embedding_provider,
            "answer_provider": settings.ai.answer_provider,
            "bedrock": {
                "model_id": settings.ai.bedrock.model_id,
                "region": settings.ai.bedrock.region,
                "embedding_model": settings.ai.bedrock.embedding_model,
                "answer_model": settings.ai.bedrock.answer_model,
                "timeout_seconds": settings.ai.bedrock.timeout_seconds,
                "max_retries": settings.ai.bedrock.max_retries,
            },
            "openai": {
                "api_key_env": api_key_env,
                "api_key_present": _api_key_present(api_key_env, environ=env),
                "base_url": settings.ai.openai.base_url or None,
                "embedding_model": settings.ai.openai.embedding_model,
                "answer_model": settings.ai.openai.answer_model,
                "embedding_dimensions": settings.ai.openai.embedding_dimensions or None,
                "timeout_seconds": settings.ai.openai.timeout_seconds,
                "max_retries": settings.ai.openai.max_retries,
            },
        },
        "knowledge": {
            "enabled": settings.knowledge.enabled,
            "directory": str(settings.knowledge.directory),
            "embedding_enabled": settings.knowledge.embedding.enabled,
            "indexing_enabled": settings.knowledge.indexing.enabled,
            "retrieval_enabled": settings.knowledge.retrieval.enabled,
            "answering_enabled": settings.knowledge.answering.enabled,
            "vector_store": {
                "provider": settings.knowledge.vector_store.provider,
                "schema": settings.knowledge.vector_store.schema_name,
                "connection_string_env": connection_env,
                "connection_configured": connection_present,
                "connection_string": (
                    redact_database_url(raw_connection) if raw_connection.strip() else None
                ),
            },
        },
        "enterprise": {
            "enabled": settings.enterprise.enabled,
            "workspace": settings.enterprise.workspace,
        },
        "mcp": {
            "enabled": settings.mcp.enabled,
            "transport": settings.mcp.transport,
            "host": settings.mcp.host,
            "port": settings.mcp.port,
        },
        "analysis": {
            "runtime": {
                "shared_source_text_cache": (
                    settings.analysis.runtime.shared_source_text_cache
                ),
                "max_read_workers": settings.analysis.runtime.max_read_workers,
                "max_source_files": settings.analysis.runtime.max_source_files,
                "max_source_chars": settings.analysis.runtime.max_source_chars,
            }
        },
        "static_analysis": {
            "enabled": settings.static_analysis.enabled,
            "pmd_enabled": settings.static_analysis.pmd.enabled,
            "pmd_profile": settings.static_analysis.pmd.profile,
        },
    }
    # Defense in depth: run pattern redaction over serialized strings.
    redacted = _redact_tree(payload)
    assert isinstance(redacted, dict)
    return redacted


def _redact_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    if isinstance(value, str):
        return redact_secrets(value)
    return value


__all__ = ["build_effective_settings"]
