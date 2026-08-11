"""Deterministic JSON formatting for privacy-first telemetry preview."""

from __future__ import annotations

from codestrata.telemetry.preview_models import PrivacyFirstTelemetryPreview


def format_privacy_first_telemetry_preview(
    preview: PrivacyFirstTelemetryPreview,
) -> str:
    """UTF-8 JSON with sorted keys, 2-space indent, trailing newline."""

    return preview.to_stable_json(indent=2)


__all__ = [
    "format_privacy_first_telemetry_preview",
]
