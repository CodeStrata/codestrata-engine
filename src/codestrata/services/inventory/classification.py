"""Data-driven repository file-kind classification.

Rules are evaluated in priority order. Exact basenames win over path markers,
filename suffixes, and extensions. No source parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from codestrata.domain.repository.enums import RepositoryFileKind


@dataclass(frozen=True, slots=True)
class _ExactNameRule:
    names: frozenset[str]
    kind: RepositoryFileKind


@dataclass(frozen=True, slots=True)
class _SuffixRule:
    suffixes: tuple[str, ...]
    kind: RepositoryFileKind


@dataclass(frozen=True, slots=True)
class _ExtensionRule:
    extensions: frozenset[str]
    kind: RepositoryFileKind


@dataclass(frozen=True, slots=True)
class _PathMarkerRule:
    markers: tuple[str, ...]
    kind: RepositoryFileKind


_EXACT_NAME_RULES: tuple[_ExactNameRule, ...] = (
    _ExactNameRule(
        frozenset(
            {
                "pom.xml",
                "package.json",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "requirements.txt",
                "pipfile",
                "pipfile.lock",
                "poetry.lock",
                "go.mod",
                "go.sum",
                "cargo.toml",
                "cargo.lock",
                "composer.json",
                "composer.lock",
                "gemfile",
                "gemfile.lock",
                "packages.config",
            }
        ),
        RepositoryFileKind.DEPENDENCY_MANIFEST,
    ),
    _ExactNameRule(
        frozenset(
            {
                "build.gradle",
                "build.gradle.kts",
                "settings.gradle",
                "settings.gradle.kts",
                "makefile",
                "cmakelists.txt",
                "build.xml",
                "rakefile",
            }
        ),
        RepositoryFileKind.BUILD,
    ),
    _ExactNameRule(
        frozenset(
            {
                "dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "compose.yml",
                "compose.yaml",
                "jenkinsfile",
                "procfile",
                "vagrantfile",
            }
        ),
        RepositoryFileKind.INFRASTRUCTURE,
    ),
    _ExactNameRule(
        frozenset(
            {
                "readme",
                "readme.md",
                "readme.txt",
                "readme.rst",
                "changelog",
                "changelog.md",
                "license",
                "license.md",
                "license.txt",
                "contributing.md",
            }
        ),
        RepositoryFileKind.DOCUMENTATION,
    ),
    _ExactNameRule(
        frozenset(
            {
                "application.yml",
                "application.yaml",
                "application.properties",
                "application-dev.yml",
                "application-dev.yaml",
                "application-prod.yml",
                "application-prod.yaml",
                ".editorconfig",
                ".gitignore",
                ".gitattributes",
                ".npmrc",
                ".nvmrc",
            }
        ),
        RepositoryFileKind.CONFIGURATION,
    ),
)

_PATH_MARKER_RULES: tuple[_PathMarkerRule, ...] = (
    _PathMarkerRule(
        ("generated-sources", "generated-test-sources", "__generated__", "generated"),
        RepositoryFileKind.GENERATED,
    ),
    _PathMarkerRule(
        ("src/test", "src/tests", "__tests__", "testdata"),
        RepositoryFileKind.TEST,
    ),
    _PathMarkerRule(
        (
            ".github/workflows",
            ".gitlab-ci",
            "deployments",
            "k8s",
            "kubernetes",
            "terraform",
            "helm",
            "charts",
            ".devcontainer",
        ),
        RepositoryFileKind.INFRASTRUCTURE,
    ),
    _PathMarkerRule(("docs", "documentation"), RepositoryFileKind.DOCUMENTATION),
)

_SUFFIX_RULES: tuple[_SuffixRule, ...] = (
    _SuffixRule(
        (
            "test.java",
            "tests.java",
            "ittest.java",
            "test.kt",
            "tests.kt",
            "test.php",
            "test.py",
            "_test.py",
            "_test.go",
            ".spec.js",
            ".spec.jsx",
            ".spec.ts",
            ".spec.tsx",
            ".test.js",
            ".test.jsx",
            ".test.ts",
            ".test.tsx",
        ),
        RepositoryFileKind.TEST,
    ),
)

_EXTENSION_RULES: tuple[_ExtensionRule, ...] = (
    _ExtensionRule(
        frozenset({".tf", ".tfvars", ".hcl"}),
        RepositoryFileKind.INFRASTRUCTURE,
    ),
    _ExtensionRule(
        frozenset({".md", ".markdown", ".rst", ".adoc"}),
        RepositoryFileKind.DOCUMENTATION,
    ),
    _ExtensionRule(
        frozenset(
            {
                ".yml",
                ".yaml",
                ".properties",
                ".ini",
                ".cfg",
                ".conf",
                ".config",
                ".toml",
                ".env",
            }
        ),
        RepositoryFileKind.CONFIGURATION,
    ),
    _ExtensionRule(
        frozenset({".gradle", ".cmake", ".make"}),
        RepositoryFileKind.BUILD,
    ),
    _ExtensionRule(
        frozenset(
            {
                ".java",
                ".kt",
                ".kts",
                ".scala",
                ".groovy",
                ".py",
                ".pyi",
                ".js",
                ".jsx",
                ".mjs",
                ".cjs",
                ".ts",
                ".tsx",
                ".php",
                ".cs",
                ".go",
                ".rb",
                ".rs",
                ".swift",
                ".c",
                ".h",
                ".cpp",
                ".cc",
                ".cxx",
                ".hpp",
            }
        ),
        RepositoryFileKind.SOURCE,
    ),
)

_MEDIA_TYPES: dict[str, str] = {
    ".java": "text/x-java-source",
    ".kt": "text/x-kotlin",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".php": "application/x-php",
    ".json": "application/json",
    ".xml": "application/xml",
    ".yml": "application/yaml",
    ".yaml": "application/yaml",
    ".md": "text/markdown",
    ".properties": "text/x-java-properties",
    ".gradle": "text/x-gradle",
}


def _path_contains_marker(normalized_path: str, marker: str) -> bool:
    lowered = normalized_path.lower()
    if "/" in marker:
        padded = f"/{lowered}/"
        return f"/{marker}/" in padded
    return marker in PurePosixPath(lowered).parts


class RepositoryFileKindClassifier:
    """Classify repository-relative paths into ``RepositoryFileKind`` values."""

    def classify(self, relative_path: str) -> RepositoryFileKind:
        normalized = relative_path.replace("\\", "/")
        posix = PurePosixPath(normalized)
        filename = posix.name
        lowered_name = filename.lower()

        for exact_rule in _EXACT_NAME_RULES:
            if lowered_name in exact_rule.names:
                return exact_rule.kind

        for path_rule in _PATH_MARKER_RULES:
            if any(_path_contains_marker(normalized, marker) for marker in path_rule.markers):
                return path_rule.kind

        for suffix_rule in _SUFFIX_RULES:
            if any(lowered_name.endswith(suffix) for suffix in suffix_rule.suffixes):
                return suffix_rule.kind

        for extension_rule in _EXTENSION_RULES:
            for extension in sorted(extension_rule.extensions, key=len, reverse=True):
                if lowered_name.endswith(extension):
                    return extension_rule.kind

        return RepositoryFileKind.UNKNOWN

    def media_type(self, relative_path: str) -> str | None:
        """Return a best-effort media type from the file extension."""

        lowered = PurePosixPath(relative_path.replace("\\", "/")).name.lower()
        for extension, media_type in sorted(
            _MEDIA_TYPES.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if lowered.endswith(extension):
                return media_type
        return None

    def is_generated(self, relative_path: str) -> bool:
        """Return whether path markers indicate generated content."""

        return self.classify(relative_path) is RepositoryFileKind.GENERATED
