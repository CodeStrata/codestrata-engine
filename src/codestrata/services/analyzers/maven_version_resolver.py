"""Resolve Maven dependency version-management information."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class MavenVersionResolution:
    """Result of resolving how a Maven dependency version is supplied."""

    version: str | None
    version_managed: bool
    version_source: str | None
    unmanaged_version: bool


class MavenVersionResolver:
    """Resolve explicit and managed Maven dependency versions."""

    SPRING_BOOT_PARENT = (
        "org.springframework.boot",
        "spring-boot-starter-parent",
    )

    def __init__(
        self,
        root: ET.Element,
        namespace: str,
    ) -> None:
        self._root = root
        self._namespace = namespace
        self._properties = self._extract_properties()
        self._managed_dependencies = self._extract_managed_dependencies()
        self._parent = self._extract_parent()

    def resolve(
        self,
        dependency_name: str,
        raw_version: str | None,
    ) -> MavenVersionResolution:
        """Resolve the version source for one Maven dependency."""

        if raw_version is not None:
            return MavenVersionResolution(
                version=self._resolve_property(raw_version),
                version_managed=False,
                version_source="dependency",
                unmanaged_version=False,
            )

        managed_version = self._managed_dependencies.get(dependency_name)

        if managed_version is not None:
            return MavenVersionResolution(
                version=self._resolve_property(managed_version),
                version_managed=True,
                version_source="dependencyManagement",
                unmanaged_version=False,
            )

        if self._uses_spring_boot_parent():
            return MavenVersionResolution(
                version=None,
                version_managed=True,
                version_source="spring-boot-parent",
                unmanaged_version=False,
            )

        return MavenVersionResolution(
            version=None,
            version_managed=False,
            version_source=None,
            unmanaged_version=True,
        )

    def _extract_properties(self) -> dict[str, str]:
        """Extract Maven project properties."""

        properties_element = self._root.find(self._path("properties"))

        if properties_element is None:
            return {}

        properties: dict[str, str] = {}

        for child in properties_element:
            property_name = child.tag.split("}")[-1]

            if child.text is None:
                continue

            property_value = child.text.strip()

            if property_value:
                properties[property_name] = property_value

        return properties

    def _extract_managed_dependencies(
        self,
    ) -> dict[str, str | None]:
        """Extract dependencies declared in dependencyManagement."""

        dependency_management = self._root.find(self._path("dependencyManagement"))

        if dependency_management is None:
            return {}

        dependencies_element = dependency_management.find(self._path("dependencies"))

        if dependencies_element is None:
            return {}

        managed_dependencies: dict[str, str | None] = {}

        for dependency_element in dependencies_element.findall(self._path("dependency")):
            group_id = self._text(
                dependency_element,
                "groupId",
            )
            artifact_id = self._text(
                dependency_element,
                "artifactId",
            )

            if not artifact_id:
                continue

            dependency_name = f"{group_id}:{artifact_id}" if group_id else artifact_id

            managed_dependencies[dependency_name] = self._text(
                dependency_element,
                "version",
            )

        return managed_dependencies

    def _extract_parent(
        self,
    ) -> tuple[str | None, str | None, str | None] | None:
        """Extract Maven parent coordinates."""

        parent_element = self._root.find(self._path("parent"))

        if parent_element is None:
            return None

        return (
            self._text(parent_element, "groupId"),
            self._text(parent_element, "artifactId"),
            self._resolve_property(self._text(parent_element, "version")),
        )

    def _uses_spring_boot_parent(self) -> bool:
        """Return whether the project uses Spring Boot's parent POM."""

        if self._parent is None:
            return False

        group_id, artifact_id, _ = self._parent

        return (
            group_id,
            artifact_id,
        ) == self.SPRING_BOOT_PARENT

    def _resolve_property(
        self,
        value: str | None,
    ) -> str | None:
        """Resolve a Maven property reference when possible."""

        if value is None:
            return None

        match = re.fullmatch(r"\$\{([^}]+)\}", value)

        if match is None:
            return value

        property_name = match.group(1)

        return self._properties.get(property_name, value)

    def _path(self, element_name: str) -> str:
        """Construct an XML path with the configured namespace."""

        if self._namespace:
            return f"{{{self._namespace}}}{element_name}"

        return element_name

    def _text(
        self,
        parent: ET.Element,
        element_name: str,
    ) -> str | None:
        """Read normalized text from a child XML element."""

        element = parent.find(self._path(element_name))

        if element is None or element.text is None:
            return None

        value = element.text.strip()

        return value or None
