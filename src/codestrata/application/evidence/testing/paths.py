"""Path helpers for testing evidence. No repository execution."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.quality.maps import language_for_path
from codestrata.application.evidence.quality.models import FileRole
from codestrata.application.evidence.quality.roles import file_role, is_ignored
from codestrata.application.evidence.testing.capability import SUPPORTED_TEST_LANGUAGES

GENERATED_PARTS = frozenset({"generated", "gen", "__generated__"})
UNSUPPORTED_LANGUAGE_SUFFIXES: dict[str, str] = {
    ".go": "go",
    ".php": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".rb": "ruby",
    ".feature": "cucumber",
}


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def posix_parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(normalize_relative_path(path)).parts


def is_generated_path(path: str) -> bool:
    parts = {part.lower() for part in posix_parts(path)}
    if parts & GENERATED_PARTS:
        return True
    return file_role(path) is FileRole.GENERATED


def unsupported_language_for_path(path: str) -> str | None:
    name = PurePosixPath(normalize_relative_path(path)).name.lower()
    for suffix, language in UNSUPPORTED_LANGUAGE_SUFFIXES.items():
        if name.endswith(suffix):
            return language
    return None


def is_supported_language(path: str) -> bool:
    language = language_for_path(path)
    return language in SUPPORTED_TEST_LANGUAGES


def eligible_production(path: str, *, ignore_markers: Sequence[str] | None = None) -> bool:
    if is_ignored(path, ignore_markers=ignore_markers):
        return False
    if is_generated_path(path) or has_test_filename(path):
        return False
    role = file_role(path)
    if role is not FileRole.SOURCE:
        return False
    return is_supported_language(path)


def has_test_filename(path: str) -> bool:
    name = PurePosixPath(normalize_relative_path(path)).name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
        or name.endswith("test.java")
        or name.endswith("tests.java")
        or name.endswith("_test.go")
        or name.endswith(".feature")
    )


def is_test_path(path: str, *, ignore_markers: Sequence[str] | None = None) -> bool:
    if is_ignored(path, ignore_markers=ignore_markers):
        return False
    return file_role(path) is FileRole.TEST


def is_test_like(path: str, *, ignore_markers: Sequence[str] | None = None) -> bool:
    """Test files, generated tests, and unsupported test-named sources."""

    testish = has_test_filename(path)
    if is_generated_path(path) and testish:
        return True
    if is_ignored(path, ignore_markers=ignore_markers):
        return False
    if is_test_path(path, ignore_markers=ignore_markers):
        return True
    if testish:
        return True
    if unsupported_language_for_path(path) and testish:
        return True
    return False


def stem_without_suffix(path: str) -> str:
    name = PurePosixPath(normalize_relative_path(path)).name
    lowered = name.lower()
    for suffix in (
        ".test.tsx",
        ".test.ts",
        ".test.jsx",
        ".test.js",
        ".spec.tsx",
        ".spec.ts",
        ".spec.jsx",
        ".spec.js",
        ".tsx",
        ".ts",
        ".jsx",
        ".js",
        ".java",
        ".py",
    ):
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return PurePosixPath(name).stem


def production_stem(path: str) -> str:
    return stem_without_suffix(path)


def convention_stems(path: str, language: str) -> tuple[str, ...]:
    """Possible production stems implied by a test filename."""

    stem = stem_without_suffix(path)
    lowered = stem.lower()
    found: list[str] = []
    if language == "python":
        if lowered.startswith("test_"):
            found.append(stem[5:])
        if lowered.endswith("_test"):
            found.append(stem[:-5])
        if lowered.endswith("_spec"):
            found.append(stem[:-5])
    elif language == "java":
        for suffix in ("Test", "Tests", "IT", "ITCase", "TestCase"):
            if stem.endswith(suffix) and len(stem) > len(suffix):
                found.append(stem[: -len(suffix)])
    elif language in {"javascript", "typescript"}:
        found.append(stem)
    unique = tuple(dict.fromkeys(item for item in found if item))
    return unique


def module_from_python_path(path: str) -> str:
    posix = PurePosixPath(normalize_relative_path(path))
    parts = list(posix.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def java_type_from_path(path: str) -> str:
    posix = PurePosixPath(normalize_relative_path(path))
    return ".".join(posix.with_suffix("").parts)


def resolve_relative_specifier(test_path: str, specifier: str) -> str:
    base = PurePosixPath(normalize_relative_path(test_path)).parent
    combined = (base / specifier).as_posix()
    parts: list[str] = []
    for part in PurePosixPath(combined).parts:
        if part == "..":
            if parts:
                parts.pop()
            continue
        if part in {".", ""}:
            continue
        parts.append(part)
    return "/".join(parts)


__all__ = [
    "convention_stems",
    "eligible_production",
    "has_test_filename",
    "is_generated_path",
    "is_supported_language",
    "is_test_like",
    "is_test_path",
    "java_type_from_path",
    "module_from_python_path",
    "normalize_relative_path",
    "production_stem",
    "resolve_relative_specifier",
    "stem_without_suffix",
    "unsupported_language_for_path",
]
