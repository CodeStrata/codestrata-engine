"""Deterministic JSON and Markdown formatting for the telemetry catalog."""

from __future__ import annotations

from codestrata.telemetry.catalog_models import TelemetryCatalog


def format_catalog_json(catalog: TelemetryCatalog) -> str:
    """UTF-8 JSON with sorted keys, 2-space indent, trailing newline."""

    return catalog.to_stable_json(indent=2)


def format_catalog_markdown(catalog: TelemetryCatalog) -> str:
    """Human-readable catalog derived from the same model as JSON."""

    lines: list[str] = [
        "# Privacy-first telemetry event-and-field catalog",
        "",
        f"**Catalog ID:** `{catalog.catalog_id}`  ",
        f"**Catalog schema:** `{catalog.schema_name}` `{catalog.schema_version}`  ",
        f"**Runtime event schema:** `{catalog.runtime_event_schema_version}`  ",
        f"**Runtime policy:** `{catalog.runtime_policy_version}`  ",
        f"**Catalog policy:** `{catalog.catalog_policy_version}`  ",
        f"**Client:** `{catalog.client_name}`  ",
        f"**Transmission:** {catalog.transmission_status.replace('_', ' ')}  ",
        f"**Installation identity:** {catalog.installation_identity_status.replace('_', ' ')}  ",
        f"**Consent scope:** {catalog.consent_scope} (persistence: {catalog.consent_persistence})  ",
        f"**Consent expands fields:** {'yes' if catalog.consent_expands_fields else 'no'}  ",
        f"**Privacy filtering:** {'required' if catalog.privacy_filtering_required else 'optional'}",
        "",
        "This catalog describes what the Engine privacy-first runtime **may**",
        "project. Not every defined event is necessarily emitted today.",
        "No privacy-first telemetry is transmitted because transport is unavailable.",
        "Examples are illustrative and were not transmitted.",
        "",
        "## Events",
        "",
    ]
    for event in catalog.events:
        lines.extend(
            [
                f"### `{event.name}`",
                "",
                f"- **Purpose:** {event.purpose}",
                f"- **Lifecycle meaning:** {event.lifecycle_meaning}",
                f"- **Usage:** `{event.usage_status}`",
                f"- **Transmission operational:** {'yes' if event.transmission_operational else 'no'}",
                f"- **Required fields:** {', '.join(f'`{f}`' for f in event.required_fields)}",
                f"- **Optional fields:** {', '.join(f'`{f}`' for f in event.optional_fields)}",
                f"- **Prohibited fields:** {event.prohibited_fields_note}",
                f"- **Constraints:** {'; '.join(event.event_specific_constraints)}",
                f"- **Privacy:** {event.privacy_notes}",
                "",
                "Illustrative example:",
                "",
                "```json",
                _compact_json(event.example),
                "```",
                "",
            ]
        )

    lines.extend(["## Shared fields", ""])
    for field in catalog.shared_fields:
        lines.extend(
            [
                f"### `{field.name}`",
                "",
                f"- **Type:** `{field.field_type}`",
                f"- **Requiredness:** `{field.requiredness}`",
                f"- **Omitted when unavailable:** {'yes' if field.omitted_when_unavailable else 'no'}",
                f"- **Enum:** `{field.enum_ref}`" if field.enum_ref else "- **Enum:** none",
                f"- **Max length:** {field.max_length if field.max_length is not None else 'n/a'}",
                f"- **Privacy classification:** `{field.privacy_classification}`",
                f"- **Source:** `{field.source}`",
                f"- **Normalization:** {field.normalization}",
                f"- **Bucketed:** {'yes' if field.bucketed else 'no'}",
                f"- **Set ordering normalized:** {'yes' if field.set_ordering_normalized else 'no'}",
                f"- **Transmitted currently:** {'yes' if field.transmitted_currently else 'no'}",
                f"- **Example:** `{field.example}`",
            ]
        )
        if field.notes:
            lines.append(f"- **Notes:** {field.notes}")
        lines.append("")

    lines.extend(["## Enums", ""])
    for enum in catalog.enums:
        lines.append(f"### `{enum.name}`")
        lines.append("")
        lines.append(f"Unknown values: `{enum.unknown_value_behavior}`.")
        if enum.notes:
            lines.append(enum.notes)
        lines.append("")
        for value in enum.values:
            lines.append(f"- `{value.value}` — {value.meaning}")
        lines.append("")

    lines.extend(["## Cross-field rules", ""])
    for rule in catalog.cross_field_rules:
        lines.append(f"- **`{rule.rule_id}`:** {rule.description}")
    lines.append("")

    lines.extend(["## Never collected", ""])
    for item in catalog.never_collected:
        lines.append(f"- **`{item.category}`** — {item.description}")
    lines.append("")

    lines.extend(["## Validation and rejection", ""])
    for item in catalog.validation_behavior:
        lines.append(f"- `{item}`")
    lines.append("")

    lines.extend(
        [
            "## Bounds",
            "",
            f"- Max event size (bytes): `{catalog.max_event_size_bytes}`",
            f"- Max property count: `{catalog.max_property_count}`",
            f"- Max string length: `{catalog.max_string_length}`",
            "",
            "## Change policy",
            "",
            "Changes to event names, field names, types, requiredness, enums,",
            "privacy classifications, never-collected categories, or cross-field",
            "rules require:",
            "",
        ]
    )
    for item in catalog.change_policy:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.extend(
        [
            "## Limitations",
            "",
        ]
    )
    for item in catalog.limitations:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.extend(
        [
            "## Related",
            "",
            "- [telemetry-transport.md](telemetry-transport.md)",
            "- [telemetry-pre-transport-privacy.md](telemetry-pre-transport-privacy.md)",
            "- [telemetry-preview.md](telemetry-preview.md)",
            "- [telemetry-status.md](telemetry-status.md)",
            "- [telemetry-runtime.md](telemetry-runtime.md)",
            "- [telemetry.md](telemetry.md)",
            "- [../PRIVACY.md](../PRIVACY.md)",
            "",
        ]
    )
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _compact_json(payload: dict) -> str:
    import json

    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)


__all__ = [
    "format_catalog_json",
    "format_catalog_markdown",
]
