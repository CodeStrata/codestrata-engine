"""Mixed mode: both providers share one registry and one legacy seam.

Slice 11.6 introduced these tests to pin "OpenAI is migrated, Bedrock is
not". Slice 11.7 migrated Bedrock, so what remains falsifiable here is that
provider *selection* is unchanged, that both providers still answer the same
legacy interface, and that Slice 11.6's OpenAI work never became a Bedrock
dependency. Bedrock's own adapter is covered by
``tests/ai/provider_adapters/bedrock/``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from codestrata.ai.providers import bedrock as bedrock_module
from codestrata.ai.providers.factory import create_assess_ai_provider
from codestrata.config import CodestrataSettings
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)


def _settings(provider: str) -> CodestrataSettings:
    payload: dict[str, object] = {"repository": {"path": "."}, "ai": {"provider": provider}}
    return CodestrataSettings.model_validate(payload)


def _bedrock_source() -> str:
    return Path(bedrock_module.__file__).read_text(encoding="utf-8")


def _is_provider_class(provider: object, expected: type) -> bool:
    """Compare by qualified name so a module reload cannot break isinstance."""

    actual = type(provider)
    return (actual.__module__, actual.__name__) == (expected.__module__, expected.__name__)


def test_default_provider_is_still_bedrock() -> None:
    settings = CodestrataSettings.model_validate({"repository": {"path": "."}})

    assert settings.ai.provider == "bedrock"
    assert _is_provider_class(create_assess_ai_provider(settings), bedrock_module.BedrockAIModelProvider)


def test_both_providers_remain_registered_under_the_same_keys() -> None:
    reset_assess_ai_provider_registry_for_tests()
    try:
        assert get_assess_ai_provider_registry().list_providers() == ("bedrock", "openai", "openrouter")
    finally:
        reset_assess_ai_provider_registry_for_tests()


def test_openai_selection_returns_the_migrated_wrapper() -> None:
    from codestrata.ai.providers import openai_provider as openai_module

    provider = create_assess_ai_provider(_settings("openai"))
    assert _is_provider_class(provider, openai_module.OpenAIAIModelProvider)


def test_bedrock_still_invokes_converse_on_its_client() -> None:
    from codestrata.ai.prompts import ModernizationPromptBuilder
    from codestrata.ai.providers.models import (
        ModelInvocationOptions,
        ModernizationModelRequest,
    )
    from codestrata.ai.recommendations import ai_recommendation_result_to_json
    from tests.ai.test_ai_model_providers import _context, _converse_response, _valid_result

    context = _context("SEC001", "SEC002")
    client = MagicMock()
    client.converse.return_value = _converse_response(
        ai_recommendation_result_to_json(_valid_result(), indent=None)
    )

    result = bedrock_module.BedrockAIModelProvider(client=client).invoke(
        ModernizationModelRequest(
            prompt_request=ModernizationPromptBuilder().build(context),
            analysis_context=context,
        ),
        ModelInvocationOptions(model_id="us.amazon.nova-pro-v1:0"),
    )

    client.converse.assert_called_once()
    assert result.metadata.provider == "bedrock"
    assert result.recommendation_result is not None


def test_bedrock_never_imports_the_openai_adapter() -> None:
    """Bedrock reaches the contracts through its own adapter, never OpenAI's."""

    tree = ast.parse(_bedrock_source())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(
        name.startswith("codestrata.ai.provider_adapters.openai") for name in imported
    )
    assert not any(
        name.startswith("codestrata.ai.providers.openai_provider") for name in imported
    )
    assert any(
        name.startswith("codestrata.ai.provider_adapters.bedrock") for name in imported
    )


def test_bedrock_source_invariants_hold() -> None:
    """Bedrock keeps its public surface, gains no retry helper, and stays OpenRouter-free."""

    source = _bedrock_source()

    assert "def invoke(" in source
    assert "build_converse_request" in source
    assert "split_prompt_for_converse" in source
    assert "extract_converse_response" in source
    assert "retry_call" not in source
    assert "openrouter" not in source.lower()


def test_bedrock_module_exports_are_unchanged() -> None:
    assert hasattr(bedrock_module, "BedrockAIModelProvider")
    assert hasattr(bedrock_module, "BEDROCK_PROVIDER_NAME")
    assert bedrock_module.BEDROCK_PROVIDER_NAME == "bedrock"
