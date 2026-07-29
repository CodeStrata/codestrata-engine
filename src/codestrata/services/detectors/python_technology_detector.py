"""Technology detector for Python repositories."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from codestrata.models import Repository, Technology, TechnologyCategory

_PYTHON_MANIFEST_NAMES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
        "uv.lock",
        "requirements.txt",
    }
)

_REQUIREMENTS_NAME = re.compile(r"^requirements(?:[-.].+)?\.txt$", re.IGNORECASE)
_REQUIREMENT_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(.*)$")

_FRAMEWORK_PACKAGES: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "aiohttp": "aiohttp",
    "sanic": "Sanic",
}

_TESTING_PACKAGES: dict[str, str] = {
    "pytest": "pytest",
    "unittest2": "unittest",
    "nose": "nose",
    "nose2": "nose2",
}


class PythonTechnologyDetector:
    """Detects Python ecosystem technologies across nested workspace layouts."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect Python language, packaging, frameworks, and test tools."""

        technologies: list[Technology] = []
        py_files = [path for path in repository.files if path.lower().endswith(".py")]
        manifest_paths = [
            path
            for path in repository.files
            if Path(path).name in _PYTHON_MANIFEST_NAMES
            or _REQUIREMENTS_NAME.match(Path(path).name) is not None
        ]

        if not py_files and not manifest_paths:
            return technologies

        technologies.append(
            Technology(
                name="Python",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0 if py_files else 0.9,
                source="file_extension_or_python_manifest",
            )
        )

        if any(Path(path).name == "uv.lock" for path in manifest_paths):
            technologies.append(
                Technology(
                    name="uv",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="uv.lock",
                )
            )
        elif any(Path(path).name == "poetry.lock" for path in manifest_paths):
            technologies.append(
                Technology(
                    name="Poetry",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="poetry.lock",
                )
            )
        elif any(Path(path).name == "Pipfile" for path in manifest_paths):
            technologies.append(
                Technology(
                    name="Pipenv",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=1.0,
                    source="Pipfile",
                )
            )
        elif manifest_paths:
            technologies.append(
                Technology(
                    name="pip",
                    category=TechnologyCategory.BUILD_TOOL,
                    confidence=0.85,
                    source="python_manifest",
                )
            )

        package_versions = self._collect_package_versions(repository, manifest_paths)
        seen_frameworks: set[str] = set()
        seen_tests: set[str] = set()

        for package_name, version in package_versions.items():
            lower = package_name.lower()
            framework = _FRAMEWORK_PACKAGES.get(lower)
            if framework is not None and framework not in seen_frameworks:
                seen_frameworks.add(framework)
                technologies.append(
                    Technology(
                        name=framework,
                        version=version,
                        category=TechnologyCategory.FRAMEWORK,
                        confidence=1.0,
                        source="python_manifest_dependency",
                    )
                )
            test_tool = _TESTING_PACKAGES.get(lower)
            if test_tool is not None and test_tool not in seen_tests:
                seen_tests.add(test_tool)
                technologies.append(
                    Technology(
                        name=test_tool,
                        version=version,
                        category=TechnologyCategory.TESTING,
                        confidence=1.0,
                        source="python_manifest_dependency",
                    )
                )

        # Source import markers as a secondary signal when manifests omit deps.
        if "FastAPI" not in seen_frameworks and self._source_mentions(
            repository, py_files, ("from fastapi", "import fastapi")
        ):
            technologies.append(
                Technology(
                    name="FastAPI",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="python_source_import",
                )
            )
        if "Flask" not in seen_frameworks and self._source_mentions(
            repository, py_files, ("from flask", "import flask")
        ):
            technologies.append(
                Technology(
                    name="Flask",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="python_source_import",
                )
            )
        if "Django" not in seen_frameworks and self._source_mentions(
            repository, py_files, ("from django", "import django")
        ):
            technologies.append(
                Technology(
                    name="Django",
                    category=TechnologyCategory.FRAMEWORK,
                    confidence=0.9,
                    source="python_source_import",
                )
            )

        return technologies

    def _collect_package_versions(
        self,
        repository: Repository,
        manifest_paths: list[str],
    ) -> dict[str, str | None]:
        packages: dict[str, str | None] = {}
        for relative in manifest_paths:
            name = Path(relative).name
            absolute = repository.path / relative
            try:
                text = absolute.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if name == "pyproject.toml":
                packages.update(self._parse_pyproject(text))
            elif _REQUIREMENTS_NAME.match(name):
                packages.update(self._parse_requirements(text))
            elif name == "Pipfile":
                packages.update(self._parse_pipfile(text))
        return packages

    def _parse_pyproject(self, text: str) -> dict[str, str | None]:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return {}
        packages: dict[str, str | None] = {}
        project = data.get("project")
        if isinstance(project, dict):
            packages.update(self._parse_pep621_deps(project.get("dependencies")))
            optional = project.get("optional-dependencies")
            if isinstance(optional, dict):
                for group in optional.values():
                    packages.update(self._parse_pep621_deps(group))
        tool = data.get("tool")
        if isinstance(tool, dict):
            poetry = tool.get("poetry")
            if isinstance(poetry, dict):
                packages.update(self._parse_mapping_deps(poetry.get("dependencies")))
                packages.update(self._parse_mapping_deps(poetry.get("dev-dependencies")))
                group = poetry.get("group")
                if isinstance(group, dict):
                    for section in group.values():
                        if isinstance(section, dict):
                            packages.update(self._parse_mapping_deps(section.get("dependencies")))
        return packages

    def _parse_pep621_deps(self, value: object) -> dict[str, str | None]:
        if not isinstance(value, list):
            return {}
        packages: dict[str, str | None] = {}
        for item in value:
            if not isinstance(item, str):
                continue
            name, version = self._split_requirement(item)
            if name:
                packages[name] = version
        return packages

    def _parse_mapping_deps(self, value: object) -> dict[str, str | None]:
        if not isinstance(value, dict):
            return {}
        packages: dict[str, str | None] = {}
        for raw_name, raw_version in value.items():
            name = str(raw_name).strip()
            if not name or name.lower() == "python":
                continue
            version: str | None
            if isinstance(raw_version, str):
                version = raw_version
            elif isinstance(raw_version, dict):
                version = str(raw_version.get("version") or "") or None
            else:
                version = None
            packages[name] = version
        return packages

    def _parse_requirements(self, text: str) -> dict[str, str | None]:
        packages: dict[str, str | None] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-")):
                continue
            name, version = self._split_requirement(stripped)
            if name:
                packages[name] = version
        return packages

    def _parse_pipfile(self, text: str) -> dict[str, str | None]:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return {}
        packages: dict[str, str | None] = {}
        for section_name in ("packages", "dev-packages"):
            packages.update(self._parse_mapping_deps(data.get(section_name)))
        return packages

    def _split_requirement(self, value: str) -> tuple[str, str | None]:
        compact = value.strip().split(";", 1)[0].strip()
        if not compact:
            return "", None
        match = _REQUIREMENT_LINE.match(compact)
        if match is None:
            return "", None
        name = match.group(1).strip()
        remainder = match.group(2).strip()
        if not remainder:
            return name, None
        for separator in ("===", "==", ">=", "<=", "~=", "!=", ">", "<"):
            if remainder.startswith(separator):
                return name, remainder
        return name, remainder or None

    def _source_mentions(
        self,
        repository: Repository,
        py_files: list[str],
        needles: tuple[str, ...],
    ) -> bool:
        sample = py_files[:40]
        lower_needles = tuple(item.lower() for item in needles)
        for relative in sample:
            try:
                text = (repository.path / relative).read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                continue
            lower = text.lower()
            if any(needle in lower for needle in lower_needles):
                return True
        return False
