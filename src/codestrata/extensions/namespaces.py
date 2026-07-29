"""Reserved extension ID namespaces for Community Edition.

Third-party analyzer and renderer IDs must use a reverse-DNS prefix that is
not reserved. Built-in and Platform surfaces use the reserved prefixes below.
"""

from __future__ import annotations

# First-party / Platform prefixes — third-party packs must not claim these.
RESERVED_EXTENSION_NAMESPACES: tuple[str, ...] = (
    "codestrata.",
    "com.codestrata.",
    "org.codestrata.",
    "io.codestrata.",
)

# Built-in assess AI provider names (not reverse-DNS; closed vocabulary).
RESERVED_ASSESS_AI_PROVIDER_IDS: frozenset[str] = frozenset({"bedrock", "openai"})

# Built-in report renderer IDs.
RESERVED_RENDERER_IDS: frozenset[str] = frozenset({"html", "json"})

# Core CLI verbs that extension Typer groups must not shadow.
RESERVED_CLI_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "about",
        "assess",
        "config",
        "doctor",
        "examples",
        "extensions",
        "init",
        "scan",
        "version",
    }
)


def is_reserved_analyzer_id(extension_id: str) -> bool:
    """Return True when an analyzer ID uses a reserved namespace."""

    lowered = extension_id.strip().lower()
    return any(lowered.startswith(prefix) for prefix in RESERVED_EXTENSION_NAMESPACES)


def assert_third_party_analyzer_id(extension_id: str) -> None:
    """Raise ValueError when a third-party analyzer claims a reserved namespace."""

    if is_reserved_analyzer_id(extension_id):
        raise ValueError(
            f"Analyzer extension id {extension_id!r} uses a reserved namespace. "
            f"Reserved prefixes: {', '.join(RESERVED_EXTENSION_NAMESPACES)}"
        )


__all__ = [
    "RESERVED_ASSESS_AI_PROVIDER_IDS",
    "RESERVED_CLI_COMMAND_NAMES",
    "RESERVED_EXTENSION_NAMESPACES",
    "RESERVED_RENDERER_IDS",
    "assert_third_party_analyzer_id",
    "is_reserved_analyzer_id",
]
