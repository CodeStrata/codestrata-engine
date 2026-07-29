"""Deterministic identity normalization for Dependency Evidence."""

from __future__ import annotations

import re


def normalize_maven_identity(group_id: str | None, artifact_id: str | None) -> str | None:
    group = (group_id or "").strip()
    artifact = (artifact_id or "").strip()
    if not artifact:
        return None
    if group:
        return f"{group}:{artifact}"
    return artifact


def normalize_python_distribution_name(name: str) -> str:
    """PEP 503-inspired packaging name normalization (deterministic, local)."""

    compact = name.strip().lower().replace("_", "-").replace(".", "-")
    compact = re.sub(r"-+", "-", compact)
    return compact.strip("-")


_PROPERTY_PATTERN = re.compile(r"\$\{([^}]+)\}")


def resolve_local_properties(
    raw: str | None, properties: dict[str, str]
) -> tuple[str | None, bool]:
    """Resolve ``${property}`` placeholders using local properties only.

    Returns (resolved_or_original, fully_resolved).
    """

    if raw is None:
        return None, False
    text = raw.strip()
    if not text:
        return None, False

    unresolved = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal unresolved
        key = match.group(1).strip()
        if key in properties:
            return properties[key]
        unresolved = True
        return match.group(0)

    resolved = _PROPERTY_PATTERN.sub(_replace, text)
    if unresolved:
        return resolved, False
    # Nested one-level: re-run once for properties that expand to other properties.
    nested = _PROPERTY_PATTERN.sub(_replace, resolved)
    if unresolved:
        return nested, False
    return nested, True
