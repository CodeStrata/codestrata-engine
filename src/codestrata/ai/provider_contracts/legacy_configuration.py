"""``LegacyConfigurationInput``: an injected snapshot of already-extracted settings values.

This module performs **pure translation only**: it never touches the
filesystem, never reads ``os.environ``, and never constructs a provider
client. Callers (production code, tests, or verification) are responsible
for extracting the relevant CLI-argument/environment-variable/
``codestrata.toml``-derived plain values *before* calling
:func:`legacy_configuration_input_from_mapping` — this module only shapes
and validates what it is given.

Nothing here is imported by ``codestrata.ai.providers.factory``,
``codestrata.application.assessment.service``, ``codestrata.ai.enrichment.
service``, ``codestrata.ai.providers.doctor``, or any CLI module. See
``configuration_projection.py`` for the function that turns a
``LegacyConfigurationInput`` into an ``AIProviderConfiguration``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

_MAX_STRING_FIELD_LENGTH = 4096


def _validate_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderContractValidationError(f"{field_name} must be a string or None")
    if len(value) > _MAX_STRING_FIELD_LENGTH:
        raise ProviderContractValidationError(
            f"{field_name} must be at most {_MAX_STRING_FIELD_LENGTH} characters"
        )
    return value


def _validate_optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProviderContractValidationError(f"{field_name} must be an int or None")
    if value < 0:
        raise ProviderContractValidationError(f"{field_name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class LegacyConfigurationInput:
    """A plain, already-extracted snapshot of the assess-relevant settings surface.

    Every field mirrors a specific, real ground-truth source (see
    ``engine/docs/ai-provider-configuration.md``):

    * ``provider`` — ``settings.ai.provider`` (e.g. ``"bedrock"``, ``"openai"``).
    * ``cli_model_id`` — the ``--model-id`` CLI argument.
    * ``env_model_id`` — the provider-appropriate environment variable value
      (``CODESTRATA_OPENAI_MODEL_ID`` or ``CODESTRATA_BEDROCK_MODEL_ID``),
      already selected by the caller based on ``provider``.
    * ``file_model_id`` — ``settings.ai.openai.answer_model`` or
      ``settings.ai.bedrock.model_id``, whichever applies.
    * ``openai_api_key_env_name`` — ``settings.ai.openai.api_key_env`` (a
      variable *name*, never a value).
    * ``openai_api_key_present`` — whether an environment variable with that
      name appears to be set (never its value).
    * ``openai_base_url_configured`` — whether ``settings.ai.openai.base_url``
      is non-blank.
    * ``bedrock_region_configured`` / ``bedrock_profile_configured`` —
      whether ``settings.aws.region``/``settings.ai.bedrock.region`` and
      ``settings.aws.profile`` are non-blank (never the values themselves).
    * ``timeout_seconds`` / ``max_retries`` — the declared-but-unwired
      ``BedrockSettings``/``OpenAISettings`` fields for the active provider.
    * ``ai_requested`` — the ``--with-ai``/``--no-ai`` CLI selection
      (``True``/``False``), or ``None`` if not yet known.
    """

    provider: str | None = None
    cli_model_id: str | None = None
    env_model_id: str | None = None
    file_model_id: str | None = None
    openai_api_key_env_name: str | None = None
    openai_api_key_present: bool = False
    openai_base_url_configured: bool = False
    bedrock_region_configured: bool = False
    bedrock_profile_configured: bool = False
    timeout_seconds: int | None = None
    max_retries: int | None = None
    ai_requested: bool | None = None

    def __post_init__(self) -> None:
        _validate_optional_string(self.provider, field_name="provider")
        _validate_optional_string(self.cli_model_id, field_name="cli_model_id")
        _validate_optional_string(self.env_model_id, field_name="env_model_id")
        _validate_optional_string(self.file_model_id, field_name="file_model_id")
        _validate_optional_string(
            self.openai_api_key_env_name, field_name="openai_api_key_env_name"
        )
        for field_name in (
            "openai_api_key_present",
            "openai_base_url_configured",
            "bedrock_region_configured",
            "bedrock_profile_configured",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ProviderContractValidationError(f"{field_name} must be a bool")
        _validate_optional_non_negative_int(self.timeout_seconds, field_name="timeout_seconds")
        _validate_optional_non_negative_int(self.max_retries, field_name="max_retries")
        if self.ai_requested is not None and not isinstance(self.ai_requested, bool):
            raise ProviderContractValidationError("ai_requested must be a bool or None")


def _mapping_get_str(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    return str(value)


def _mapping_get_bool(mapping: Mapping[str, Any], key: str) -> bool:
    return bool(mapping.get(key, False))


def _mapping_get_optional_int(mapping: Mapping[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ProviderContractValidationError(f"{key} must be an int, not a bool")
    return int(value)


def legacy_configuration_input_from_mapping(
    mapping: Mapping[str, Any],
) -> LegacyConfigurationInput:
    """Translate a plain mapping of already-extracted values into a ``LegacyConfigurationInput``.

    ``mapping`` is expected to use the same key names as
    ``LegacyConfigurationInput``'s fields (unknown keys are ignored). This
    function performs no filesystem access, no environment variable reads,
    and constructs no provider client — the caller must have already
    extracted every value from wherever it actually lives (CLI arguments,
    ``os.environ``, a loaded ``CodestrataSettings`` instance) before calling
    this function.
    """

    if not isinstance(mapping, Mapping):
        raise ProviderContractValidationError("mapping must be a Mapping")

    ai_requested_raw = mapping.get("ai_requested")
    ai_requested = None if ai_requested_raw is None else bool(ai_requested_raw)

    return LegacyConfigurationInput(
        provider=_mapping_get_str(mapping, "provider"),
        cli_model_id=_mapping_get_str(mapping, "cli_model_id"),
        env_model_id=_mapping_get_str(mapping, "env_model_id"),
        file_model_id=_mapping_get_str(mapping, "file_model_id"),
        openai_api_key_env_name=_mapping_get_str(mapping, "openai_api_key_env_name"),
        openai_api_key_present=_mapping_get_bool(mapping, "openai_api_key_present"),
        openai_base_url_configured=_mapping_get_bool(mapping, "openai_base_url_configured"),
        bedrock_region_configured=_mapping_get_bool(mapping, "bedrock_region_configured"),
        bedrock_profile_configured=_mapping_get_bool(mapping, "bedrock_profile_configured"),
        timeout_seconds=_mapping_get_optional_int(mapping, "timeout_seconds"),
        max_retries=_mapping_get_optional_int(mapping, "max_retries"),
        ai_requested=ai_requested,
    )


__all__ = [
    "LegacyConfigurationInput",
    "legacy_configuration_input_from_mapping",
]
