from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    BuildFacts,
    Repository,
    RepositoryFacts,
    Technology,
)


class BuildMetadataAnalyzer:
    """Extract deterministic metadata from repository build files."""

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        del technologies
        del facts

        root = Path(repository.path)

        build_facts = BuildFacts()

        for relative_path in repository.files:
            path = root / relative_path
            filename = path.name

            if filename == "pom.xml":
                build_facts = build_facts.merge(
                    self._analyze_maven(
                        path=path,
                        relative_path=relative_path,
                        root=root,
                    )
                )
            elif filename in {"build.gradle", "build.gradle.kts"}:
                build_facts = build_facts.merge(
                    self._analyze_gradle(
                        path=path,
                        relative_path=relative_path,
                        root=root,
                    )
                )
            elif filename == "package.json":
                build_facts = build_facts.merge(
                    self._analyze_npm(
                        path=path,
                        relative_path=relative_path,
                    )
                )
            elif filename == "composer.json":
                build_facts = build_facts.merge(
                    self._analyze_composer(
                        path=path,
                        relative_path=relative_path,
                    )
                )
            elif filename == "build.xml":
                build_facts = build_facts.merge(
                    self._analyze_ant(
                        relative_path=relative_path,
                    )
                )

        return AnalyzerResult(
            facts=RepositoryFacts(build=build_facts),
            findings=[],
        )

    def _analyze_maven(
        self,
        path: Path,
        relative_path: str,
        root: Path,
    ) -> BuildFacts:
        try:
            tree = ElementTree.parse(path)
        except (ElementTree.ParseError, OSError):
            return BuildFacts()

        project = tree.getroot()
        namespace = self._xml_namespace(project.tag)

        packaging = self._find_text(
            project,
            "packaging",
            namespace,
        )

        modules = [
            module.strip()
            for module in self._find_all_text(
                project,
                "modules/module",
                namespace,
            )
            if module.strip()
        ]

        plugins = self._maven_plugins(project, namespace)

        properties = self._maven_properties(project, namespace)

        source_versions = self._non_empty(
            properties.get("maven.compiler.source"),
            properties.get("java.version"),
        )

        target_versions = self._non_empty(
            properties.get("maven.compiler.target"),
            properties.get("java.version"),
        )

        wrapper_available = self._maven_wrapper_available(
            root=root,
            build_file=path,
        )

        command_prefix = "./mvnw" if wrapper_available else "mvn"

        return BuildFacts(
            multi_module=bool(modules),
            modules=modules,
            plugins=plugins,
            packaging_types=[packaging] if packaging else [],
            java_source_versions=source_versions,
            java_target_versions=target_versions,
            inferred_commands=[
                f"{command_prefix} test",
                f"{command_prefix} package",
            ],
        )

    def _analyze_gradle(
        self,
        path: Path,
        relative_path: str,
        root: Path,
    ) -> BuildFacts:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return BuildFacts()

        plugins = self._gradle_plugins(content)

        source_versions = self._regex_values(
            content,
            patterns=[
                r"sourceCompatibility\s*=\s*[\"']?([^\"'\s]+)",
                r"sourceCompatibility\s*=\s*JavaVersion\.VERSION_([A-Za-z0-9_]+)",
                r"languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)",
            ],
        )

        target_versions = self._regex_values(
            content,
            patterns=[
                r"targetCompatibility\s*=\s*[\"']?([^\"'\s]+)",
                r"targetCompatibility\s*=\s*JavaVersion\.VERSION_([A-Za-z0-9_]+)",
                r"languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)",
            ],
        )

        wrapper_available = self._gradle_wrapper_available(
            root=root,
            build_file=path,
        )

        command_prefix = "./gradlew" if wrapper_available else "gradle"

        return BuildFacts(
            plugins=plugins,
            java_source_versions=source_versions,
            java_target_versions=target_versions,
            inferred_commands=[
                f"{command_prefix} test",
                f"{command_prefix} build",
            ],
        )

    def _analyze_npm(
        self,
        path: Path,
        relative_path: str,
    ) -> BuildFacts:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return BuildFacts()

        scripts = document.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}

        commands: list[str] = []

        if "test" in scripts:
            commands.append("npm test")

        if "build" in scripts:
            commands.append("npm run build")

        if "lint" in scripts:
            commands.append("npm run lint")

        if "start" in scripts:
            commands.append("npm start")

        return BuildFacts(
            inferred_commands=commands,
        )

    def _analyze_composer(
        self,
        path: Path,
        relative_path: str,
    ) -> BuildFacts:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return BuildFacts()

        scripts = document.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}

        commands = ["composer install"]

        for script_name in ("test", "lint", "analyse", "analyze", "build"):
            if script_name in scripts:
                commands.append(f"composer {script_name}")

        return BuildFacts(
            inferred_commands=commands,
        )

    def _analyze_ant(
        self,
        relative_path: str,
    ) -> BuildFacts:
        return BuildFacts(
            inferred_commands=["ant"],
        )

    @staticmethod
    def _xml_namespace(tag: str) -> str:
        if tag.startswith("{") and "}" in tag:
            return tag[1 : tag.index("}")]

        return ""

    @staticmethod
    def _qualified_name(name: str, namespace: str) -> str:
        if not namespace:
            return name

        parts = name.split("/")
        return "/".join(f"{{{namespace}}}{part}" for part in parts)

    def _find_text(
        self,
        element: ElementTree.Element,
        name: str,
        namespace: str,
    ) -> str | None:
        child = element.find(self._qualified_name(name, namespace))

        if child is None or child.text is None:
            return None

        value = child.text.strip()
        return value or None

    def _find_all_text(
        self,
        element: ElementTree.Element,
        name: str,
        namespace: str,
    ) -> list[str]:
        return [
            child.text.strip()
            for child in element.findall(self._qualified_name(name, namespace))
            if child.text and child.text.strip()
        ]

    def _maven_plugins(
        self,
        project: ElementTree.Element,
        namespace: str,
    ) -> list[str]:
        plugin_paths = (
            "build/plugins/plugin",
            "build/pluginManagement/plugins/plugin",
        )

        plugins: list[str] = []

        for plugin_path in plugin_paths:
            for plugin in project.findall(self._qualified_name(plugin_path, namespace)):
                group_id = self._find_text(
                    plugin,
                    "groupId",
                    namespace,
                )
                artifact_id = self._find_text(
                    plugin,
                    "artifactId",
                    namespace,
                )

                if not artifact_id:
                    continue

                plugins.append(f"{group_id}:{artifact_id}" if group_id else artifact_id)

        return list(dict.fromkeys(plugins))

    def _maven_properties(
        self,
        project: ElementTree.Element,
        namespace: str,
    ) -> dict[str, str]:
        properties_element = project.find(self._qualified_name("properties", namespace))

        if properties_element is None:
            return {}

        properties: dict[str, str] = {}

        for child in properties_element:
            name = child.tag.split("}")[-1]

            if child.text and child.text.strip():
                properties[name] = child.text.strip()

        return properties

    @staticmethod
    def _maven_wrapper_available(
        root: Path,
        build_file: Path,
    ) -> bool:
        candidates = [
            build_file.parent / "mvnw",
            root / "mvnw",
        ]
        return any(candidate.is_file() for candidate in candidates)

    @staticmethod
    def _gradle_wrapper_available(
        root: Path,
        build_file: Path,
    ) -> bool:
        candidates = [
            build_file.parent / "gradlew",
            root / "gradlew",
        ]
        return any(candidate.is_file() for candidate in candidates)

    @staticmethod
    def _gradle_plugins(content: str) -> list[str]:
        patterns = [
            r"\bid\s*\(?\s*[\"']([^\"']+)[\"']",
            r"\bapply\s+plugin:\s*[\"']([^\"']+)[\"']",
            r"\b([A-Za-z][A-Za-z0-9_.-]+)\s*$",
        ]

        plugin_block_match = re.search(
            r"plugins\s*\{(?P<body>.*?)\}",
            content,
            flags=re.DOTALL,
        )

        searchable_content = plugin_block_match.group("body") if plugin_block_match else content

        plugins: list[str] = []

        for pattern in patterns:
            plugins.extend(
                match.group(1)
                for match in re.finditer(
                    pattern,
                    searchable_content,
                    flags=re.MULTILINE,
                )
            )

        return list(dict.fromkeys(plugins))

    @staticmethod
    def _regex_values(
        content: str,
        patterns: list[str],
    ) -> list[str]:
        values: list[str] = []

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                value = match.group(1).strip()

                if value:
                    values.append(value.replace("_", "."))

        return list(dict.fromkeys(values))

    @staticmethod
    def _non_empty(*values: str | None) -> list[str]:
        return list(dict.fromkeys(value for value in values if value is not None and value.strip()))
