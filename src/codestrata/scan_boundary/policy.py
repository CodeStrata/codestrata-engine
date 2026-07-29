"""Canonical repository scan-boundary policy (Phase 13.6.3).

Authority for which paths enter ``repository.files`` and how retained paths
are role-classified. Collectors must not invent independent ignore lists.
"""

from __future__ import annotations

from enum import StrEnum

BOUNDARY_POLICY_VERSION = "1.0.0"

# Directory *names* pruned during repository walks (any depth).
# Overridable via ScanBoundarySettings / BoundaryPolicy includes.
DEFAULT_EXCLUDED_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".codestrata",
        ".codestrata-examples",
        ".codestrata-test-knowledge",
        ".export-staging",
        "export-staging",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".vscode",
        ".vscode-test",
        "__pycache__",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "target",
        "coverage",
        "reports",
        "generated",
        "tmp",
        "temp",
        "venv",
    }
)


def default_ignore_path_markers(
    *,
    extra: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Path-substring markers for defense-in-depth filters (posix, lowercased)."""

    markers = tuple(f"/{name}/" for name in sorted(DEFAULT_EXCLUDED_DIRECTORY_NAMES))
    # Also match leading-dot variants already covered as directory names.
    extras = (
        "/.generated/",
        "/bin/",
        "/obj/",
        "/packages/",
        *extra,
    )
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for marker in (*markers, *extras):
        key = marker.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(marker)
    return tuple(out)


class ScanSourceRole(StrEnum):
    """Canonical source-role classification for retained paths."""

    PRODUCTION = "production"
    TEST = "test"
    FIXTURE = "fixture"
    EXAMPLE = "example"
    GENERATED = "generated"
    VENDOR = "vendor"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"
    EXCLUDED = "excluded"


# Heuristic directory / path tokens → role (checked after overrides).
_TEST_PARTS = frozenset({"test", "tests", "__tests__", "spec", "specs"})
_FIXTURE_PARTS = frozenset(
    {"fixture", "fixtures", "testdata", "test-data", "test_data", "golden"}
)
_EXAMPLE_PARTS = frozenset({"example", "examples", "sample", "samples", "demo", "demos"})
_DOC_PARTS = frozenset({"docs", "doc", "documentation"})
_VENDOR_PARTS = frozenset({"vendor", "third_party", "third-party", "external"})
_GENERATED_MARKERS = (
    "/generated/",
    "/.generated/",
    "/target/generated",
    "/__generated__/",
)

__all__ = [
    "BOUNDARY_POLICY_VERSION",
    "DEFAULT_EXCLUDED_DIRECTORY_NAMES",
    "ScanSourceRole",
    "default_ignore_path_markers",
]
