"""Provider and model-ID resolution as pure, injected-input functions.

Mirrors the exact resolution order of
``codestrata.ai.providers.factory.resolve_assess_model_id`` and the
``[ai].provider`` selection already performed by
``codestrata.ai.providers.factory.create_assess_ai_provider`` — but as
side-effect-free functions that take already-extracted candidate values as
arguments. **No function in this module reads ``os.environ`` or any file.**
Callers are responsible for extracting the relevant environment
variable/CLI-argument/settings values before calling these functions (see
``legacy_configuration.py`` for one such caller).
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.configuration_policy import (
    DEFAULT_MODEL_BY_PROVIDER,
    DEFAULT_PROVIDER_ID,
)
from codestrata.ai.provider_contracts.configuration_precedence import select_first_present
from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId, ProviderModelReference

# Re-exported so callers building an AIProviderConfiguration do not need to
# import configuration_policy directly for these two well-known constants.
DEFAULT_PROVIDER_ID_VALUE: str = DEFAULT_PROVIDER_ID
DEFAULT_MODEL_ID_BY_PROVIDER: dict[str, str] = dict(DEFAULT_MODEL_BY_PROVIDER)


def default_model_id_for_provider(provider_id: ProviderId) -> str:
    """Return the hardcoded default model ID for ``provider_id``."""

    try:
        return DEFAULT_MODEL_ID_BY_PROVIDER[provider_id.value]
    except KeyError as error:
        raise ProviderContractValidationError(
            f"no default model ID is declared for provider_id {provider_id!r}"
        ) from error


def resolve_provider_id(*, file_provider: str | None) -> tuple[ProviderId, SourceCategory]:
    """Resolve the active provider the same way ``create_assess_ai_provider`` does.

    ``codestrata assess`` has no ``--provider`` CLI flag and no dedicated
    provider-selection environment variable today (see
    ``configuration_precedence.FIELD_PRECEDENCE_NOTES["provider_id"]``), so
    the only two levels that apply are the configuration file value and the
    hardcoded default.
    """

    value, source = select_first_present(
        candidates=((file_provider, SourceCategory.CONFIGURATION_FILE),),
        default=DEFAULT_PROVIDER_ID_VALUE,
        default_source=SourceCategory.DEFAULT,
    )
    normalized = value.strip().lower()
    try:
        return ProviderId(normalized), source
    except ValueError as error:
        raise ProviderContractValidationError(
            f"unsupported provider id {normalized!r}; expected one of "
            f"{tuple(p.value for p in ProviderId)}"
        ) from error


def resolve_model_reference(
    *,
    provider_id: ProviderId,
    cli_model_id: str | None,
    env_model_id: str | None,
    file_model_id: str | None,
) -> tuple[ProviderModelReference, SourceCategory]:
    """Resolve the effective model ID exactly as ``resolve_assess_model_id`` does.

    Order: ``cli_model_id`` (``--model-id``) > ``env_model_id`` (the
    provider-appropriate ``CODESTRATA_OPENAI_MODEL_ID`` /
    ``CODESTRATA_BEDROCK_MODEL_ID`` value, already selected by the caller)
    > ``file_model_id`` (``[ai.openai].answer_model`` /
    ``[ai.bedrock].model_id``) > the hardcoded default for ``provider_id``.
    """

    if not isinstance(provider_id, ProviderId):
        raise ProviderContractValidationError(
            f"provider_id must be a ProviderId, got {type(provider_id).__name__}"
        )
    value, source = select_first_present(
        candidates=(
            (cli_model_id, SourceCategory.CLI),
            (env_model_id, SourceCategory.ENVIRONMENT),
            (file_model_id, SourceCategory.CONFIGURATION_FILE),
        ),
        default=default_model_id_for_provider(provider_id),
        default_source=SourceCategory.DEFAULT,
    )
    return ProviderModelReference(value), source


__all__ = [
    "DEFAULT_MODEL_ID_BY_PROVIDER",
    "DEFAULT_PROVIDER_ID_VALUE",
    "default_model_id_for_provider",
    "resolve_model_reference",
    "resolve_provider_id",
]
