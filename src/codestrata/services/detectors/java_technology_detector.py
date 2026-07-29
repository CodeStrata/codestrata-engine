"""Technology detector for Java repositories."""

from codestrata.models import Repository, Technology, TechnologyCategory


class JavaTechnologyDetector:
    """Detects Java technologies from repository files."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect Java ecosystem technologies."""

        file_set = set(repository.files)
        technologies: list[Technology] = []

        has_java_files = any(file_path.endswith(".java") for file_path in repository.files)

        if has_java_files:
            technologies.append(
                Technology(
                    name="Java",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="file_extension",
                )
            )

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
                technologies.append(
                    Technology(
                        name="Spring Boot",
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=0.95,
                        source="pom.xml",
                    )
                )

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

        gradle_files = {
            "build.gradle",
            "build.gradle.kts",
        }

        detected_gradle_file = next(
            (file_name for file_name in gradle_files if file_name in file_set),
            None,
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

            gradle_content = self._read_file(
                repository,
                detected_gradle_file,
            )

            if "spring-boot" in gradle_content:
                technologies.append(
                    Technology(
                        name="Spring Boot",
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=0.95,
                        source=detected_gradle_file,
                    )
                )

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

        if any(file_name in file_set for file_name in application_files):
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
