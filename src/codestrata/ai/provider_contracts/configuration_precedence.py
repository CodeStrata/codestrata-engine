"""Generic CLI > environment > configuration-file > default precedence.

This module encodes the *shape* of the real ``codestrata assess`` precedence
chain (see ``codestrata.ai.providers.factory.resolve_assess_model_id`` and
``codestrata.ai.aws_config.resolve_aws_config``) as a small, pure, reusable
helper. It does not read ``os.environ``, does not read any file, and does
not know about any specific settings field — callers (``model_configuration.
py``, ``legacy_configuration.py``) pass in already-extracted candidate
values.

Not every configuration field is resolved through every level of this
chain. ``FIELD_PRECEDENCE_NOTES`` documents, per field, exactly which levels
apply today — this is important because it would be inaccurate to claim
(for example) that ``provider_id`` has a CLI override, since
``codestrata assess`` has no ``--provider`` flag.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

# The canonical precedence order, highest priority first. Matches the
# ordering already documented on resolve_assess_model_id/resolve_aws_config:
# CLI wins over environment, environment wins over the configuration file,
# and the configuration file wins over a hardcoded default.
PRECEDENCE_ORDER: tuple[SourceCategory, ...] = (
    SourceCategory.CLI,
    SourceCategory.ENVIRONMENT,
    SourceCategory.CONFIGURATION_FILE,
    SourceCategory.DEFAULT,
)

# Field-specific notes, kept here (rather than assumed) because not every
# field is overridable at every level. See engine/docs/ai-provider-configuration.md
# for the ground-truth source that each note restates.
FIELD_PRECEDENCE_NOTES: dict[str, str] = {
    "provider_id": (
        "Resolved from the codestrata.toml [ai].provider value, or the "
        "'bedrock' default. codestrata assess has no --provider CLI flag "
        "and no dedicated provider-selection environment variable today."
    ),
    "model_reference": (
        "CLI --model-id wins over the provider-specific environment variable "
        "(CODESTRATA_OPENAI_MODEL_ID for openai, CODESTRATA_BEDROCK_MODEL_ID "
        "for bedrock), which wins over the configuration file value "
        "([ai.openai].answer_model / [ai.bedrock].model_id), which wins over "
        "the hardcoded default (gpt-4o-mini / amazon.nova-lite-v1:0). Note: "
        "CODESTRATA_OPENAI_MODEL_ID is read only at model-resolution time, "
        "not overlaid into settings; CODESTRATA_BEDROCK_MODEL_ID is both "
        "overlaid into settings and read again at resolution time — both "
        "behaviors are preserved unchanged by this slice."
    ),
    "aws_profile": (
        "Explicit argument > AWS_PROFILE environment variable > "
        "[aws].profile configuration file value > boto3 default credential "
        "chain (no configuration-domain default value)."
    ),
    "aws_region": (
        "Explicit argument > AWS_REGION/AWS_DEFAULT_REGION environment "
        "variables > [aws].region, then [ai.bedrock].region, configuration "
        "file values > boto3 default region chain (no configuration-domain "
        "default value)."
    ),
    "timeout_seconds": (
        "Declared on [ai.bedrock]/[ai.openai] settings but NOT read by the "
        "assess provider factory; there is no CLI or environment override "
        "path today. Represented here as a configuration-file-or-absent "
        "value only, and never wired to execution by this slice."
    ),
    "max_retries": (
        "Declared on [ai.bedrock]/[ai.openai] settings but NOT read by the "
        "assess provider factory; there is no CLI or environment override "
        "path today. Represented here as a configuration-file-or-absent "
        "value only, and never wired to execution by this slice."
    ),
}


def select_first_present(
    *,
    candidates: tuple[tuple[str | None, SourceCategory], ...],
    default: str,
    default_source: SourceCategory = SourceCategory.DEFAULT,
) -> tuple[str, SourceCategory]:
    """Return the first non-blank candidate value, in the given precedence order.

    ``candidates`` must already be ordered highest-precedence first (e.g.
    CLI before environment before configuration file) — this function does
    not reorder them. A candidate is used only if it is a non-``None``,
    non-blank-after-``strip()`` string.
    """

    if default_source not in PRECEDENCE_ORDER:
        raise ProviderContractValidationError(
            f"default_source must be one of {PRECEDENCE_ORDER}, got {default_source!r}"
        )
    for value, source in candidates:
        if source not in PRECEDENCE_ORDER:
            raise ProviderContractValidationError(
                f"candidate source must be one of {PRECEDENCE_ORDER}, got {source!r}"
            )
        if value is not None and value.strip():
            return value.strip(), source
    if not isinstance(default, str) or not default.strip():
        raise ProviderContractValidationError("default must be a non-empty string")
    return default.strip(), default_source


__all__ = [
    "FIELD_PRECEDENCE_NOTES",
    "PRECEDENCE_ORDER",
    "select_first_present",
]
