"""Shared scan-boundary decision service."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from codestrata.scan_boundary.policy import (
    _DOC_PARTS,
    _EXAMPLE_PARTS,
    _FIXTURE_PARTS,
    _GENERATED_MARKERS,
    _TEST_PARTS,
    _VENDOR_PARTS,
    BOUNDARY_POLICY_VERSION,
    DEFAULT_EXCLUDED_DIRECTORY_NAMES,
    ScanSourceRole,
    default_ignore_path_markers,
)


def normalize_repo_relative(path: str) -> str:
    """Normalize a repository-relative path to posix form without leading ``./``."""

    text = (path or "").replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


@dataclass(frozen=True, slots=True)
class BoundaryPolicy:
    """Effective boundary policy for one assessment root."""

    excluded_directory_names: frozenset[str] = DEFAULT_EXCLUDED_DIRECTORY_NAMES
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()
    production_roots: tuple[str, ...] = ()
    test_roots: tuple[str, ...] = ()
    example_roots: tuple[str, ...] = ()
    generated_roots: tuple[str, ...] = ()
    vendor_roots: tuple[str, ...] = ()
    fixture_roots: tuple[str, ...] = ()
    documentation_roots: tuple[str, ...] = ()
    source_role_overrides: tuple[tuple[str, ScanSourceRole], ...] = ()
    ignore_path_markers: tuple[str, ...] = field(default_factory=default_ignore_path_markers)
    policy_version: str = BOUNDARY_POLICY_VERSION

    @classmethod
    def from_settings(cls, settings: object | None = None) -> BoundaryPolicy:
        """Build policy from optional ``CodestrataSettings.scan`` section."""

        scan = getattr(settings, "scan", None) if settings is not None else None
        if scan is None:
            return cls()

        extra_exclude_dirs = tuple(
            _clean_token(item) for item in getattr(scan, "excluded_directories", ()) or ()
        )
        excluded = frozenset(DEFAULT_EXCLUDED_DIRECTORY_NAMES | set(extra_exclude_dirs))
        # Allow removing defaults via include of directory names listed in
        # ``include_default_directories`` (rare); primarily use include_paths.
        restore = {
            _clean_token(item) for item in getattr(scan, "include_default_directories", ()) or ()
        }
        if restore:
            excluded = frozenset(name for name in excluded if name not in restore)

        overrides_raw = getattr(scan, "source_role_overrides", None) or {}
        overrides: list[tuple[str, ScanSourceRole]] = []
        if isinstance(overrides_raw, dict):
            for key, value in overrides_raw.items():
                role = _parse_role(str(value))
                if role is None:
                    continue
                overrides.append((_clean_prefix(str(key)), role))

        return cls(
            excluded_directory_names=excluded,
            include_paths=tuple(
                _clean_prefix(item) for item in getattr(scan, "include_paths", ()) or ()
            ),
            exclude_paths=tuple(
                _clean_prefix(item) for item in getattr(scan, "exclude_paths", ()) or ()
            ),
            production_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "production_roots", ()) or ()
            ),
            test_roots=tuple(_clean_prefix(item) for item in getattr(scan, "test_roots", ()) or ()),
            example_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "example_roots", ()) or ()
            ),
            generated_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "generated_roots", ()) or ()
            ),
            vendor_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "vendor_roots", ()) or ()
            ),
            fixture_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "fixture_roots", ()) or ()
            ),
            documentation_roots=tuple(
                _clean_prefix(item) for item in getattr(scan, "documentation_roots", ()) or ()
            ),
            source_role_overrides=tuple(overrides),
            ignore_path_markers=default_ignore_path_markers(
                extra=tuple(getattr(scan, "ignore_path_markers", ()) or ())
            ),
        )


@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    included: bool
    role: ScanSourceRole
    reason: str


@dataclass
class BoundaryDiagnostics:
    policy_version: str = BOUNDARY_POLICY_VERSION
    included_files: int = 0
    excluded_files: int = 0
    role_counts: dict[str, int] = field(default_factory=dict)
    excluded_by_default_sample: list[str] = field(default_factory=list)
    excluded_by_config_sample: list[str] = field(default_factory=list)
    included_by_override_sample: list[str] = field(default_factory=list)
    default_excluded_directories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "included_files": self.included_files,
            "excluded_files": self.excluded_files,
            "role_counts": dict(sorted(self.role_counts.items())),
            "default_excluded_directories": list(self.default_excluded_directories),
            "excluded_by_default_sample": list(self.excluded_by_default_sample[:12]),
            "excluded_by_config_sample": list(self.excluded_by_config_sample[:12]),
            "included_by_override_sample": list(self.included_by_override_sample[:12]),
        }


class BoundaryService:
    """Single shared boundary decision service for repository traversal."""

    def __init__(self, policy: BoundaryPolicy | None = None) -> None:
        self.policy = policy or BoundaryPolicy()
        self.diagnostics = BoundaryDiagnostics(
            policy_version=self.policy.policy_version,
            default_excluded_directories=sorted(self.policy.excluded_directory_names),
        )

    def decide(self, relative_path: str) -> BoundaryDecision:
        """Apply precedence: include → exclude → role override → default → heuristic."""

        path = normalize_repo_relative(relative_path)
        if not path:
            return BoundaryDecision(False, ScanSourceRole.EXCLUDED, "empty-path")

        if self._matches_any_prefix(path, self.policy.include_paths):
            role = self.classify_role(path)
            return BoundaryDecision(True, role, "explicit-include")

        if self._matches_any_prefix(path, self.policy.exclude_paths):
            return BoundaryDecision(False, ScanSourceRole.EXCLUDED, "explicit-exclude")

        parts = PurePosixPath(path).parts
        if any(part in self.policy.excluded_directory_names for part in parts):
            return BoundaryDecision(False, ScanSourceRole.EXCLUDED, "default-exclude")

        lowered = f"/{path.lower()}/"
        for marker in self.policy.ignore_path_markers:
            if marker.lower() in lowered:
                return BoundaryDecision(False, ScanSourceRole.EXCLUDED, "ignore-marker")

        role = self.classify_role(path)
        return BoundaryDecision(True, role, "heuristic")

    def classify_role(self, relative_path: str) -> ScanSourceRole:
        path = normalize_repo_relative(relative_path)
        for prefix, role in self.policy.source_role_overrides:
            if self._path_under_prefix(path, prefix):
                return role
        for prefix in self.policy.production_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.PRODUCTION
        for prefix in self.policy.test_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.TEST
        for prefix in self.policy.fixture_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.FIXTURE
        for prefix in self.policy.example_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.EXAMPLE
        for prefix in self.policy.generated_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.GENERATED
        for prefix in self.policy.vendor_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.VENDOR
        for prefix in self.policy.documentation_roots:
            if self._path_under_prefix(path, prefix):
                return ScanSourceRole.DOCUMENTATION
        return classify_path_role(path)

    def should_prune_directory(self, name: str, *, relative_dir: str = "") -> bool:
        """Return True when ``name`` should not be descended into during walks."""

        if name not in self.policy.excluded_directory_names:
            return False
        candidate = (
            f"{normalize_repo_relative(relative_dir)}/{name}".strip("/") if relative_dir else name
        )
        # Explicit includes under an otherwise-excluded directory keep it walkable.
        if self._matches_any_prefix(candidate, self.policy.include_paths):
            return False
        if any(
            include == candidate or include.startswith(f"{candidate}/")
            for include in self.policy.include_paths
        ):
            return False
        return True

    def collect_files(
        self,
        repository_root: Path,
        *,
        max_files: int | None = None,
    ) -> list[str]:
        """Walk ``repository_root`` applying the shared boundary policy."""

        root = repository_root.expanduser().resolve()
        collected: list[str] = []
        excluded_samples_default: list[str] = []
        excluded_samples_config: list[str] = []
        included_override_samples: list[str] = []
        role_counter: Counter[str] = Counter()

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(dirpath)
            try:
                relative_dir = current.relative_to(root).as_posix()
            except ValueError:
                relative_dir = ""
            if relative_dir == ".":
                relative_dir = ""

            kept_names: list[str] = []
            for name in sorted(dirnames):
                child = current / name
                if child.is_symlink():
                    continue
                if self.should_prune_directory(name, relative_dir=relative_dir):
                    self.diagnostics.excluded_files += 1
                    sample = f"{relative_dir}/{name}/".strip("/") if relative_dir else f"{name}/"
                    if len(excluded_samples_default) < 12:
                        excluded_samples_default.append(sample)
                    continue
                kept_names.append(name)
            dirnames[:] = kept_names

            for name in filenames:
                path = current / name
                # Never follow or inventory file symlinks — only regular files.
                if path.is_symlink() or not path.is_file():
                    continue

                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    continue

                decision = self.decide(relative)
                if not decision.included:
                    self.diagnostics.excluded_files += 1
                    if decision.reason == "explicit-exclude":
                        if len(excluded_samples_config) < 12:
                            excluded_samples_config.append(relative)
                    elif len(excluded_samples_default) < 12:
                        excluded_samples_default.append(relative)
                    continue

                role_counter[decision.role.value] += 1
                if decision.reason == "explicit-include" and len(included_override_samples) < 12:
                    included_override_samples.append(relative)
                collected.append(relative)
                if max_files is not None and len(collected) >= max_files:
                    break
            if max_files is not None and len(collected) >= max_files:
                break

        self.diagnostics.included_files = len(collected)
        self.diagnostics.role_counts = dict(role_counter)
        self.diagnostics.excluded_by_default_sample = excluded_samples_default
        self.diagnostics.excluded_by_config_sample = excluded_samples_config
        self.diagnostics.included_by_override_sample = included_override_samples
        return sorted(collected)

    @staticmethod
    def _matches_any_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
        return any(BoundaryService._path_under_prefix(path, prefix) for prefix in prefixes)

    @staticmethod
    def _path_under_prefix(path: str, prefix: str) -> bool:
        clean = normalize_repo_relative(prefix)
        if not clean:
            return False
        return path == clean or path.startswith(f"{clean}/")


def classify_path_role(path: str) -> ScanSourceRole:
    """Heuristic source-role classification for an in-scope path."""

    normalized = normalize_repo_relative(path)
    lower = normalized.lower()
    lowered_path = f"/{lower}/"
    if any(marker in lowered_path for marker in _GENERATED_MARKERS):
        return ScanSourceRole.GENERATED
    parts = {part.lower() for part in PurePosixPath(lower).parts}
    if (
        parts.intersection(_FIXTURE_PARTS)
        or "test-fixtures" in lower
        or "/fixtures/" in lowered_path
    ):
        return ScanSourceRole.FIXTURE
    # Prefer conventional test/source trees over example-token false positives
    # (e.g. org.springframework.samples.petclinic package paths).
    if _under_conventional_test_tree(lowered_path) or parts.intersection(_TEST_PARTS):
        if not _under_conventional_main_tree(lowered_path):
            return ScanSourceRole.TEST
    if _is_example_layout(lowered_path, parts):
        return ScanSourceRole.EXAMPLE
    if parts.intersection(_DOC_PARTS):
        return ScanSourceRole.DOCUMENTATION
    if parts.intersection(_VENDOR_PARTS):
        return ScanSourceRole.VENDOR
    return ScanSourceRole.PRODUCTION


def _under_conventional_main_tree(lowered_path: str) -> bool:
    return any(
        marker in lowered_path
        for marker in (
            "/src/main/",
            "/app/main/",
        )
    )


def _under_conventional_test_tree(lowered_path: str) -> bool:
    return any(
        marker in lowered_path
        for marker in (
            "/src/test/",
            "/src/tests/",
            "/app/test/",
        )
    )


def _is_example_layout(lowered_path: str, parts: set[str]) -> bool:
    """Detect example/sample/demo layout directories without Java package false positives."""

    if not parts.intersection(_EXAMPLE_PARTS):
        return False
    # Application source trees often use package names like ``samples``.
    if any(
        marker in lowered_path
        for marker in (
            "/src/main/java/",
            "/src/test/java/",
            "/src/main/kotlin/",
            "/src/test/kotlin/",
            "/src/main/scala/",
            "/src/test/scala/",
            "/src/main/groovy/",
            "/src/test/groovy/",
        )
    ):
        return False
    return True


def _clean_token(value: str) -> str:
    return value.strip().strip("/").replace("\\", "/")


def _clean_prefix(value: str) -> str:
    return normalize_repo_relative(value)


def _parse_role(value: str) -> ScanSourceRole | None:
    compact = value.strip().lower().replace("-", "_")
    aliases = {
        "source": ScanSourceRole.PRODUCTION,
        "production": ScanSourceRole.PRODUCTION,
        "test": ScanSourceRole.TEST,
        "fixture": ScanSourceRole.FIXTURE,
        "example": ScanSourceRole.EXAMPLE,
        "generated": ScanSourceRole.GENERATED,
        "vendor": ScanSourceRole.VENDOR,
        "documentation": ScanSourceRole.DOCUMENTATION,
        "docs": ScanSourceRole.DOCUMENTATION,
        "unknown": ScanSourceRole.UNKNOWN,
        "excluded": ScanSourceRole.EXCLUDED,
    }
    return aliases.get(compact)


__all__ = [
    "BoundaryDecision",
    "BoundaryDiagnostics",
    "BoundaryPolicy",
    "BoundaryService",
    "classify_path_role",
    "normalize_repo_relative",
]
