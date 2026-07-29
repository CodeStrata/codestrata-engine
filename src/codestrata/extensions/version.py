"""Extension API versioning for Community Edition contracts."""

from __future__ import annotations

# Semver for extension contracts (analyzers, assess AI providers, report renderers).
# Major bumps are breaking; Engine rejects incompatible contributions.
EXTENSION_API_VERSION = "1.0.0"


def extension_api_major(version: str) -> int | None:
    """Return the major component of an extension API version string."""

    text = version.strip().lstrip("vV")
    if not text:
        return None
    head = text.split(".", maxsplit=1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def extension_api_compatible(extension_version: str, *, engine_version: str | None = None) -> bool:
    """Return True when extension major matches the Engine Extension API major."""

    engine = engine_version or EXTENSION_API_VERSION
    left = extension_api_major(extension_version)
    right = extension_api_major(engine)
    if left is None or right is None:
        return False
    return left == right


__all__ = [
    "EXTENSION_API_VERSION",
    "extension_api_compatible",
    "extension_api_major",
]
