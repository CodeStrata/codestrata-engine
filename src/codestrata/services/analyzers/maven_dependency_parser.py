"""Parse direct dependencies from Maven POM files."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from codestrata.models import Dependency
from codestrata.services.analyzers.maven_version_resolver import (
    MavenVersionResolver,
)

DependencyClassifier = Callable[[str, str], list[str]]


class MavenDependencyParser:
    """Extract direct dependencies from a Maven POM."""

    def __init__(
        self,
        dependency_classifier: DependencyClassifier,
    ) -> None:
        self._dependency_classifier = dependency_classifier

    def parse(
        self,
        manifest_path: Path,
        relative_path: str,
    ) -> list[Dependency]:
        """Parse direct dependencies from the supplied Maven POM."""

        if not manifest_path.is_file():
            return []

        try:
            root = ET.parse(manifest_path).getroot()
        except (ET.ParseError, OSError):
            return []

        namespace = self._xml_namespace(root)
        version_resolver = MavenVersionResolver(
            root=root,
            namespace=namespace,
        )

        dependencies_element = root.find(self._xml_path(namespace, "dependencies"))

        if dependencies_element is None:
            return []

        dependencies: list[Dependency] = []

        for dependency_element in dependencies_element.findall(
            self._xml_path(namespace, "dependency")
        ):
            dependency = self._parse_dependency(
                dependency_element=dependency_element,
                namespace=namespace,
                relative_path=relative_path,
                version_resolver=version_resolver,
            )

            if dependency is not None:
                dependencies.append(dependency)

        return dependencies

    def _parse_dependency(
        self,
        dependency_element: ET.Element,
        namespace: str,
        relative_path: str,
        version_resolver: MavenVersionResolver,
    ) -> Dependency | None:
        """Convert one Maven dependency element into an CodeStrata dependency."""

        group_id = self._xml_text(
            dependency_element,
            namespace,
            "groupId",
        )
        artifact_id = self._xml_text(
            dependency_element,
            namespace,
            "artifactId",
        )

        if not artifact_id:
            return None

        dependency_name = f"{group_id}:{artifact_id}" if group_id else artifact_id

        raw_version = self._xml_text(
            dependency_element,
            namespace,
            "version",
        )

        version_resolution = version_resolver.resolve(
            dependency_name=dependency_name,
            raw_version=raw_version,
        )

        raw_scope = self._xml_text(
            dependency_element,
            namespace,
            "scope",
        )

        return Dependency(
            name=dependency_name,
            version=version_resolution.version,
            ecosystem="maven",
            scope=self._normalize_scope(raw_scope),
            manifest_path=relative_path,
            categories=self._dependency_classifier(
                dependency_name,
                "maven",
            ),
            dynamic_version=self._is_dynamic_version(raw_version),
            unmanaged_version=version_resolution.unmanaged_version,
            version_managed=version_resolution.version_managed,
            version_source=version_resolution.version_source,
        )

    def _normalize_scope(
        self,
        scope: str | None,
    ) -> str:
        """Map Maven scopes to normalized CodeStrata dependency scopes."""

        if scope is None or scope == "compile":
            return "runtime"

        supported_scopes = {
            "test",
            "provided",
            "runtime",
            "system",
            "import",
        }

        if scope in supported_scopes:
            return scope

        return scope

    def _is_dynamic_version(
        self,
        version: str | None,
    ) -> bool:
        """Return whether a Maven dependency uses a dynamic version."""

        if version is None:
            return False

        normalized_version = version.strip().upper()

        return (
            normalized_version in {"LATEST", "RELEASE"}
            or normalized_version.startswith("[")
            or normalized_version.startswith("(")
        )

    def _xml_namespace(self, root: ET.Element) -> str:
        """Extract the XML namespace from the root element."""

        if root.tag.startswith("{"):
            return root.tag.split("}")[0][1:]

        return ""

    def _xml_path(
        self,
        namespace: str,
        element_name: str,
    ) -> str:
        """Construct an ElementTree path with an optional namespace."""

        if namespace:
            return f"{{{namespace}}}{element_name}"

        return element_name

    def _xml_text(
        self,
        parent: ET.Element,
        namespace: str,
        element_name: str,
    ) -> str | None:
        """Read normalized text from a child XML element."""

        element = parent.find(self._xml_path(namespace, element_name))

        if element is None or element.text is None:
            return None

        value = element.text.strip()

        return value or None
