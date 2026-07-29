"""Candidate path discovery for repository-sensitive evidence."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.language.adapters import classify_source_path
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.repository_sensitive.enums import (
    DiscoveryBasis,
    SensitiveArtifactKind,
)
from codestrata.scan_boundary import default_ignore_path_markers

DEFAULT_IGNORE_MARKERS: tuple[str, ...] = default_ignore_path_markers()

_EXACT_FILENAMES: dict[str, SensitiveArtifactKind] = {
    ".env": SensitiveArtifactKind.ENVIRONMENT_FILE,
    "id_rsa": SensitiveArtifactKind.SSH_PRIVATE_KEY,
    "id_dsa": SensitiveArtifactKind.SSH_PRIVATE_KEY,
    "id_ecdsa": SensitiveArtifactKind.SSH_PRIVATE_KEY,
    "id_ed25519": SensitiveArtifactKind.SSH_PRIVATE_KEY,
    "credentials": SensitiveArtifactKind.CLOUD_CREDENTIALS_FILE,
    ".npmrc": SensitiveArtifactKind.PACKAGE_REGISTRY_CREDENTIALS_FILE,
    ".pypirc": SensitiveArtifactKind.PACKAGE_REGISTRY_CREDENTIALS_FILE,
    ".netrc": SensitiveArtifactKind.PACKAGE_REGISTRY_CREDENTIALS_FILE,
}

_EXTENSION_KINDS: dict[str, SensitiveArtifactKind] = {
    ".pem": SensitiveArtifactKind.UNKNOWN_SENSITIVE_ARTIFACT,
    ".key": SensitiveArtifactKind.PRIVATE_KEY,
    ".crt": SensitiveArtifactKind.PUBLIC_CERTIFICATE,
    ".cer": SensitiveArtifactKind.PUBLIC_CERTIFICATE,
    ".p12": SensitiveArtifactKind.KEYSTORE,
    ".pfx": SensitiveArtifactKind.KEYSTORE,
    ".jks": SensitiveArtifactKind.KEYSTORE,
    ".keystore": SensitiveArtifactKind.KEYSTORE,
    ".truststore": SensitiveArtifactKind.TRUSTSTORE,
}

_BINARY_EXTENSIONS = {".p12", ".pfx", ".jks", ".keystore", ".truststore"}

_ENV_PATTERN = ".env.*"

_CONFIG_EXTENSIONS = {".properties", ".yml", ".yaml", ".json", ".toml"}
_CONFIG_BASENAMES = {
    "settings.xml",
    "application.properties",
    "application.yml",
    "application.yaml",
    "application.toml",
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


def is_binary_extension(path: str) -> bool:
    return PurePosixPath(normalize_relative_path(path)).suffix.lower() in _BINARY_EXTENSIONS


def classify_candidate(
    path: str,
) -> tuple[SensitiveArtifactKind | None, tuple[DiscoveryBasis, ...]]:
    """Return artifact kind and discovery bases, or (None, ()) if not a candidate."""

    normalized = normalize_relative_path(path)
    name = PurePosixPath(normalized).name
    lower_name = name.lower()
    suffix = PurePosixPath(normalized).suffix.lower()
    bases: list[DiscoveryBasis] = []
    kind: SensitiveArtifactKind | None = None

    if lower_name in _EXACT_FILENAMES:
        kind = _EXACT_FILENAMES[lower_name]
        bases.append(DiscoveryBasis.EXACT_FILENAME)
    elif fnmatch.fnmatch(lower_name, _ENV_PATTERN):
        kind = SensitiveArtifactKind.ENVIRONMENT_FILE
        bases.append(DiscoveryBasis.FILENAME_PATTERN)
    elif normalized.lower().endswith("/.aws/credentials") or (
        lower_name == "credentials" and "/.aws/" in f"/{normalized.lower()}"
    ):
        kind = SensitiveArtifactKind.CLOUD_CREDENTIALS_FILE
        bases.extend([DiscoveryBasis.EXACT_FILENAME, DiscoveryBasis.FILENAME_PATTERN])
    elif lower_name == "settings.xml" and (
        "maven" in normalized.lower()
        or "/.m2/" in f"/{normalized.lower()}"
        or normalized.lower() == "settings.xml"
    ):
        kind = SensitiveArtifactKind.CREDENTIAL_CONFIGURATION
        bases.append(DiscoveryBasis.EXACT_FILENAME)
    elif suffix in _EXTENSION_KINDS:
        kind = _EXTENSION_KINDS[suffix]
        bases.append(DiscoveryBasis.EXTENSION)

    if kind is None:
        return None, ()
    return kind, tuple(dict.fromkeys(bases))


def is_configuration_candidate(path: str) -> bool:
    normalized = normalize_relative_path(path)
    name = PurePosixPath(normalized).name.lower()
    suffix = PurePosixPath(normalized).suffix.lower()
    if name in _CONFIG_BASENAMES or name.startswith(".env"):
        return True
    if suffix in _CONFIG_EXTENSIONS:
        return True
    if name in {".npmrc", ".pypirc", ".netrc", "credentials"}:
        return True
    return False


def discover_candidates(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
) -> tuple[tuple[str, SensitiveArtifactKind, tuple[DiscoveryBasis, ...]], ...]:
    found: list[tuple[str, SensitiveArtifactKind, tuple[DiscoveryBasis, ...]]] = []
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path or is_ignored_path(path, ignore_markers=ignore_markers):
            continue
        kind, bases = classify_candidate(path)
        if kind is None:
            continue
        found.append((path, kind, bases))
    found.sort(key=lambda item: item[0])
    return tuple(found[: max(0, max_files)])


def discover_configuration_paths(
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
        if is_configuration_candidate(path) or classify_candidate(path)[0] is not None:
            paths.append(path)
    return tuple(sorted(set(paths))[: max(0, max_files)])
