"""Parse NuGet PackageReference / packages.config bytes into domain dependency facts."""

from __future__ import annotations

import re

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import DependencyScope

_PACKAGE_REFERENCE = re.compile(
    r"""<PackageReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["']"""
    r"""[^>]*(?:\bVersion\s*=\s*["']([^"']+)["'])?""",
    re.IGNORECASE,
)
_PACKAGE_REFERENCE_VERSION_CHILD = re.compile(
    r"""<PackageReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["'][^>]*>"""
    r"""\s*<Version>\s*([^<]+)\s*</Version>""",
    re.IGNORECASE | re.DOTALL,
)
_PACKAGES_CONFIG = re.compile(
    r"""<package\b[^>]*\bid\s*=\s*["']([^"']+)["']"""
    r"""[^>]*\bversion\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)


def parse_nuget_dependencies(
    content: bytes,
    *,
    source_file: str,
) -> tuple[Dependency, ...]:
    """Parse dependency facts from a NuGet manifest."""

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return ()

    lower_name = source_file.replace("\\", "/").rsplit("/", 1)[-1].lower()
    facts: list[Dependency] = []
    if lower_name == "packages.config":
        for match in _PACKAGES_CONFIG.finditer(text):
            facts.append(
                _fact(
                    name=match.group(1).strip(),
                    version=match.group(2).strip(),
                    source_file=source_file,
                    kind="packages-config",
                )
            )
    else:
        seen: dict[str, str | None] = {}
        for match in _PACKAGE_REFERENCE.finditer(text):
            name = match.group(1).strip()
            version = (match.group(2) or "").strip() or None
            if name:
                seen.setdefault(name, version)
        for match in _PACKAGE_REFERENCE_VERSION_CHILD.finditer(text):
            name = match.group(1).strip()
            version = match.group(2).strip()
            if name:
                seen[name] = version
        for name, version in sorted(seen.items()):
            facts.append(
                _fact(
                    name=name,
                    version=version,
                    source_file=source_file,
                    kind="package-reference",
                )
            )
    return _dedupe(facts)


def is_malformed_nuget_manifest(content: bytes) -> bool:
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return False
    if "<" not in text:
        return True
    return False


def _fact(
    *,
    name: str,
    version: str | None,
    source_file: str,
    kind: str,
) -> Dependency:
    return Dependency(
        ecosystem="nuget",
        name=name,
        namespace=None,
        version=_version_or_none(version),
        scope=DependencyScope.RUNTIME,
        source_file=source_file,
        direct=True,
        metadata={"kind": kind},
    )


def _version_or_none(version: str | None) -> DependencyVersion | None:
    if version is None or not str(version).strip():
        return None
    return DependencyVersion(raw=str(version).strip())


def _dedupe(facts: list[Dependency]) -> tuple[Dependency, ...]:
    unique: dict[tuple[str, str, str | None], Dependency] = {}
    for item in facts:
        key = (
            item.ecosystem,
            item.name.lower(),
            item.version.raw if item.version else None,
        )
        unique.setdefault(key, item)
    return tuple(sorted(unique.values(), key=lambda item: (item.name.lower(), item.source_file)))
