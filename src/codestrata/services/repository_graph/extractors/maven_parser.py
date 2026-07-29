"""Parse Maven POM bytes into domain dependency facts.

Deterministic XML parsing only — no Maven CLI, no network, no shell.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping

from codestrata.domain.repository_graph.dependencies import Dependency, DependencyVersion
from codestrata.domain.repository_graph.enums import DependencyScope

_PROPERTY_REF = re.compile(r"\$\{([^}]+)\}")

_SPRING_BOOT_PARENT = ("org.springframework.boot", "spring-boot-starter-parent")

_JAVA_VERSION_PROPERTIES = (
    "java.version",
    "maven.compiler.release",
    "maven.compiler.source",
)


def parse_maven_dependencies(
    content: bytes,
    *,
    source_file: str,
) -> tuple[Dependency, ...]:
    """Parse dependency facts from POM bytes.

    Returns an empty tuple for empty or malformed XML (callers may emit
    diagnostics separately).
    """

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return ()

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return ()

    namespace = _xml_namespace(root)
    project = _ProjectModel.from_root(root, namespace)
    facts: list[Dependency] = []

    parent = project.parent
    if parent is not None and parent.artifact_id:
        facts.append(
            Dependency(
                ecosystem="maven",
                name=parent.artifact_id,
                namespace=parent.group_id,
                version=_version_or_none(parent.version),
                scope=DependencyScope.UNKNOWN,
                source_file=source_file,
                direct=True,
                metadata={"kind": "parent"},
            )
        )
        if (parent.group_id, parent.artifact_id) == _SPRING_BOOT_PARENT:
            facts.append(
                _spring_boot_concept(
                    version=parent.version,
                    source_file=source_file,
                    kind="parent",
                )
            )

    managed_keys: set[tuple[str | None, str]] = set()
    for managed in project.managed_dependencies:
        if not managed.artifact_id:
            continue
        key = (managed.group_id, managed.artifact_id)
        managed_keys.add(key)
        facts.append(
            Dependency(
                ecosystem="maven",
                name=managed.artifact_id,
                namespace=managed.group_id,
                version=_version_or_none(managed.version),
                scope=_maven_scope(managed.scope),
                source_file=source_file,
                direct=False,
                metadata={"kind": "dependencyManagement"},
            )
        )
        if _is_spring_boot_artifact(managed.group_id, managed.artifact_id):
            facts.append(
                _spring_boot_concept(
                    version=managed.version,
                    source_file=source_file,
                    kind="dependencyManagement",
                )
            )

    managed_by_key = {
        (item.group_id, item.artifact_id): item for item in project.managed_dependencies
    }
    for declared in project.dependencies:
        if not declared.artifact_id:
            continue
        key = (declared.group_id, declared.artifact_id)
        version = declared.version
        version_managed = False
        if version is None and key in managed_by_key:
            version = managed_by_key[key].version
            version_managed = True
        elif version is None and project.uses_spring_boot_parent:
            version_managed = True
        facts.append(
            Dependency(
                ecosystem="maven",
                name=declared.artifact_id,
                namespace=declared.group_id,
                version=_version_or_none(version),
                scope=_maven_scope(declared.scope),
                source_file=source_file,
                direct=True,
                metadata={
                    "kind": "dependency",
                    "version_managed": version_managed,
                },
            )
        )
        if _is_spring_boot_artifact(declared.group_id, declared.artifact_id):
            concept_version = version
            if concept_version is None and project.uses_spring_boot_parent and parent is not None:
                concept_version = parent.version
            facts.append(
                _spring_boot_concept(
                    version=concept_version,
                    source_file=source_file,
                    kind="dependency",
                )
            )

    java_version = project.java_version
    if java_version is not None:
        facts.append(
            Dependency(
                ecosystem="jvm",
                name="java",
                namespace=None,
                version=DependencyVersion(raw=java_version),
                scope=DependencyScope.COMPILE,
                source_file=source_file,
                direct=True,
                metadata={"kind": "java-version-property"},
            )
        )

    return _dedupe_dependencies(facts)


def is_malformed_maven_pom(content: bytes) -> bool:
    """Return True when non-empty content is not well-formed XML."""

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return False
    try:
        ET.fromstring(content)
    except ET.ParseError:
        return True
    return False


class _Coordinate:
    __slots__ = ("group_id", "artifact_id", "version", "scope")

    def __init__(
        self,
        *,
        group_id: str | None,
        artifact_id: str | None,
        version: str | None,
        scope: str | None = None,
    ) -> None:
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version
        self.scope = scope


class _ProjectModel:
    __slots__ = (
        "group_id",
        "artifact_id",
        "version",
        "properties",
        "parent",
        "dependencies",
        "managed_dependencies",
        "uses_spring_boot_parent",
        "java_version",
    )

    def __init__(
        self,
        *,
        group_id: str | None,
        artifact_id: str | None,
        version: str | None,
        properties: Mapping[str, str],
        parent: _Coordinate | None,
        dependencies: tuple[_Coordinate, ...],
        managed_dependencies: tuple[_Coordinate, ...],
        uses_spring_boot_parent: bool,
        java_version: str | None,
    ) -> None:
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version
        self.properties = dict(properties)
        self.parent = parent
        self.dependencies = dependencies
        self.managed_dependencies = managed_dependencies
        self.uses_spring_boot_parent = uses_spring_boot_parent
        self.java_version = java_version

    @classmethod
    def from_root(cls, root: ET.Element, namespace: str) -> _ProjectModel:
        raw_properties = _extract_properties(root, namespace)
        group_id = _text(root, namespace, "groupId")
        artifact_id = _text(root, namespace, "artifactId")
        version = _text(root, namespace, "version")

        parent_element = root.find(_path(namespace, "parent"))
        parent: _Coordinate | None = None
        if parent_element is not None:
            parent = _Coordinate(
                group_id=_text(parent_element, namespace, "groupId"),
                artifact_id=_text(parent_element, namespace, "artifactId"),
                version=_text(parent_element, namespace, "version"),
            )

        project_props = dict(raw_properties)
        if group_id:
            project_props.setdefault("project.groupId", group_id)
            project_props.setdefault("groupId", group_id)
        if artifact_id:
            project_props.setdefault("project.artifactId", artifact_id)
            project_props.setdefault("artifactId", artifact_id)
        if version:
            project_props.setdefault("project.version", version)
            project_props.setdefault("version", version)
        if parent is not None:
            if parent.group_id:
                project_props.setdefault("project.parent.groupId", parent.group_id)
            if parent.artifact_id:
                project_props.setdefault("project.parent.artifactId", parent.artifact_id)
            if parent.version:
                project_props.setdefault("project.parent.version", parent.version)

        resolved_props = _resolve_all_properties(project_props)

        def resolve(value: str | None) -> str | None:
            return _resolve_value(value, resolved_props)

        if parent is not None:
            parent = _Coordinate(
                group_id=resolve(parent.group_id),
                artifact_id=resolve(parent.artifact_id),
                version=resolve(parent.version),
            )

        managed = tuple(
            _Coordinate(
                group_id=resolve(item.group_id),
                artifact_id=resolve(item.artifact_id),
                version=resolve(item.version),
                scope=resolve(item.scope),
            )
            for item in _extract_dependency_block(
                root,
                namespace,
                container_path=("dependencyManagement", "dependencies"),
            )
        )
        deps = tuple(
            _Coordinate(
                group_id=resolve(item.group_id),
                artifact_id=resolve(item.artifact_id),
                version=resolve(item.version),
                scope=resolve(item.scope),
            )
            for item in _extract_dependency_block(
                root,
                namespace,
                container_path=("dependencies",),
            )
        )

        uses_boot = (
            parent is not None and (parent.group_id, parent.artifact_id) == _SPRING_BOOT_PARENT
        )
        java_version: str | None = None
        for key in _JAVA_VERSION_PROPERTIES:
            candidate = resolved_props.get(key)
            if candidate:
                java_version = candidate
                break

        return cls(
            group_id=resolve(group_id),
            artifact_id=resolve(artifact_id),
            version=resolve(version),
            properties=resolved_props,
            parent=parent,
            dependencies=deps,
            managed_dependencies=managed,
            uses_spring_boot_parent=uses_boot,
            java_version=java_version,
        )


def _extract_properties(root: ET.Element, namespace: str) -> dict[str, str]:
    properties_element = root.find(_path(namespace, "properties"))
    if properties_element is None:
        return {}
    properties: dict[str, str] = {}
    for child in properties_element:
        name = child.tag.split("}")[-1]
        if child.text is None:
            continue
        value = child.text.strip()
        if value:
            properties[name] = value
    return properties


def _extract_dependency_block(
    root: ET.Element,
    namespace: str,
    *,
    container_path: tuple[str, ...],
) -> tuple[_Coordinate, ...]:
    current: ET.Element | None = root
    for segment in container_path:
        if current is None:
            return ()
        current = current.find(_path(namespace, segment))
    if current is None:
        return ()

    items: list[_Coordinate] = []
    for dependency_element in current.findall(_path(namespace, "dependency")):
        artifact_id = _text(dependency_element, namespace, "artifactId")
        if not artifact_id:
            continue
        items.append(
            _Coordinate(
                group_id=_text(dependency_element, namespace, "groupId"),
                artifact_id=artifact_id,
                version=_text(dependency_element, namespace, "version"),
                scope=_text(dependency_element, namespace, "scope"),
            )
        )
    return tuple(items)


def _resolve_all_properties(properties: Mapping[str, str]) -> dict[str, str]:
    resolved = dict(properties)
    for _ in range(16):
        changed = False
        next_values: dict[str, str] = {}
        for key, value in resolved.items():
            new_value = _resolve_value(value, resolved) or value
            next_values[key] = new_value
            if new_value != value:
                changed = True
        resolved = next_values
        if not changed:
            break
    return resolved


def _resolve_value(value: str | None, properties: Mapping[str, str]) -> str | None:
    if value is None:
        return None

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return properties.get(key, match.group(0))

    previous = value
    for _ in range(16):
        current = _PROPERTY_REF.sub(replace, previous)
        if current == previous:
            return current
        previous = current
    return previous


def _maven_scope(raw: str | None) -> DependencyScope:
    if raw is None or not raw.strip():
        return DependencyScope.COMPILE
    normalized = raw.strip().lower()
    mapping = {
        "compile": DependencyScope.COMPILE,
        "runtime": DependencyScope.RUNTIME,
        "test": DependencyScope.TEST,
        "provided": DependencyScope.PROVIDED,
        "optional": DependencyScope.OPTIONAL,
        "system": DependencyScope.PROVIDED,
        "import": DependencyScope.UNKNOWN,
    }
    return mapping.get(normalized, DependencyScope.UNKNOWN)


def _is_spring_boot_artifact(group_id: str | None, artifact_id: str | None) -> bool:
    if artifact_id is None:
        return False
    if group_id == "org.springframework.boot":
        return True
    return artifact_id.startswith("spring-boot")


def _spring_boot_concept(
    *,
    version: str | None,
    source_file: str,
    kind: str,
) -> Dependency:
    return Dependency(
        ecosystem="maven",
        name="spring-boot",
        namespace="org.springframework.boot",
        version=_version_or_none(version),
        scope=DependencyScope.COMPILE,
        source_file=source_file,
        direct=True,
        metadata={"kind": "spring-boot-concept", "source_kind": kind},
    )


def _version_or_none(raw: str | None) -> DependencyVersion | None:
    if raw is None or not raw.strip():
        return None
    return DependencyVersion(raw=raw.strip())


def _dedupe_dependencies(facts: list[Dependency]) -> tuple[Dependency, ...]:
    """Keep one fact per (ecosystem, namespace, name), preferring versioned/direct."""

    ranked: dict[tuple[str, str | None, str], Dependency] = {}
    for fact in facts:
        key = (fact.ecosystem, fact.namespace, fact.name)
        existing = ranked.get(key)
        if existing is None:
            ranked[key] = fact
            continue
        ranked[key] = _prefer_dependency(existing, fact)
    return tuple(
        ranked[key]
        for key in sorted(
            ranked,
            key=lambda item: (
                item[0],
                item[1] or "",
                item[2],
            ),
        )
    )


def _prefer_dependency(left: Dependency, right: Dependency) -> Dependency:
    left_score = (
        1 if left.version is not None else 0,
        1 if left.direct else 0,
        0 if left.metadata.get("kind") == "spring-boot-concept" else 1,
    )
    right_score = (
        1 if right.version is not None else 0,
        1 if right.direct else 0,
        0 if right.metadata.get("kind") == "spring-boot-concept" else 1,
    )
    if right_score > left_score:
        return right
    if right_score < left_score:
        return left
    # Stable tie-break: prefer lexicographically smaller source_kind metadata.
    left_kind = str(left.metadata.get("source_kind") or left.metadata.get("kind") or "")
    right_kind = str(right.metadata.get("source_kind") or right.metadata.get("kind") or "")
    return left if left_kind <= right_kind else right


def _xml_namespace(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}")[0][1:]
    return ""


def _path(namespace: str, element_name: str) -> str:
    if namespace:
        return f"{{{namespace}}}{element_name}"
    return element_name


def _text(parent: ET.Element, namespace: str, element_name: str) -> str | None:
    element = parent.find(_path(namespace, element_name))
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None
