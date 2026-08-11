"""Human-readable formatting for privacy-first telemetry status (Slice 9.7)."""

from __future__ import annotations

from codestrata.telemetry.status_models import PrivacyFirstTelemetryStatus


def format_privacy_first_telemetry_status(
    status: PrivacyFirstTelemetryStatus,
) -> str:
    """Render concise developer-facing status text (stdout)."""

    prompt_cmds = ", ".join(f"`codestrata {c}`" for c in status.interactive_prompt_commands)
    flag_cmds = ", ".join(status.flag_commands)
    lines = [
        "Privacy-first telemetry",
        "-----------------------",
        "Default: Disabled",
        "Consent scope: Current command/process only",
        "Consent saved: No",
        "Prior consent reused: No",
        f"Interactive prompt: {prompt_cmds} only, when eligible (default No)",
        (
            "Explicit flags: `--telemetry-allow` / `--telemetry-deny` "
            f"on {flag_cmds}"
        ),
        "Non-interactive behavior: Prompt suppressed",
        "Privacy filtering: Required",
        "Transport: Unavailable",
        "Operational transport configured: No",
        "HTTP transport implementation: Present, explicit configuration required",
        "Transmission: Not operational",
        "Installation identity: Not used by the privacy-first runtime",
        "Status side effects: None",
        (
            f"Public event catalog: Available "
            f"(`{status.catalog_documentation_label}`, "
            f"schema {status.catalog_schema_version}; "
            f"{status.catalog_event_count} events, "
            f"{status.catalog_field_count} fields)"
        ),
        (
            f"Preview command: Available (`{status.preview_command}`; "
            f"local only: {'yes' if status.preview_local_only else 'no'}; "
            f"transmission performed: "
            f"{'yes' if status.preview_transmission_performed else 'no'})"
        ),
        (
            f"Pre-transport privacy gate: "
            f"{'Required / Available' if status.privacy_gate_available and status.privacy_gate_required else 'Unavailable'} "
            f"(policy {status.privacy_policy_version})"
        ),
        "",
        "Legacy compatibility",
        "--------------------",
        "Legacy preference controls are separate and are not used by the",
        "privacy-first runtime.",
        "Status does not inspect, display, or modify legacy preference,",
        "installation-identity, queue, or endpoint state.",
        "",
        "Limitations",
        "-----------",
        "- HTTP transport requires explicit configuration (not activated by default)",
        "- Assessment isolation: telemetry failures never alter assessment results",
        "- VS Code/Cursor integration is not yet implemented",
        "",
        (
            "No privacy-first telemetry is transmitted because the default "
            "transport is unavailable and no operational transport is configured."
        ),
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "format_privacy_first_telemetry_status",
]
