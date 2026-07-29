"""Candidate path discovery for repository-testing evidence."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    TestBuildSourceType,
    TestDiscoveryBasis,
    TestFileRole,
)
from codestrata.scan_boundary import default_ignore_path_markers

DEFAULT_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_DIR_MARKERS: tuple[str, ...] = (
    "test",
    "tests",
    "spec",
    "specs",
    "__tests__",
    "cypress",
    "playwright",
    "e2e",
    "integration",
    "integrationtest",
    "fixtures",
    "testdata",
    "test-support",
    "test_support",
    "snapshots",
    "snapshot",
)

_LANGUAGE_BY_SUFFIX: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".groovy": "groovy",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
}


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def is_ignored_path(path: str, *, ignore_markers: Sequence[str]) -> bool:
    normalized = f"/{normalize_relative_path(path).lower()}/"
    return any(marker.lower() in normalized for marker in ignore_markers)


def classification_for_path(path: str) -> SourceClassification:
    return classify_source_path(normalize_relative_path(path))


def language_hint_for_path(path: str) -> str | None:
    suffix = PurePosixPath(normalize_relative_path(path)).suffix.lower()
    return _LANGUAGE_BY_SUFFIX.get(suffix)


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(normalize_relative_path(path)).parts)


def _has_dir_marker(parts: Sequence[str], *names: str) -> bool:
    wanted = {name.lower() for name in names}
    return any(part in wanted for part in parts)


_JUNK_FILENAMES = frozenset(
    {
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
        ".gitkeep",
        ".keep",
    }
)


def _filename_role(
    name: str,
) -> tuple[TestFileRole | None, tuple[TestDiscoveryBasis, ...]]:
    """Match conventional test filenames without weak suffix collisions.

    Importantly, do not treat ``Visit.java`` as ``*IT.java`` via lowercase
    ``endswith("it.java")``.
    """

    bases: list[TestDiscoveryBasis] = [TestDiscoveryBasis.FILENAME_CONVENTION]
    # Preserve original casing for Java/.NET camelCase suffixes.
    if name.endswith("IT.java") or name.endswith("ITCase.java"):
        return TestFileRole.INTEGRATION_TEST, tuple(bases)
    if name.endswith("Tests.java") or name.endswith("Test.java"):
        if "Integration" in name:
            return TestFileRole.INTEGRATION_TEST, tuple(bases)
        return TestFileRole.UNIT_TEST, tuple(bases)
    if name.endswith("Tests.cs") or name.endswith("Test.cs"):
        return TestFileRole.UNIT_TEST, tuple(bases)
    if name.endswith("Spec.groovy"):
        return TestFileRole.UNKNOWN_TEST, tuple(bases)

    lower = name.lower()
    if fnmatch.fnmatch(lower, "test_*.py") or fnmatch.fnmatch(lower, "*_test.py"):
        return TestFileRole.UNIT_TEST, tuple(bases)
    if fnmatch.fnmatch(lower, "*_spec.py"):
        return TestFileRole.UNKNOWN_TEST, tuple(bases)
    if (
        fnmatch.fnmatch(lower, "*.test.js")
        or fnmatch.fnmatch(lower, "*.test.ts")
        or fnmatch.fnmatch(lower, "*.test.jsx")
        or fnmatch.fnmatch(lower, "*.test.tsx")
        or fnmatch.fnmatch(lower, "*.spec.js")
        or fnmatch.fnmatch(lower, "*.spec.ts")
        or fnmatch.fnmatch(lower, "*.spec.jsx")
        or fnmatch.fnmatch(lower, "*.spec.tsx")
    ):
        return TestFileRole.UNIT_TEST, tuple(bases)
    if fnmatch.fnmatch(lower, "*_test.go"):
        return TestFileRole.UNIT_TEST, tuple(bases)
    if fnmatch.fnmatch(lower, "*_spec.rb"):
        return TestFileRole.UNKNOWN_TEST, tuple(bases)
    if (
        fnmatch.fnmatch(lower, "*test.php")
        or fnmatch.fnmatch(lower, "test*.php")
        or lower.endswith("test.php")
    ):
        return TestFileRole.UNIT_TEST, tuple(bases)
    return None, ()


def _is_junk_filename(name: str) -> bool:
    return name.lower() in _JUNK_FILENAMES


def classify_test_candidate(
    path: str,
) -> tuple[TestFileRole | None, tuple[TestDiscoveryBasis, ...], str | None]:
    """Return (role, discovery bases, language_hint) or (None, (), None)."""

    normalized = normalize_relative_path(path)
    if not normalized:
        return None, (), None

    parts = _path_parts(normalized)
    name = PurePosixPath(normalized).name
    if _is_junk_filename(name):
        return None, (), None

    language_hint = language_hint_for_path(normalized)
    bases: list[TestDiscoveryBasis] = []
    role: TestFileRole | None = None

    # Directory markers apply only when the path segment is an exact conventional
    # directory name (already lowercased in parts).
    dir_hit = any(part in _DIR_MARKERS for part in parts) or ("src" in parts and "test" in parts)
    if dir_hit:
        bases.append(TestDiscoveryBasis.DIRECTORY_CONVENTION)

    file_role, file_bases = _filename_role(name)
    if file_role is not None:
        bases.extend(file_bases)
        role = file_role

    if _has_dir_marker(parts, "fixtures", "testdata", "snapshots", "snapshot"):
        role = TestFileRole.TEST_FIXTURE
        if TestDiscoveryBasis.FIXTURE_CONVENTION not in bases:
            bases.append(TestDiscoveryBasis.FIXTURE_CONVENTION)
    elif _has_dir_marker(parts, "test-support", "test_support"):
        role = TestFileRole.TEST_SUPPORT
    elif _has_dir_marker(parts, "cypress", "playwright", "e2e"):
        role = TestFileRole.END_TO_END_TEST
    elif _has_dir_marker(parts, "integration", "integrationtest") or any(
        part == "integrationtest" or part.endswith("integrationtest") for part in parts
    ):
        role = TestFileRole.INTEGRATION_TEST
    elif role is None and dir_hit:
        # Clear unit-oriented directories without stronger signals.
        if _has_dir_marker(parts, "test", "tests", "__tests__", "spec", "specs") or (
            "src" in parts and "test" in parts
        ):
            role = TestFileRole.UNIT_TEST
        else:
            role = TestFileRole.UNKNOWN_TEST

    if role is None and not bases:
        return None, (), None
    if role is None:
        role = TestFileRole.UNKNOWN_TEST

    return role, tuple(dict.fromkeys(bases)), language_hint


def classify_build_manifest(path: str) -> TestBuildSourceType | None:
    normalized = normalize_relative_path(path)
    name = PurePosixPath(normalized).name
    lower = name.lower()

    if lower == "pom.xml":
        return TestBuildSourceType.MAVEN
    if lower in {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}:
        return TestBuildSourceType.GRADLE
    if lower == "package.json":
        return TestBuildSourceType.NPM
    if lower == "pyproject.toml":
        return TestBuildSourceType.PYTHON_PROJECT
    if fnmatch.fnmatch(lower, "requirements*.txt"):
        return TestBuildSourceType.REQUIREMENTS
    if lower == "tox.ini":
        return TestBuildSourceType.TOX
    if lower in {"pytest.ini", "setup.cfg"}:
        return TestBuildSourceType.STANDALONE_CONFIG
    if lower.endswith(".csproj"):
        return TestBuildSourceType.DOTNET_PROJECT
    if lower == "go.mod":
        return TestBuildSourceType.GO_MODULE
    if lower == "cargo.toml":
        return TestBuildSourceType.CARGO
    if lower == "composer.json":
        return TestBuildSourceType.COMPOSER
    if lower in {"phpunit.xml", "phpunit.xml.dist"}:
        return TestBuildSourceType.STANDALONE_CONFIG
    return None


def classify_ci_path(path: str) -> bool:
    normalized = normalize_relative_path(path)
    lower = normalized.lower()
    name = PurePosixPath(lower).name

    if lower.startswith(".github/workflows/") and (name.endswith(".yml") or name.endswith(".yaml")):
        return True
    if name == ".gitlab-ci.yml":
        return True
    if lower == ".circleci/config.yml" or lower.endswith("/.circleci/config.yml"):
        return True
    if name == "jenkinsfile":
        return True
    if fnmatch.fnmatch(name, "azure-pipelines*.yml") or fnmatch.fnmatch(
        name, "azure-pipelines*.yaml"
    ):
        return True
    if name == "bitbucket-pipelines.yml":
        return True
    return False


def classify_coverage_config(path: str) -> CoverageFactType | None:
    normalized = normalize_relative_path(path)
    name = PurePosixPath(normalized).name
    lower = name.lower()

    if lower in {".coveragerc", "nyc.config.js", "nyc.config.cjs", "nyc.config.mjs"}:
        return CoverageFactType.COVERAGE_CONFIGURATION
    if fnmatch.fnmatch(lower, "nyc.config*"):
        return CoverageFactType.COVERAGE_CONFIGURATION
    if lower in {"coverage.xml", "lcov.info"}:
        return CoverageFactType.COVERAGE_REPORT_REFERENCE
    if "jacoco" in lower:
        if lower.endswith(".xml") or "report" in lower:
            return CoverageFactType.COVERAGE_REPORT_REFERENCE
        return CoverageFactType.COVERAGE_CONFIGURATION
    if "cobertura" in lower:
        return CoverageFactType.COVERAGE_REPORT_REFERENCE
    if fnmatch.fnmatch(lower, "jest.config*"):
        return CoverageFactType.COVERAGE_CONFIGURATION
    return None


def discover_candidates(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[tuple[str, TestFileRole, tuple[TestDiscoveryBasis, ...], str | None], ...]:
    found: list[tuple[str, TestFileRole, tuple[TestDiscoveryBasis, ...], str | None]] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        role, bases, language_hint = classify_test_candidate(path)
        if role is None:
            continue
        found.append((path, role, bases, language_hint))
    found.sort(key=lambda item: item[0])
    return tuple(found[: max(0, max_files)])


def discover_build_paths(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[tuple[str, TestBuildSourceType], ...]:
    found: list[tuple[str, TestBuildSourceType]] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        source = classify_build_manifest(path)
        if source is None:
            continue
        found.append((path, source))
    found.sort(key=lambda item: item[0])
    return tuple(found[: max(0, max_files)])


def discover_ci_paths(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[str, ...]:
    paths: list[str] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        if classify_ci_path(path):
            paths.append(path)
    return tuple(sorted(set(paths))[: max(0, max_files)])


def discover_fixture_paths(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[str, ...]:
    paths: list[str] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        role, _, _ = classify_test_candidate(path)
        parts = _path_parts(path)
        if role is TestFileRole.TEST_FIXTURE or _has_dir_marker(
            parts, "fixtures", "testdata", "snapshots", "snapshot"
        ):
            paths.append(path)
    return tuple(sorted(set(paths))[: max(0, max_files)])


def discover_coverage_paths(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[tuple[str, CoverageFactType], ...]:
    found: list[tuple[str, CoverageFactType]] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        fact_type = classify_coverage_config(path)
        if fact_type is None:
            continue
        found.append((path, fact_type))
    found.sort(key=lambda item: item[0])
    return tuple(found[: max(0, max_files)])
