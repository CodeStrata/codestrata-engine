"""Technology detector for Java repositories."""

from __future__ import annotations

import re

from codestrata.models import Repository, Technology, TechnologyCategory

_JAVA_VERSION_PROPERTY = re.compile(
    r"<java\.version>\s*([^<]+)\s*</java\.version>",
    re.IGNORECASE,
)
_SPRING_BOOT_PARENT_VERSION = re.compile(
    r"<artifactId>\s*spring-boot-starter-parent\s*</artifactId>\s*"
    r"<version>\s*([^<]+)\s*</version>",
    re.IGNORECASE | re.DOTALL,
)
_SPRING_BOOT_PLUGIN_VERSION = re.compile(
    r'id\s*\(?\s*["\']org\.springframework\.boot["\']\s*\)?\s*version\s+["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class JavaTechnologyDetector:
    """Detects Java technologies from repository files."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect Java ecosystem technologies."""

        file_set = set(repository.files)
        technologies: list[Technology] = []

        has_java_files = any(file_path.endswith(".java") for file_path in repository.files)

        if has_java_files:
            java_version: str | None = None
            if "pom.xml" in file_set:
                pom_preview = self._read_file(repository, "pom.xml")
                match = _JAVA_VERSION_PROPERTY.search(pom_preview)
                if match:
                    java_version = match.group(1).strip() or None
            technologies.append(
                Technology(
                    name="Java",
                    version=java_version,
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="file_extension",
                )
            )

        spring_boot_seen = False

        if "pom.xml" in file_set:
            technologies.append(
                Technology(
                    name="Maven",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="pom.xml",
                )
            )

            pom_content = self._read_file(repository, "pom.xml")

            if "spring-boot" in pom_content:
                spring_version = None
                parent_match = _SPRING_BOOT_PARENT_VERSION.search(pom_content)
                if parent_match:
                    spring_version = parent_match.group(1).strip() or None
                technologies.append(
                    Technology(
                        name="Spring Boot",
                        version=spring_version,
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=0.95,
                        source="pom.xml",
                    )
                )
                spring_boot_seen = True

            if "junit" in pom_content.lower():
                technologies.append(
                    Technology(
                        name="JUnit",
                        category=TechnologyCategory.TESTING,
                        confidence=0.9,
                        source="pom.xml",
                    )
                )

            if (
                "hibernate" in pom_content.lower()
                or "jakarta.persistence" in pom_content.lower()
                or "javax.persistence" in pom_content.lower()
            ):
                technologies.append(
                    Technology(
                        name="JPA/Hibernate",
                        category=TechnologyCategory.LIBRARY,
                        confidence=0.9,
                        source="pom.xml",
                    )
                )

        # Detect Gradle from root or nested module manifests (multi-module layouts).
        gradle_manifest_names = {
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        }
        gradle_paths = sorted(
            path
            for path in repository.files
            if path.replace("\\", "/").rsplit("/", 1)[-1] in gradle_manifest_names
        )
        detected_gradle_file = next(
            (
                path
                for path in gradle_paths
                if path.replace("\\", "/").rsplit("/", 1)[-1]
                in {"build.gradle", "build.gradle.kts"}
            ),
            gradle_paths[0] if gradle_paths else None,
        )

        if detected_gradle_file is not None:
            technologies.append(
                Technology(
                    name="Gradle",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source=detected_gradle_file,
                )
            )

            gradle_content = "\n".join(
                self._read_file(repository, path) for path in gradle_paths
            )

            if "spring-boot" in gradle_content and not spring_boot_seen:
                spring_version = None
                plugin_match = _SPRING_BOOT_PLUGIN_VERSION.search(gradle_content)
                if plugin_match:
                    spring_version = plugin_match.group(1).strip() or None
                technologies.append(
                    Technology(
                        name="Spring Boot",
                        version=spring_version,
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=0.95,
                        source=detected_gradle_file,
                    )
                )
                spring_boot_seen = True

            if "junit" in gradle_content.lower():
                technologies.append(
                    Technology(
                        name="JUnit",
                        category=TechnologyCategory.TESTING,
                        confidence=0.9,
                        source=detected_gradle_file,
                    )
                )

        application_files = {
            "src/main/resources/application.properties",
            "src/main/resources/application.yml",
            "src/main/resources/application.yaml",
        }

        if any(file_name in file_set for file_name in application_files) and not spring_boot_seen:
            technologies.append(
                Technology(
                    name="Spring Boot",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.8,
                    source="application_configuration",
                )
            )

        return technologies

    def _read_file(
        self,
        repository: Repository,
        relative_path: str,
    ) -> str:
        """Read a repository file safely."""

        file_path = repository.path / relative_path

        try:
            return file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            return ""
