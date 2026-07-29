"""Parse package.json bytes into domain dependency facts.

Deterministic JSON parsing only — no npm CLI, no lockfiles, no shell.
"""

from __future__ import annotations

import json

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import DependencyScope

_SECTIONS: tuple[tuple[str, DependencyScope], ...] = (
    ("dependencies", DependencyScope.RUNTIME),
    ("devDependencies", DependencyScope.DEVELOPMENT),
    ("peerDependencies", DependencyScope.OPTIONAL),
    ("optionalDependencies", DependencyScope.OPTIONAL),
)


def parse_package_json_dependencies(
    content: bytes,
    *,
    source_file: str,
) -> tuple[Dependency, ...]:
    """Parse dependency facts from package.json bytes.

    Returns an empty tuple for empty or malformed JSON.
    """

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
            version = version_value if isinstance(version_value, str) else None
            facts.append(
                Dependency(
                    ecosystem="npm",
                    name=package_name,
                    namespace=None,
                    version=_version_or_none(version),
                    scope=scope,
                    source_file=source_file,
                    direct=True,
                    metadata={"kind": "package-json", "section": section_name},
                )
            )

    engines = payload.get("engines")
    if isinstance(engines, dict):
        node_engine = engines.get("node")
        if isinstance(node_engine, str) and node_engine.strip():
            facts.append(
                Dependency(
                    ecosystem="nodejs",
                    name="nodejs",
                    namespace=None,
                    version=DependencyVersion(raw=node_engine.strip()),
                    scope=DependencyScope.RUNTIME,
                    source_file=source_file,
                    direct=True,
                    metadata={"kind": "engines.node"},
                )
            )

    return _dedupe(facts)


def is_malformed_package_json(content: bytes) -> bool:
    """Return True when non-empty content is not valid JSON object/array text."""

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
        # Scope participates so the same package in dependencies + peerDependencies
        # remains distinct at the fact level; graph identity still omits scope.
        scoped_key = (fact.ecosystem, fact.namespace, fact.name, fact.scope.value)
        existing = ranked.get(scoped_key)
        if existing is None or (existing.version is None and fact.version is not None):
            ranked[scoped_key] = fact
    # Collapse to one graph identity: prefer runtime over development/optional.
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
