"""Deterministic JSON serialization: private vs. diagnostic configuration views.

Two distinct representations are provided, mirroring the "adapter-private
vs. diagnostics-safe" split described in
``engine/docs/ai-provider-configuration.md``:

* :func:`private_view_of_configuration` / :func:`serialize_configuration_private`
  — a **complete** representation, including any adapter-private raw value
  (currently: ``OpenAIAdapterConfiguration.base_url``, if the caller
  happened to construct one with a raw value). This view is for internal
  test/debugging use only and must **never** be written to logs, telemetry,
  CLI output, or verification reports.
* :func:`diagnostic_view_of_configuration` (re-exported from
  ``configuration_diagnostics``) / :func:`serialize_configuration_for_diagnostics`
  — the redacted, privacy-safe view that is safe to write anywhere.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.provider_contracts.adapter_configuration import OpenAIAdapterConfiguration
from codestrata.ai.provider_contracts.configuration_diagnostics import (
    diagnostic_view_of_configuration,
)
from codestrata.ai.provider_contracts.configuration_models import AIProviderConfiguration


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def private_view_of_configuration(configuration: AIProviderConfiguration) -> dict[str, Any]:
    """Return the complete internal view, including any adapter-private raw value.

    **Never** write this view to a log, report, or CLI output — it may
    include ``OpenAIAdapterConfiguration.base_url``'s raw value when one was
    stored. Reserved for internal tests only.
    """

    view = diagnostic_view_of_configuration(configuration)
    adapter = configuration.adapter_configuration
    private_adapter: dict[str, Any] = dict(view["adapter"])
    if isinstance(adapter, OpenAIAdapterConfiguration):
        private_adapter["base_url"] = adapter.base_url
    view = {**view, "adapter": private_adapter}
    return view


def serialize_configuration_for_diagnostics(configuration: AIProviderConfiguration) -> str:
    """Canonical JSON of the redacted, privacy-safe diagnostic view."""

    return canonical_json(diagnostic_view_of_configuration(configuration))


def serialize_configuration_private(configuration: AIProviderConfiguration) -> str:
    """Canonical JSON of the complete internal view. Never write this to a report/log."""

    return canonical_json(private_view_of_configuration(configuration))


__all__ = [
    "canonical_json",
    "diagnostic_view_of_configuration",
    "private_view_of_configuration",
    "serialize_configuration_for_diagnostics",
    "serialize_configuration_private",
]
