"""Deterministic JSON serialization: private vs. diagnostic execution result views.

Two distinct representations, mirroring ``configuration_serialization.py``
(Slice 11.3):

* :func:`private_view_of_execution_result` /
  :func:`serialize_execution_result_private` — a **complete** representation,
  including ``provider_result.content`` (raw text/structured payload) when
  present. Reserved for internal test/debugging use only; must **never** be
  written to logs, telemetry, CLI output, or verification reports.
* :func:`diagnostic_view_of_execution_result` (re-exported from
  ``execution_diagnostics``) / :func:`serialize_execution_result_for_diagnostics`
  — the redacted, content-free view that is safe to write anywhere.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.provider_contracts.execution_diagnostics import (
    diagnostic_view_of_execution_result,
)
from codestrata.ai.provider_contracts.execution_models import AIProviderExecutionResult


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def private_view_of_execution_result(result: AIProviderExecutionResult) -> dict[str, Any]:
    """Return the complete internal view, including any ``provider_result.content``.

    **Never** write this view to a log, report, or CLI output — reserved for
    internal tests only.
    """

    view = diagnostic_view_of_execution_result(result)
    provider_result = result.provider_result
    if provider_result is not None and provider_result.content is not None:
        private_provider_result: dict[str, Any] = dict(view["provider_result"] or {})
        private_provider_result["structured_payload"] = provider_result.content.structured_payload
        private_provider_result["text"] = provider_result.content.text
        view = {**view, "provider_result": private_provider_result}
    return view


def serialize_execution_result_for_diagnostics(result: AIProviderExecutionResult) -> str:
    """Canonical JSON of the redacted, privacy-safe diagnostic view."""

    return canonical_json(diagnostic_view_of_execution_result(result))


def serialize_execution_result_private(result: AIProviderExecutionResult) -> str:
    """Canonical JSON of the complete internal view. Never write this to a report/log."""

    return canonical_json(private_view_of_execution_result(result))


__all__ = [
    "canonical_json",
    "diagnostic_view_of_execution_result",
    "private_view_of_execution_result",
    "serialize_execution_result_for_diagnostics",
    "serialize_execution_result_private",
]
