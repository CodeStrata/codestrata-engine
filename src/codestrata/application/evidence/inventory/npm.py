"""Inventory-local npm declared vs resolved collection.

Kept outside DependencyEcosystem (no npm member there yet). Missing lock is
UNKNOWN resolution, not zero dependencies. Package scripts are never executed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.inventory.models import (
    ManifestObservation,
    ResolutionObservation,
    SupportKind,
)
from codestrata.domain.evidence.language.identifiers import stable_evidence_id

NPM_PARSER_VERSION = "inventory.npm.v1"
_LOCK_NAMES = frozenset({"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"})


class NpmDeclarationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    declaration_id: str
    name: str
    declared_range: str | None = None
    scope: str
    manifest_path: str
    line: int | None = None


class NpmResolutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: str
    declaration_id: str | None
    resolved_identity: str
    resolved_version: str | None = None
    lock_path: str
    direct: bool = True


class NpmManifestFacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation: ManifestObservation
    declarations: tuple[NpmDeclarationRecord, ...] = ()
    resolutions: tuple[NpmResolutionRecord, ...] = ()


def collect_npm_facts(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[NpmManifestFacts, ...]:
    """Parse package.json declarations and lockfile resolution occurrences."""

    paths = tuple(sorted(path.replace("\\", "/") for path in relative_paths))
    lock_by_dir = _lock_paths(paths)
    facts: list[NpmManifestFacts] = []
    seen_locks: set[str] = set()
    for path in paths:
        name = PurePosixPath(path).name.lower()
        if name == "package.json":
            facts.append(_package_json_facts(path, file_texts, lock_by_dir))
            continue
        if name in {"package-lock.json", "npm-shrinkwrap.json"}:
            seen_locks.add(path)
            facts.append(_lock_observation(path, file_texts))
    for path in paths:
        name = PurePosixPath(path).name.lower()
        if name in {"yarn.lock", "pnpm-lock.yaml"} and path not in seen_locks:
            facts.append(
                NpmManifestFacts(
                    observation=ManifestObservation(
                        relative_path=path,
                        ecosystem="npm",
                        manifest_kind="lockfile",
                        support=SupportKind.DETECTION_ONLY,
                        resolution=ResolutionObservation.UNKNOWN,
                        parser_version=NPM_PARSER_VERSION,
                        diagnostics=("lock_format_unparsed",),
                    )
                )
            )
    return tuple(sorted(facts, key=lambda item: item.observation.relative_path))


def _lock_paths(paths: Sequence[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in paths:
        name = PurePosixPath(path).name.lower()
        if name not in _LOCK_NAMES:
            continue
        directory = str(PurePosixPath(path).parent)
        if directory == ".":
            directory = ""
        mapping.setdefault(directory, path)
    return mapping


def _package_json_facts(
    path: str,
    file_texts: Mapping[str, str],
    lock_by_dir: Mapping[str, str],
) -> NpmManifestFacts:
    text = file_texts.get(path, file_texts.get(path.replace("/", "\\"), ""))
    diagnostics: list[str] = []
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError as error:
        return NpmManifestFacts(
            observation=ManifestObservation(
                relative_path=path,
                ecosystem="npm",
                manifest_kind="manifest",
                support=SupportKind.STRUCTURAL,
                resolution=ResolutionObservation.UNKNOWN,
                parser_version=NPM_PARSER_VERSION,
                diagnostics=(f"package_json_parse_error:{error}",),
            )
        )
    if not isinstance(data, dict):
        return NpmManifestFacts(
            observation=ManifestObservation(
                relative_path=path,
                ecosystem="npm",
                manifest_kind="manifest",
                support=SupportKind.STRUCTURAL,
                resolution=ResolutionObservation.UNKNOWN,
                parser_version=NPM_PARSER_VERSION,
                diagnostics=("package_json_not_object",),
            )
        )
    if "workspaces" in data:
        diagnostics.append("workspace_packages_detection_only")
    declarations = _declarations_from_package(path, text, data)
    directory = str(PurePosixPath(path).parent)
    if directory == ".":
        directory = ""
    lock_path = lock_by_dir.get(directory)
    resolutions: tuple[NpmResolutionRecord, ...] = ()
    resolution = ResolutionObservation.UNKNOWN
    if lock_path:
        lock_text = file_texts.get(lock_path, file_texts.get(lock_path.replace("/", "\\"), ""))
        resolutions = _resolutions_from_lock(lock_path, lock_text, declarations)
        if PurePosixPath(lock_path).name.lower() in {"yarn.lock", "pnpm-lock.yaml"}:
            resolution = ResolutionObservation.UNKNOWN
            diagnostics.append("lock_format_unparsed")
        else:
            resolution = ResolutionObservation.RESOLVED
    identities = [item.name for item in declarations]
    duplicates = tuple(sorted({name for name in identities if identities.count(name) > 1}))
    resolved_ids = {item.declaration_id for item in resolutions if item.declaration_id}
    return NpmManifestFacts(
        observation=ManifestObservation(
            relative_path=path,
            ecosystem="npm",
            manifest_kind="manifest",
            support=SupportKind.STRUCTURAL,
            resolution=resolution,
            declared_count=len(declarations),
            resolved_count=len(resolved_ids),
            parser_version=NPM_PARSER_VERSION,
            duplicate_coordinates=duplicates,
            diagnostics=tuple(diagnostics),
        ),
        declarations=declarations,
        resolutions=resolutions,
    )


def _declarations_from_package(
    path: str,
    text: str,
    data: dict[object, object],
) -> tuple[NpmDeclarationRecord, ...]:
    sections = (
        ("dependencies", "runtime"),
        ("devDependencies", "development"),
        ("optionalDependencies", "optional"),
        ("peerDependencies", "peer"),
    )
    records: list[NpmDeclarationRecord] = []
    for field, scope in sections:
        block = data.get(field)
        if not isinstance(block, dict):
            continue
        for raw_name, raw_range in sorted(block.items(), key=lambda item: str(item[0])):
            name = str(raw_name).strip()
            if not name:
                continue
            declared = str(raw_range).strip() if raw_range is not None else None
            line = _line_of(text, f'"{name}"')
            declaration_id = stable_evidence_id(
                "dependency.declaration",
                NPM_PARSER_VERSION,
                path,
                name,
                scope,
                declared or "",
                str(line or 0),
            )
            records.append(
                NpmDeclarationRecord(
                    declaration_id=declaration_id,
                    name=name,
                    declared_range=declared or None,
                    scope=scope,
                    manifest_path=path,
                    line=line,
                )
            )
    return tuple(records)


def _lock_observation(path: str, file_texts: Mapping[str, str]) -> NpmManifestFacts:
    text = file_texts.get(path, file_texts.get(path.replace("/", "\\"), ""))
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError as error:
        return NpmManifestFacts(
            observation=ManifestObservation(
                relative_path=path,
                ecosystem="npm",
                manifest_kind="lockfile",
                support=SupportKind.STRUCTURAL,
                resolution=ResolutionObservation.UNKNOWN,
                parser_version=NPM_PARSER_VERSION,
                diagnostics=(f"lock_parse_error:{error}",),
            )
        )
    count = 0
    if isinstance(data, dict):
        packages = data.get("packages")
        if isinstance(packages, dict):
            count = sum(1 for key in packages if str(key).startswith("node_modules/"))
        dependencies = data.get("dependencies")
        if count == 0 and isinstance(dependencies, dict):
            count = len(dependencies)
    return NpmManifestFacts(
        observation=ManifestObservation(
            relative_path=path,
            ecosystem="npm",
            manifest_kind="lockfile",
            support=SupportKind.STRUCTURAL,
            resolution=(ResolutionObservation.RESOLVED if count else ResolutionObservation.UNKNOWN),
            resolved_count=count,
            parser_version=NPM_PARSER_VERSION,
        )
    )


def _resolutions_from_lock(
    lock_path: str,
    text: str,
    declarations: Sequence[NpmDeclarationRecord],
) -> tuple[NpmResolutionRecord, ...]:
    name = PurePosixPath(lock_path).name.lower()
    if name not in {"package-lock.json", "npm-shrinkwrap.json"}:
        return ()
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, dict):
        return ()
    declared = {item.name: item for item in declarations}
    records: list[NpmResolutionRecord] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for raw_key, raw_value in sorted(packages.items(), key=lambda item: str(item[0])):
            key = str(raw_key)
            if not key.startswith("node_modules/"):
                continue
            identity = key.rsplit("node_modules/", 1)[-1]
            payload = raw_value if isinstance(raw_value, dict) else {}
            version = str(payload.get("version") or "").strip() or None
            declaration = declared.get(identity)
            occurrence_id = stable_evidence_id(
                "dependency.resolution",
                NPM_PARSER_VERSION,
                lock_path,
                identity,
                version or "",
            )
            records.append(
                NpmResolutionRecord(
                    occurrence_id=occurrence_id,
                    declaration_id=declaration.declaration_id if declaration else None,
                    resolved_identity=identity,
                    resolved_version=version,
                    lock_path=lock_path,
                    direct=declaration is not None,
                )
            )
        return tuple(records)
    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        for raw_name, raw_value in sorted(dependencies.items(), key=lambda item: str(item[0])):
            identity = str(raw_name)
            payload = raw_value if isinstance(raw_value, dict) else {}
            version = str(payload.get("version") or "").strip() or None
            declaration = declared.get(identity)
            occurrence_id = stable_evidence_id(
                "dependency.resolution",
                NPM_PARSER_VERSION,
                lock_path,
                identity,
                version or "",
            )
            records.append(
                NpmResolutionRecord(
                    occurrence_id=occurrence_id,
                    declaration_id=declaration.declaration_id if declaration else None,
                    resolved_identity=identity,
                    resolved_version=version,
                    lock_path=lock_path,
                    direct=declaration is not None,
                )
            )
    return tuple(records)


def _line_of(text: str, needle: str) -> int | None:
    if not needle:
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None
