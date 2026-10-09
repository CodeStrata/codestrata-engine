"""M01 mutually exclusive primary-class classification.

Reuses the existing path-kind classifier and overlays vendor, binary, and
ignore reasons required by the measurement contract. A language detection hit
does not mark the file structurally supported.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from codestrata.application.evidence.inventory.models import CLASSIFIER_VERSION
from codestrata.application.evidence.language.providers.depth import (
    STRUCTURAL_LANGUAGE_LABELS,
    pin_for_language,
)
from codestrata.domain.repository.enums import RepositoryFileKind
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass
from codestrata.services.inventory.classification import RepositoryFileKindClassifier
from codestrata.services.inventory.language import FilenameLanguageDetector

_VENDOR_PARTS = frozenset(
    {"vendor", "node_modules", "third_party", "third-party", "external", "packages"}
)
_BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".jar",
        ".class",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".woff",
        ".woff2",
        ".bin",
        ".dat",
        ".wasm",
    }
)
_KIND_TO_PRIMARY: dict[RepositoryFileKind, InventoryPrimaryClass] = {
    RepositoryFileKind.SOURCE: InventoryPrimaryClass.SOURCE,
    RepositoryFileKind.TEST: InventoryPrimaryClass.TEST,
    RepositoryFileKind.CONFIGURATION: InventoryPrimaryClass.CONFIG,
    RepositoryFileKind.BUILD: InventoryPrimaryClass.CONFIG,
    RepositoryFileKind.DEPENDENCY_MANIFEST: InventoryPrimaryClass.CONFIG,
    RepositoryFileKind.INFRASTRUCTURE: InventoryPrimaryClass.INFRA,
    RepositoryFileKind.DOCUMENTATION: InventoryPrimaryClass.DOCS,
    RepositoryFileKind.GENERATED: InventoryPrimaryClass.GENERATED,
    RepositoryFileKind.UNKNOWN: InventoryPrimaryClass.UNKNOWN,
}

# Dependency installs, build outputs, and framework caches. Inventory still walks
# vendor/ and generated/ so those trees can be classified; it does not hash build
# outputs or node_modules.
INVENTORY_PRUNE_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".vscode",
        ".angular",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".turbo",
        ".cache",
        ".parcel-cache",
        "node_modules",
        "dist",
        "build",
        "out",
        "coverage",
        "target",
    }
)
_DEFAULT_IGNORE_DIR_NAMES = INVENTORY_PRUNE_DIR_NAMES

_MANIFEST_NAMES = frozenset(
    {
        "pom.xml",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.json",
        "composer.lock",
        "requirements.txt",
        "pyproject.toml",
        "poetry.lock",
        "pipfile",
        "pipfile.lock",
        "packages.config",
        "packages.lock.json",
        "go.mod",
        "go.sum",
        "cargo.toml",
        "cargo.lock",
    }
)


def normalize_relative_path(path: str) -> str:
    text = path.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def is_binary_bytes(sample: bytes) -> bool:
    return b"\x00" in sample[:8192]


def is_binary_path(relative_path: str) -> bool:
    suffix = PurePosixPath(normalize_relative_path(relative_path)).suffix.lower()
    return suffix in _BINARY_EXTENSIONS


def path_parts(relative_path: str) -> tuple[str, ...]:
    return PurePosixPath(normalize_relative_path(relative_path).lower()).parts


def ignore_reason_for_path(relative_path: str) -> str | None:
    parts = path_parts(relative_path)
    for name in parts:
        if name in _DEFAULT_IGNORE_DIR_NAMES:
            return f"default-exclude:{name}"
    return None


def is_vendor_path(relative_path: str) -> bool:
    return bool(set(path_parts(relative_path)).intersection(_VENDOR_PARTS))


class InventoryPrimaryClassifier:
    """Classify a repository-relative path into one M01 primary class."""

    def __init__(
        self,
        *,
        kind_classifier: RepositoryFileKindClassifier | None = None,
        language_detector: FilenameLanguageDetector | None = None,
    ) -> None:
        self._kinds = kind_classifier or RepositoryFileKindClassifier()
        self._languages = language_detector or FilenameLanguageDetector()

    @property
    def version(self) -> str:
        return CLASSIFIER_VERSION

    def classify(
        self,
        relative_path: str,
        *,
        binary: bool = False,
        unreadable: bool = False,
    ) -> InventoryPrimaryClass:
        if unreadable:
            return InventoryPrimaryClass.UNKNOWN
        if binary or is_binary_path(relative_path):
            return InventoryPrimaryClass.BINARY
        kind = self._kinds.classify(relative_path)
        if kind is RepositoryFileKind.GENERATED:
            return InventoryPrimaryClass.GENERATED
        if is_vendor_path(relative_path):
            return InventoryPrimaryClass.VENDOR
        return _KIND_TO_PRIMARY.get(kind, InventoryPrimaryClass.UNKNOWN)

    def detect_language(self, relative_path: str) -> str | None:
        return self._languages.detect(relative_path)

    def structural_language(self, relative_path: str) -> str | None:
        label = self.detect_language(relative_path)
        if label is None:
            return None
        mapped = STRUCTURAL_LANGUAGE_LABELS.get(label)
        if mapped is not None:
            return mapped
        pin = pin_for_language(label)
        return pin.language if pin is not None else None

    def manifest_location(self, relative_path: str) -> str | None:
        name = PurePosixPath(normalize_relative_path(relative_path)).name.lower()
        if name in _MANIFEST_NAMES:
            return normalize_relative_path(relative_path)
        if name.endswith((".csproj", ".fsproj", ".vbproj")):
            return normalize_relative_path(relative_path)
        return None
