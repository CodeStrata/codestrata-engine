"""Extract dependency metadata from supported manifest files."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    Dependency,
    DependencyFacts,
    Repository,
    RepositoryFacts,
    Technology,
)
from codestrata.services.analyzers.maven_dependency_parser import (
    MavenDependencyParser,
)


class DependencyMetadataAnalyzer:
    """Extract direct dependencies from repository manifests."""

    def __init__(self) -> None:
        self._maven_parser = MavenDependencyParser(
            dependency_classifier=self._classify_dependency,
        )

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Parse supported dependency manifests."""

        del technologies
        del facts

        dependencies: list[Dependency] = []

        for relative_path in repository.files:
            manifest_path = repository.path / relative_path

            if relative_path.endswith("pom.xml"):
                dependencies.extend(
                    self._maven_parser.parse(
                        manifest_path=manifest_path,
                        relative_path=relative_path,
                    )
                )

            elif relative_path.endswith("package.json"):
                dependencies.extend(
                    self._parse_npm(
                        manifest_path=manifest_path,
                        relative_path=relative_path,
                    )
                )

            elif relative_path.endswith("composer.json"):
                dependencies.extend(
                    self._parse_composer(
                        manifest_path=manifest_path,
                        relative_path=relative_path,
                    )
                )

            elif (
                relative_path.lower().endswith((".csproj", ".fsproj", ".vbproj"))
                or Path(relative_path).name.lower() == "packages.config"
            ):
                dependencies.extend(
                    self._parse_nuget(
                        manifest_path=manifest_path,
                        relative_path=relative_path,
                    )
                )

        dependencies.sort(
            key=lambda dependency: (
                dependency.ecosystem,
                dependency.manifest_path,
                dependency.name,
                dependency.scope,
            )
        )

        dependency_facts = self._build_dependency_facts(dependencies)

        return AnalyzerResult(
            findings=[],
            facts=RepositoryFacts(
                dependencies=dependency_facts,
            ),
        )

    def _parse_npm(
        self,
        manifest_path: Path,
        relative_path: str,
    ) -> list[Dependency]:
        """Parse dependencies from an npm package.json file."""

        if not manifest_path.is_file():
            return []

        try:
            package_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return []

        if not isinstance(package_data, dict):
            return []

        dependency_sections = {
            "dependencies": "runtime",
            "devDependencies": "development",
            "peerDependencies": "peer",
            "optionalDependencies": "optional",
        }

        dependencies: list[Dependency] = []

        for section_name, scope in dependency_sections.items():
            section = package_data.get(section_name, {})

            if not isinstance(section, dict):
                continue

            for name, version_value in section.items():
                if not isinstance(name, str):
                    continue

                version = version_value if isinstance(version_value, str) else None

                dependencies.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem="npm",
                        scope=scope,
                        manifest_path=relative_path,
                        categories=self._classify_dependency(
                            name=name,
                            ecosystem="npm",
                        ),
                        dynamic_version=self._is_dynamic_npm_version(version),
                        unmanaged_version=version is None,
                        version_managed=False,
                        version_source=("dependency" if version is not None else None),
                    )
                )

        return dependencies

    def _parse_composer(
        self,
        manifest_path: Path,
        relative_path: str,
    ) -> list[Dependency]:
        """Parse dependencies from a Composer composer.json file."""

        if not manifest_path.is_file():
            return []

        try:
            composer_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return []

        if not isinstance(composer_data, dict):
            return []

        dependency_sections = {
            "require": "runtime",
            "require-dev": "development",
        }

        dependencies: list[Dependency] = []

        for section_name, scope in dependency_sections.items():
            section = composer_data.get(section_name, {})

            if not isinstance(section, dict):
                continue

            for name, version_value in section.items():
                if not isinstance(name, str):
                    continue
                package_name = name.strip()
                lower = package_name.lower()
                if lower == "php" or lower.startswith("ext-") or lower.startswith("lib-"):
                    continue

                version = version_value if isinstance(version_value, str) else None

                dependencies.append(
                    Dependency(
                        name=package_name,
                        version=version,
                        ecosystem="composer",
                        scope=scope,
                        manifest_path=relative_path,
                        categories=self._classify_dependency(
                            name=package_name,
                            ecosystem="composer",
                        ),
                        dynamic_version=self._is_dynamic_composer_version(version),
                        unmanaged_version=version is None,
                        version_managed=False,
                        version_source=("dependency" if version is not None else None),
                    )
                )

        return dependencies

    def _parse_nuget(
        self,
        manifest_path: Path,
        relative_path: str,
    ) -> list[Dependency]:
        """Parse PackageReference or packages.config NuGet declarations."""

        if not manifest_path.is_file():
            return []

        try:
            text = manifest_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        from codestrata.services.repository_graph.extractors.nuget_parser import (
            parse_nuget_dependencies,
        )

        parsed = parse_nuget_dependencies(text.encode("utf-8"), source_file=relative_path)
        dependencies: list[Dependency] = []
        for item in parsed:
            version = item.version.raw if item.version is not None else None
            dependencies.append(
                Dependency(
                    name=item.name,
                    version=version,
                    ecosystem="nuget",
                    scope="runtime",
                    manifest_path=relative_path,
                    categories=self._classify_dependency(
                        name=item.name,
                        ecosystem="nuget",
                    ),
                    dynamic_version=self._is_dynamic_nuget_version(version),
                    unmanaged_version=version is None,
                    version_managed=False,
                    version_source=("dependency" if version is not None else None),
                )
            )
        return dependencies

    def _build_dependency_facts(
        self,
        dependencies: list[Dependency],
    ) -> DependencyFacts:
        """Build aggregate facts from extracted dependencies."""

        return DependencyFacts(
            dependencies=dependencies,
            dependency_count=len(dependencies),
            direct_dependency_count=len(dependencies),
            development_dependency_count=sum(
                dependency.scope == "development" for dependency in dependencies
            ),
            test_dependency_count=sum(
                dependency.scope == "test" or "testing" in dependency.categories
                for dependency in dependencies
            ),
            framework_dependencies=self._dependencies_in_category(
                dependencies,
                "framework",
            ),
            database_drivers=self._dependencies_in_category(
                dependencies,
                "database",
            ),
            cloud_sdks=self._dependencies_in_category(
                dependencies,
                "cloud",
            ),
            logging_libraries=self._dependencies_in_category(
                dependencies,
                "logging",
            ),
            testing_libraries=self._dependencies_in_category(
                dependencies,
                "testing",
            ),
            security_libraries=self._dependencies_in_category(
                dependencies,
                "security",
            ),
            dynamic_version_dependencies=[
                dependency.name for dependency in dependencies if dependency.dynamic_version
            ],
            unmanaged_version_dependencies=[
                dependency.name for dependency in dependencies if dependency.unmanaged_version
            ],
        )

    def _dependencies_in_category(
        self,
        dependencies: list[Dependency],
        category: str,
    ) -> list[str]:
        """Return dependency names belonging to a category."""

        return list(
            dict.fromkeys(
                dependency.name for dependency in dependencies if category in dependency.categories
            )
        )

    def _classify_dependency(
        self,
        name: str,
        ecosystem: str,
    ) -> list[str]:
        """Apply deterministic dependency classifications."""

        normalized_name = name.lower()
        categories: list[str] = []

        category_patterns = {
            "framework": (
                "spring-boot",
                "spring-framework",
                "react",
                "angular",
                "vue",
                "next",
                "express",
                "laravel/framework",
                "symfony/framework-bundle",
                "symfony/symfony",
                "codeigniter4/framework",
                "laminas/laminas-mvc",
            ),
            "database": (
                "postgresql",
                "mysql",
                "mariadb",
                "oracle",
                "mongodb",
                "mongoose",
                "hibernate",
                "jdbc",
                "doctrine/orm",
                "illuminate/database",
            ),
            "cloud": (
                "aws-sdk",
                "software.amazon.awssdk",
                "azure",
                "google-cloud",
                "@aws-sdk",
                "aws/aws-sdk-php",
            ),
            "logging": (
                "slf4j",
                "logback",
                "log4j",
                "winston",
                "pino",
                "monolog/monolog",
            ),
            "testing": (
                "junit",
                "mockito",
                "assertj",
                "jest",
                "vitest",
                "mocha",
                "cypress",
                "playwright",
                "phpunit/phpunit",
                "pestphp/pest",
                "codeception/codeception",
            ),
            "security": (
                "spring-security",
                "oauth",
                "jwt",
                "jsonwebtoken",
                "passport",
                "firebase/php-jwt",
                "league/oauth2",
            ),
        }

        for category, patterns in category_patterns.items():
            if any(pattern in normalized_name for pattern in patterns):
                categories.append(category)

        if ecosystem == "npm" and normalized_name in {
            "react",
            "vue",
            "express",
        }:
            if "framework" not in categories:
                categories.append("framework")

        if ecosystem == "composer" and normalized_name in {
            "laravel/framework",
            "symfony/framework-bundle",
            "symfony/symfony",
            "codeigniter4/framework",
            "laminas/laminas-mvc",
        }:
            if "framework" not in categories:
                categories.append("framework")

        if ecosystem == "nuget" and (
            normalized_name.startswith("microsoft.aspnetcore")
            or normalized_name.startswith("microsoft.entityframeworkcore")
            or normalized_name in {"entityframework", "microsoft.aspnet.mvc"}
        ):
            if "framework" not in categories:
                categories.append("framework")

        return categories

    def _is_dynamic_npm_version(
        self,
        version: str | None,
    ) -> bool:
        """Determine whether an npm dependency uses a dynamic version."""

        if version is None:
            return False

        normalized_version = version.strip().lower()

        return (
            normalized_version in {"*", "latest", ""}
            or normalized_version.startswith("^")
            or normalized_version.startswith("~")
            or normalized_version.startswith(">")
            or normalized_version.startswith("<")
            or "||" in normalized_version
            or " - " in normalized_version
            or normalized_version.startswith("git")
            or normalized_version.startswith("http")
            or normalized_version.startswith("file:")
        )

    def _is_dynamic_composer_version(
        self,
        version: str | None,
    ) -> bool:
        """Determine whether a Composer constraint is dynamic."""

        if version is None:
            return False

        normalized_version = version.strip().lower()
        return (
            normalized_version in {"*", "dev-main", "dev-master", ""}
            or normalized_version.startswith("^")
            or normalized_version.startswith("~")
            or normalized_version.startswith(">")
            or normalized_version.startswith("<")
            or normalized_version.startswith("dev-")
            or "||" in normalized_version
            or "," in normalized_version
            or normalized_version.startswith("as ")
        )

    def _is_dynamic_nuget_version(
        self,
        version: str | None,
    ) -> bool:
        """Determine whether a NuGet version expression is dynamic."""

        if version is None:
            return False
        normalized_version = version.strip().lower()
        return (
            normalized_version in {"*", ""}
            or "*" in normalized_version
            or normalized_version.startswith("[")
            or normalized_version.startswith("(")
            or "," in normalized_version
        )
