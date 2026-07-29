"""Parse composer.json bytes into domain dependency facts.

Deterministic JSON parsing only — no Composer CLI, no lockfile resolution.
"""

from __future__ import annotations

import json

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import DependencyScope

_SECTIONS: tuple[tuple[str, DependencyScope], ...] = (
    ("require", DependencyScope.RUNTIME),
    ("require-dev", DependencyScope.DEVELOPMENT),
)

_PLATFORM_PACKAGES = frozenset({"php", "hhvm", "ext-json", "composer-plugin-api"})


def parse_composer_json_dependencies(
    content: bytes,
    *,
    source_file: str,
) -> tuple[Dependency, ...]:
    """Parse dependency facts from composer.json bytes."""

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return ()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ()

    if not isinstance(payload, dict):
        return ()

    facts: list[Dependency] = []
    for section_name, scope in _SECTIONS:
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        for name, version_value in section.items():
            if not isinstance(name, str) or not name.strip():
                continue
            package_name = name.strip()
            if package_name.lower() in _PLATFORM_PACKAGES or package_name.lower().startswith(
                "ext-"
            ):
                continue
            version = version_value if isinstance(version_value, str) else None
            namespace, _, short_name = package_name.partition("/")
            facts.append(
                Dependency(
                    ecosystem="composer",
                    name=short_name or package_name,
                    namespace=namespace if short_name else None,
                    version=_version_or_none(version),
                    scope=scope,
                    source_file=source_file,
                    direct=True,
                    metadata={"kind": "composer-json", "section": section_name},
                )
            )

    return _dedupe(facts)


def is_malformed_composer_json(content: bytes) -> bool:
    """Return True when non-empty content is not valid JSON."""

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return False
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return True
    return False


def _version_or_none(raw: str | None) -> DependencyVersion | None:
    if raw is None or not str(raw).strip():
        return None
    return DependencyVersion(raw=str(raw).strip())


def _dedupe(facts: list[Dependency]) -> tuple[Dependency, ...]:
    ranked: dict[tuple[str, str | None, str, str], Dependency] = {}
    for fact in facts:
        scoped_key = (fact.ecosystem, fact.namespace, fact.name, fact.scope.value)
        existing = ranked.get(scoped_key)
        if existing is None or (existing.version is None and fact.version is not None):
            ranked[scoped_key] = fact
    by_identity: dict[tuple[str, str | None, str], Dependency] = {}
    preference = {
        DependencyScope.RUNTIME: 3,
        DependencyScope.COMPILE: 3,
        DependencyScope.DEVELOPMENT: 2,
        DependencyScope.OPTIONAL: 1,
        DependencyScope.TEST: 1,
        DependencyScope.PROVIDED: 1,
        DependencyScope.UNKNOWN: 0,
    }
    for fact in ranked.values():
        identity = (fact.ecosystem, fact.namespace, fact.name)
        existing = by_identity.get(identity)
        if existing is None:
            by_identity[identity] = fact
            continue
        if preference.get(fact.scope, 0) > preference.get(existing.scope, 0):
            by_identity[identity] = fact
            continue
        if preference.get(fact.scope, 0) == preference.get(existing.scope, 0):
            if fact.version is not None and existing.version is None:
                by_identity[identity] = fact
    return tuple(
        by_identity[identity]
        for identity in sorted(
            by_identity,
            key=lambda item: (item[0], item[1] or "", item[2]),
        )
    )
