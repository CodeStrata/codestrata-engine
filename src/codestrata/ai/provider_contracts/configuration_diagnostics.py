"""Safe, privacy-preserving diagnostic views of an ``AIProviderConfiguration``.

Mirrors ``diagnostics.py`` (Slice 11.2). The view returned by
:func:`diagnostic_view_of_configuration` is what a future logger, CLI
diagnostics command, or verification report is allowed to record. It never
includes:

* the raw model reference value (only :meth:`ProviderModelReference.redacted`)
* credential values (only presence booleans / env var *names*)
* the OpenAI ``base_url`` value (only ``base_url_configured``)
* AWS profile/region values (only presence booleans)
* filesystem paths
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.configuration_models import AIProviderConfiguration


def diagnostic_view_of_configuration(configuration: AIProviderConfiguration) -> dict[str, Any]:
    """Return a safe, credential-free, value-free summary of a configuration."""

    options = configuration.execution_options
    return {
        "adapter": configuration.adapter_configuration.redacted(),
        "ai_requested": configuration.ai_requested,
        "capability_id": str(configuration.capability_id),
        "configuration_version": configuration.configuration_version,
        "credential_requirements": [
            {
                "availability_status": item.availability_status,
                "credential_kind": item.credential_kind,
                "provider_id": str(item.provider_id),
                "required": item.required,
                "source_category": str(item.source_category),
            }
            for item in configuration.credential_requirements
        ],
        "execution_options_present": {
            "max_tokens": options.max_tokens is not None,
            "temperature": options.temperature is not None,
            "timeout_seconds": options.timeout_seconds is not None,
        },
        "limitations": sorted(configuration.limitations),
        "model_reference": configuration.model_reference.redacted(),
        "provider_id": str(configuration.provider_id),
        "source_trace": [
            {"field_name": item.field_name, "source_category": str(item.source_category)}
            for item in sorted(configuration.source_trace, key=lambda item: item.field_name)
        ],
    }


__all__ = [
    "diagnostic_view_of_configuration",
]
