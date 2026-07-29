"""Factory for assess / Modernization Advisor AI model providers."""

from __future__ import annotations

import os

from codestrata.ai.providers.base import AIModelProvider
from codestrata.config.settings import DEFAULT_BEDROCK_MODEL_ID, CodestrataSettings
from codestrata.extensions.assess_ai import get_assess_ai_provider_registry

CODESTRATA_BEDROCK_MODEL_ID_ENV = "CODESTRATA_BEDROCK_MODEL_ID"
CODESTRATA_OPENAI_MODEL_ID_ENV = "CODESTRATA_OPENAI_MODEL_ID"


def supported_assess_ai_providers() -> frozenset[str]:
    """Return currently registered assess AI provider names."""

    return frozenset(get_assess_ai_provider_registry().list_providers())


# Back-compat: historically a frozenset constant of built-ins.
SUPPORTED_ASSESS_AI_PROVIDERS = frozenset({"bedrock", "openai"})


def create_assess_ai_provider(settings: CodestrataSettings) -> AIModelProvider:
    """Create the AI model provider selected by ``[ai].provider`` for assess."""

    provider_name = (settings.ai.provider or "bedrock").strip().lower()
    return get_assess_ai_provider_registry().create(provider_name, settings)


def resolve_assess_model_id(
    *,
    cli_model_id: str | None,
    settings: CodestrataSettings,
) -> str:
    """Resolve assess enrichment model ID for the active provider."""

    if cli_model_id and cli_model_id.strip():
        return cli_model_id.strip()

    provider_name = (settings.ai.provider or "bedrock").strip().lower()
    if provider_name == "openai":
        env_model = os.environ.get(CODESTRATA_OPENAI_MODEL_ID_ENV)
        if env_model and env_model.strip():
            return env_model.strip()
        configured = (settings.ai.openai.answer_model or "").strip()
        if configured:
            return configured
        return "gpt-4o-mini"

    env_model_id = os.environ.get(CODESTRATA_BEDROCK_MODEL_ID_ENV)
    if env_model_id and env_model_id.strip():
        return env_model_id.strip()
    configured = (settings.ai.bedrock.model_id or "").strip()
    if configured:
        return configured
    return DEFAULT_BEDROCK_MODEL_ID


# Back-compat alias used by older call sites / docs.
resolve_bedrock_model_id = resolve_assess_model_id

__all__ = [
    "CODESTRATA_BEDROCK_MODEL_ID_ENV",
    "CODESTRATA_OPENAI_MODEL_ID_ENV",
    "SUPPORTED_ASSESS_AI_PROVIDERS",
    "create_assess_ai_provider",
    "resolve_assess_model_id",
    "resolve_bedrock_model_id",
    "supported_assess_ai_providers",
]
