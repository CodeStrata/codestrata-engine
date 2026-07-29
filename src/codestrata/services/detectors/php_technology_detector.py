"""Technology detector for PHP repositories."""

import json
from typing import Any

from codestrata.models import Repository, Technology, TechnologyCategory


class PhpTechnologyDetector:
    """Detects PHP ecosystem technologies."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect PHP ecosystem technologies."""

        file_set = set(repository.files)
        technologies: list[Technology] = []

        has_php_files = any(file_path.endswith(".php") for file_path in repository.files)

        if has_php_files or "composer.json" in file_set:
            technologies.append(
                Technology(
                    name="PHP",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="file_extension_or_composer.json",
                )
            )

        if "composer.json" in file_set:
            technologies.append(
                Technology(
                    name="Composer",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="composer.json",
                )
            )

            composer_data = self._read_composer_json(repository)
            dependencies = self._collect_dependencies(composer_data)

            framework_mappings = {
                "laravel/framework": "Laravel",
                "symfony/framework-bundle": "Symfony",
                "symfony/symfony": "Symfony",
                "codeigniter4/framework": "CodeIgniter",
                "codeigniter/framework": "CodeIgniter",
                "laminas/laminas-mvc": "Laminas",
                "laminas/laminas-servicemanager": "Laminas",
                "zendframework/zendframework": "Laminas",
            }

            for dependency_name, technology_name in framework_mappings.items():
                if dependency_name in dependencies:
                    technologies.append(
                        Technology(
                            name=technology_name,
                            version=dependencies[dependency_name],
                            category=TechnologyCategory.FRAMEWORK,
                            confidence=1.0,
                            source="composer.json",
                        )
                    )

            if "phpunit/phpunit" in dependencies:
                technologies.append(
                    Technology(
                        name="PHPUnit",
                        version=dependencies["phpunit/phpunit"],
                        category=TechnologyCategory.TESTING,
                        confidence=1.0,
                        source="composer.json",
                    )
                )

        if "artisan" in file_set:
            technologies.append(
                Technology(
                    name="Laravel",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.95,
                    source="artisan",
                )
            )

        if any(
            name in file_set
            for name in ("spark", "system/CodeIgniter.php", "app/Config/Paths.php")
        ) or any(
            path.startswith("system/") and path.endswith("CodeIgniter.php")
            for path in repository.files
        ):
            technologies.append(
                Technology(
                    name="CodeIgniter",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="codeigniter_structure",
                )
            )

        if "config/application.config.php" in file_set or any(
            path.endswith("module.config.php") for path in repository.files
        ):
            technologies.append(
                Technology(
                    name="Laminas",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="laminas_structure",
                )
            )

        if "wp-config.php" in file_set or any(
            file_path.startswith("wp-content/") for file_path in repository.files
        ):
            technologies.append(
                Technology(
                    name="WordPress",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.95,
                    source="wordpress_structure",
                )
            )

        return self._dedupe_technologies(technologies)

    def _read_composer_json(
        self,
        repository: Repository,
    ) -> dict[str, Any]:
        """Read and parse composer.json."""

        composer_file = repository.path / "composer.json"

        try:
            content = composer_file.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            parsed_content = json.loads(content)

            if isinstance(parsed_content, dict):
                return parsed_content
        except (OSError, json.JSONDecodeError):
            pass

        return {}

    def _collect_dependencies(
        self,
        composer_data: dict[str, Any],
    ) -> dict[str, str]:
        """Combine Composer runtime and development dependencies."""

        dependencies: dict[str, str] = {}

        for section_name in ("require", "require-dev"):
            section = composer_data.get(section_name, {})

            if isinstance(section, dict):
                dependencies.update({str(name): str(version) for name, version in section.items()})

        return dependencies

    def _dedupe_technologies(self, technologies: list[Technology]) -> list[Technology]:
        """Keep the highest-confidence technology per name."""

        ranked: dict[str, Technology] = {}
        for technology in technologies:
            existing = ranked.get(technology.name)
            left = technology.confidence if technology.confidence is not None else 0.0
            if existing is not None and existing.confidence is not None:
                right = existing.confidence
            else:
                right = -1.0
            if existing is None or left > right:
                ranked[technology.name] = technology
            elif (
                existing is not None
                and left == right
                and technology.version
                and not existing.version
            ):
                ranked[technology.name] = technology
        return list(ranked.values())
