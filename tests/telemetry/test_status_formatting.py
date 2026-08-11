"""Human-readable status formatting tests (Slice 9.7)."""

from __future__ import annotations

from codestrata.telemetry.status import build_privacy_first_telemetry_status
from codestrata.telemetry.status_formatting import format_privacy_first_telemetry_status


def test_human_readable_sections() -> None:
    text = format_privacy_first_telemetry_status(build_privacy_first_telemetry_status())
    assert text.startswith("Privacy-first telemetry\n")
    assert "Default: Disabled" in text
    assert "Consent saved: No" in text
    assert "Prior consent reused: No" in text
    assert "`codestrata assess`" in text
    assert "--telemetry-allow" in text
    assert "--telemetry-deny" in text
    assert "Transport: Unavailable" in text
    assert "Operational transport configured: No" in text
    assert "HTTP transport implementation: Present" in text
    assert "Assessment isolation" in text or "telemetry failures never alter" in text
    assert "Transmission: Not operational" in text
    assert "Installation identity: Not used" in text
    assert "Status side effects: None" in text
    assert "Legacy compatibility" in text
    assert "not used by the" in text
    assert "Public event catalog: Available" in text
    assert "telemetry-event-catalog" in text
    assert "Preview command: Available" in text
    assert "codestrata telemetry preview" in text
    assert "Pre-transport privacy gate: Required / Available" in text
    assert "policy 1.0" in text
    assert "CLI preview command is not yet available" not in text
    assert "No privacy-first telemetry is transmitted" in text
    assert "Public event catalog is not yet available" not in text


def test_formatting_excludes_sensitive() -> None:
    text = format_privacy_first_telemetry_status(build_privacy_first_telemetry_status())
    for needle in (
        "installation_id",
        "CODESTRATA_TELEMETRY_ENDPOINT",
        "https://",
        "/Users/",
        "queue_depth",
        "enabled\": true",
    ):
        assert needle not in text
