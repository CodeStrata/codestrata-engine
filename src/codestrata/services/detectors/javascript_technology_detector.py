"""Technology detector for JavaScript repositories."""

import json
from typing import Any

from codestrata.models import Repository, Technology, TechnologyCategory


class JavaScriptTechnologyDetector:
    """Detects JavaScript and TypeScript ecosystem technologies."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect JavaScript ecosystem technologies."""

        file_set = set(repository.files)
        technologies: list[Technology] = []

        has_javascript_files = any(
            file_path.endswith((".js", ".jsx", ".mjs", ".cjs")) for file_path in repository.files
        )

        has_typescript_files = any(
            file_path.endswith((".ts", ".tsx")) for file_path in repository.files
        )

        if has_javascript_files or "package.json" in file_set:
            technologies.append(
                Technology(
                    name="JavaScript",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="file_extension_or_package.json",
                )
            )

        if has_typescript_files or "tsconfig.json" in file_set:
            technologies.append(
                Technology(
                    name="TypeScript",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="file_extension_or_tsconfig.json",
                )
            )

        if "package.json" not in file_set:
            return technologies

        technologies.append(
            Technology(
                name="Node.js",
                category=TechnologyCategory.RUNTIME,
                confidence=0.9,
                source="package.json",
            )
        )

        if "package-lock.json" in file_set:
            technologies.append(
                Technology(
                    name="npm",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="package-lock.json",
                )
            )
        elif "yarn.lock" in file_set:
            technologies.append(
                Technology(
                    name="Yarn",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="yarn.lock",
                )
            )
        elif "pnpm-lock.yaml" in file_set:
            technologies.append(
                Technology(
                    name="pnpm",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="pnpm-lock.yaml",
                )
            )
        else:
            technologies.append(
                Technology(
                    name="npm",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=0.7,
                    source="package.json",
                )
            )

        package_data = self._read_package_json(repository)

        dependencies = self._collect_dependencies(package_data)

        framework_mappings = {
            "react": "React",
            "next": "Next.js",
            "@angular/core": "Angular",
            "vue": "Vue.js",
            "express": "Express",
        }

        for dependency_name, technology_name in framework_mappings.items():
            if dependency_name in dependencies:
                technologies.append(
                    Technology(
                        name=technology_name,
                        version=dependencies[dependency_name],
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=1.0,
                        source="package.json",
                    )
                )

        testing_mappings = {
            "jest": "Jest",
            "vitest": "Vitest",
            "mocha": "Mocha",
        }

        for dependency_name, technology_name in testing_mappings.items():
            if dependency_name in dependencies:
                technologies.append(
                    Technology(
                        name=technology_name,
                        version=dependencies[dependency_name],
                        category=TechnologyCategory.TESTING,
                        confidence=1.0,
                        source="package.json",
                    )
                )

        return technologies

    def _read_package_json(
        self,
        repository: Repository,
    ) -> dict[str, Any]:
        """Read and parse package.json."""

        package_file = repository.path / "package.json"

        try:
            content = package_file.read_text(
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
        package_data: dict[str, Any],
    ) -> dict[str, str]:
        """Combine runtime and development dependencies."""

        dependencies: dict[str, str] = {}

        for section_name in ("dependencies", "devDependencies"):
            section = package_data.get(section_name, {})

            if isinstance(section, dict):
                dependencies.update({str(name): str(version) for name, version in section.items()})

        return dependencies
