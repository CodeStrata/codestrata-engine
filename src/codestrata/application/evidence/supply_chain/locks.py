"""Parse lockfiles into resolved package occurrences. Never install packages."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.supply_chain.models import ResolutionOccurrence
from codestrata.application.evidence.supply_chain.versions import is_exact_lock_version
from codestrata.domain.evidence.language.identifiers import stable_evidence_id

LOCK_BASENAMES: dict[str, str] = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "yarn.lock": "npm_unparsed",
    "pnpm-lock.yaml": "npm_unparsed",
    "poetry.lock": "python",
    "pipfile.lock": "python",
    "uv.lock": "python",
    "composer.lock": "composer",
    "packages.lock.json": "nuget",
    "gradle.lockfile": "gradle",
}

UNPARSED_LOCKS = frozenset({"npm_unparsed"})


def parent_dir(path: str) -> str:
    directory = str(PurePosixPath(path).parent)
    return "" if directory == "." else directory


def parse_lockfiles(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[tuple[ResolutionOccurrence, ...], tuple[str, ...]]:
    diagnostics: list[str] = []
    occurrences: list[ResolutionOccurrence] = []
    for path in sorted(path.replace("\\", "/") for path in relative_paths):
        name = PurePosixPath(path).name.lower()
        kind = LOCK_BASENAMES.get(name)
        if kind is None:
            continue
        text = file_texts.get(path, file_texts.get(path.replace("/", "\\"), ""))
        if kind in UNPARSED_LOCKS:
            diagnostics.append(f"lock_format_unparsed:{path}")
            continue
        parsed, extra = _parse_one(path, name, text)
        occurrences.extend(parsed)
        diagnostics.extend(extra)
    ordered = tuple(
        sorted(
            occurrences,
            key=lambda item: (
                item.lock_path,
                item.package_name,
                item.resolved_version or "",
                item.occurrence_id,
            ),
        )
    )
    return ordered, tuple(sorted(set(diagnostics)))


def _parse_one(path: str, name: str, text: str) -> tuple[list[ResolutionOccurrence], list[str]]:
    if name in {"package-lock.json", "npm-shrinkwrap.json"}:
        return _npm_lock(path, text), []
    if name == "poetry.lock":
        return _poetry_lock(path, text)
    if name == "pipfile.lock":
        return _pipfile_lock(path, text), []
    if name == "uv.lock":
        return _uv_lock(path, text)
    if name == "composer.lock":
        return _composer_lock(path, text), []
    if name == "packages.lock.json":
        return _nuget_lock(path, text), []
    if name == "gradle.lockfile":
        return _gradle_lock(path, text), []
    return [], [f"lock_format_unparsed:{path}"]


def _occurrence(
    *,
    lock_path: str,
    ecosystem: str,
    package_name: str,
    version: str | None,
    direct: bool,
    dependency_path: tuple[str, ...],
    environment: str = "",
    scheme: str,
) -> ResolutionOccurrence:
    exact = is_exact_lock_version(version)
    unsupported = bool(version) and not exact
    if version and not exact:
        scheme = "unsupported"
    elif not version:
        unsupported = True
        scheme = "unsupported"
    return ResolutionOccurrence(
        occurrence_id=stable_evidence_id(
            "supply_chain.occurrence",
            lock_path,
            ecosystem,
            package_name,
            version or "",
            environment,
            "direct" if direct else "transitive",
        ),
        ecosystem=ecosystem,
        package_name=package_name,
        resolved_version=version if exact else version,
        version_scheme=scheme,
        lock_path=lock_path,
        direct=direct,
        dependency_path=dependency_path or (package_name,),
        environment=environment,
        exact=exact,
        unsupported_scheme=unsupported,
    )


def _npm_lock(path: str, text: str) -> list[ResolutionOccurrence]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[ResolutionOccurrence] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for raw_key, raw_value in packages.items():
            key = str(raw_key)
            if not key.startswith("node_modules/"):
                continue
            payload = raw_value if isinstance(raw_value, dict) else {}
            identity = key.rsplit("node_modules/", 1)[-1]
            version = str(payload.get("version") or "").strip() or None
            nested = key.count("node_modules/") > 1
            chain = tuple(part for part in key.split("node_modules/") if part and part != ".")
            records.append(
                _occurrence(
                    lock_path=path,
                    ecosystem="npm",
                    package_name=identity,
                    version=version,
                    direct=not nested,
                    dependency_path=chain or (identity,),
                    scheme="SEMVER",
                )
            )
        return records
    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        _walk_npm_tree(path, dependencies, (), records)
    return records


def _walk_npm_tree(
    lock_path: str,
    tree: dict[object, object],
    parents: tuple[str, ...],
    records: list[ResolutionOccurrence],
) -> None:
    for raw_name, raw_value in tree.items():
        name = str(raw_name)
        payload = raw_value if isinstance(raw_value, dict) else {}
        version = str(payload.get("version") or "").strip() or None
        chain = (*parents, name)
        records.append(
            _occurrence(
                lock_path=lock_path,
                ecosystem="npm",
                package_name=name,
                version=version,
                direct=not parents,
                dependency_path=chain,
                scheme="SEMVER",
            )
        )
        nested = payload.get("dependencies")
        if isinstance(nested, dict):
            _walk_npm_tree(lock_path, nested, chain, records)


def _poetry_lock(path: str, text: str) -> tuple[list[ResolutionOccurrence], list[str]]:
    try:
        data = tomllib.loads(text) if text else {}
    except tomllib.TOMLDecodeError as error:
        return [], [f"lock_parse_error:{path}:{error}"]
    records: list[ResolutionOccurrence] = []
    packages = data.get("package")
    if not isinstance(packages, list):
        return records, []
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower().replace("_", "-")
        version = str(item.get("version") or "").strip() or None
        category = str(item.get("category") or item.get("group") or "").strip()
        if not name:
            continue
        records.append(
            _occurrence(
                lock_path=path,
                ecosystem="python",
                package_name=name,
                version=version,
                direct=str(item.get("source", {}).get("type") or "") != "directory"
                if isinstance(item.get("source"), dict)
                else True,
                dependency_path=(name,),
                environment=category,
                scheme="ECOSYSTEM",
            )
        )
    return records, []


def _pipfile_lock(path: str, text: str) -> list[ResolutionOccurrence]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[ResolutionOccurrence] = []
    for section, environment in (("default", "runtime"), ("develop", "development")):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for raw_name, raw_value in block.items():
            payload = raw_value if isinstance(raw_value, dict) else {}
            version = str(payload.get("version") or "").lstrip("=").strip() or None
            records.append(
                _occurrence(
                    lock_path=path,
                    ecosystem="python",
                    package_name=str(raw_name).strip().lower().replace("_", "-"),
                    version=version,
                    direct=True,
                    dependency_path=(str(raw_name),),
                    environment=environment,
                    scheme="ECOSYSTEM",
                )
            )
    return records


def _uv_lock(path: str, text: str) -> tuple[list[ResolutionOccurrence], list[str]]:
    try:
        data = tomllib.loads(text) if text else {}
    except tomllib.TOMLDecodeError as error:
        return [], [f"lock_parse_error:{path}:{error}"]
    records: list[ResolutionOccurrence] = []
    packages = data.get("package")
    if not isinstance(packages, list):
        return records, []
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower().replace("_", "-")
        version = str(item.get("version") or "").strip() or None
        if not name:
            continue
        records.append(
            _occurrence(
                lock_path=path,
                ecosystem="python",
                package_name=name,
                version=version,
                direct=True,
                dependency_path=(name,),
                scheme="ECOSYSTEM",
            )
        )
    return records, []


def _composer_lock(path: str, text: str) -> list[ResolutionOccurrence]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[ResolutionOccurrence] = []
    for section, environment in (("packages", "runtime"), ("packages-dev", "development")):
        block = data.get(section)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip().lower()
            version = str(item.get("version") or "").lstrip("v").strip() or None
            if not name:
                continue
            records.append(
                _occurrence(
                    lock_path=path,
                    ecosystem="composer",
                    package_name=name,
                    version=version,
                    direct=True,
                    dependency_path=(name,),
                    environment=environment,
                    scheme="ECOSYSTEM",
                )
            )
    return records


def _nuget_lock(path: str, text: str) -> list[ResolutionOccurrence]:
    try:
        data = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records: list[ResolutionOccurrence] = []
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, dict):
        return records
    for framework, block in dependencies.items():
        if not isinstance(block, dict):
            continue
        for raw_name, raw_value in block.items():
            payload = raw_value if isinstance(raw_value, dict) else {}
            version = str(payload.get("resolved") or payload.get("version") or "").strip() or None
            kind = str(payload.get("type") or "Direct")
            records.append(
                _occurrence(
                    lock_path=path,
                    ecosystem="nuget",
                    package_name=str(raw_name).strip().lower(),
                    version=version,
                    direct=kind.lower() != "transitive",
                    dependency_path=(str(raw_name),),
                    environment=str(framework),
                    scheme="ECOSYSTEM",
                )
            )
    return records


def _gradle_lock(path: str, text: str) -> list[ResolutionOccurrence]:
    records: list[ResolutionOccurrence] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("empty="):
            continue
        if "=" not in stripped:
            continue
        coordinate, configurations = stripped.split("=", 1)
        parts = coordinate.split(":")
        if len(parts) < 3:
            continue
        identity = f"{parts[0]}:{parts[1]}"
        version = parts[2]
        environment = configurations.split(",")[0] if configurations else ""
        records.append(
            _occurrence(
                lock_path=path,
                ecosystem="gradle",
                package_name=identity,
                version=version,
                direct=True,
                dependency_path=(identity,),
                environment=environment,
                scheme="ECOSYSTEM",
            )
        )
    return records
