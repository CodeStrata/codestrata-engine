"""Python pyproject.toml and requirements.txt Dependency Evidence collectors."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.dependency.normalize import (
    normalize_python_distribution_name,
)
from codestrata.application.evidence.dependency.paths import (
    classification_for_path,
    classify_manifest_basename,
    select_manifest_paths,
    texts_for_paths,
)
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.identifiers import (
    PYTHON_PROVIDER_ID,
    PYTHON_PROVIDER_VERSION,
    make_declaration_evidence_id,
    make_manifest_evidence_id,
)
from codestrata.domain.evidence.dependency.models import (
    DependencyDeclarationEvidence,
    DependencyEvidenceBundle,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance

_REQ_LINE = re.compile(
    r"""^\s*(?P<editable>-e\s+)?(?P<path>\.?\.?/[^\s;]+|[A-Za-z0-9_.-]+(?:\[[^\]]+\])?)"""
    r"""(?P<spec>(?:[=<>!~]=?|===)[^;]+)?(?:\s*;\s*(?P<marker>.+))?\s*$"""
)
_INCLUDE = re.compile(r"^\s*(?:-r|--requirement)\s+(?P<target>\S+)\s*$", re.IGNORECASE)
_UNSUPPORTED_DIRECTIVE = re.compile(
    r"^\s*(?:-i|--index-url|-f|--find-links|--extra-index-url|--trusted-host|--no-index)\b",
    re.IGNORECASE,
)
_NAME_EXTRAS = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[^\]]+)\])?$"
)


def _provenance(path: str, fingerprint: str, method: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PYTHON_PROVIDER_ID,
        provider_version=PYTHON_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method=method,
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        configuration_fingerprint=fingerprint,
        transformation_chain=("python",),
    )


def _parse_requirement_token(
    token: str,
) -> tuple[str, str, tuple[str, ...], str | None, str | None]:
    """Return original, normalized, extras, version_spec, marker."""

    marker = None
    body = token.strip()
    if ";" in body:
        body, marker = body.split(";", 1)
        marker = marker.strip() or None
        body = body.strip()
    # Prefer packaging-style split on version operators.
    version = None
    name_part = body
    for operator in ("===", "==", ">=", "<=", "!=", "~=", ">", "<"):
        if operator in body:
            name_part, version = body.split(operator, 1)
            version = f"{operator}{version.strip()}"
            break
    name_match = _NAME_EXTRAS.match(name_part.strip())
    if name_match is None:
        original = body
        return original, normalize_python_distribution_name(original), (), version, marker
    original = name_match.group("name")
    extras_raw = name_match.group("extras")
    extras = tuple(
        item.strip() for item in (extras_raw or "").split(",") if item.strip()
    )
    return (
        original,
        normalize_python_distribution_name(original),
        extras,
        version,
        marker,
    )


def _declaration_from_req(
    *,
    path: str,
    manifest_type: DependencyManifestType,
    original: str,
    normalized: str,
    kind: DependencyDeclarationKind,
    raw_version: str | None,
    extras: tuple[str, ...],
    marker: str | None,
    group_name: str | None,
    line: int | None,
    snippet: str,
    fingerprint: str,
    is_editable: bool = False,
    is_local_path: bool = False,
) -> DependencyDeclarationEvidence:
    return DependencyDeclarationEvidence(
        evidence_id=make_declaration_evidence_id(
            provider_id=PYTHON_PROVIDER_ID,
            path=path,
            identity=normalized,
            kind=kind.value,
            raw_version=raw_version or "",
            profile=group_name or "",
            line=str(line or 0),
        ),
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=manifest_type,
        declaration_kind=kind,
        normalized_identity=normalized,
        original_identity=original,
        raw_version=raw_version,
        resolved_version_local=None,
        version_availability=(
            DependencyEvidenceAvailability.AVAILABLE
            if raw_version
            else DependencyEvidenceAvailability.UNAVAILABLE
        ),
        version_resolution_status=(
            DependencyVersionResolutionStatus.RESOLVED
            if raw_version
            else DependencyVersionResolutionStatus.NOT_APPLICABLE
        ),
        extras=extras,
        environment_marker=marker,
        group_name=group_name,
        is_editable=is_editable,
        is_local_path=is_local_path,
        source=DependencySourceLocation(
            path=path,
            line_start=line,
            line_end=line,
            snippet=snippet[:200],
        ),
        classification=classification_for_path(path),
        provenance=_provenance(path, fingerprint, "python_manifest_parse"),
    )


def parse_pyproject_text(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> tuple[DependencyManifestEvidence, tuple[DependencyDeclarationEvidence, ...]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=PYTHON_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.PYTHON,
            manifest_type=DependencyManifestType.PYPROJECT_TOML,
            parse_status=DependencyParseStatus.FAILED,
            classification=classification_for_path(path),
            diagnostics=(f"pyproject_parse_error:{error}",),
            provenance=_provenance(path, configuration_fingerprint, "toml_parse"),
        )
        return manifest, ()

    declarations: list[DependencyDeclarationEvidence] = []
    unsupported: list[str] = []
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    deps = project.get("dependencies") if isinstance(project, dict) else None
    if isinstance(deps, list):
        for index, item in enumerate(deps):
            if not isinstance(item, str):
                unsupported.append(f"{path}:project.dependencies[{index}]:non_string")
                continue
            original, normalized, extras, version, marker = _parse_requirement_token(item)
            declarations.append(
                _declaration_from_req(
                    path=path,
                    manifest_type=DependencyManifestType.PYPROJECT_TOML,
                    original=original,
                    normalized=normalized,
                    kind=DependencyDeclarationKind.RUNTIME,
                    raw_version=version,
                    extras=extras,
                    marker=marker,
                    group_name=None,
                    line=None,
                    snippet=item,
                    fingerprint=configuration_fingerprint,
                )
            )
    optional = (
        project.get("optional-dependencies") if isinstance(project, dict) else None
    )
    if isinstance(optional, dict):
        for group, items in sorted(optional.items()):
            if not isinstance(items, list):
                unsupported.append(
                    f"{path}:optional-dependencies.{group}:non_list"
                )
                continue
            for index, item in enumerate(items):
                if not isinstance(item, str):
                    unsupported.append(
                        f"{path}:optional-dependencies.{group}[{index}]:non_string"
                    )
                    continue
                original, normalized, extras, version, marker = _parse_requirement_token(
                    item
                )
                declarations.append(
                    _declaration_from_req(
                        path=path,
                        manifest_type=DependencyManifestType.PYPROJECT_TOML,
                        original=original,
                        normalized=normalized,
                        kind=DependencyDeclarationKind.OPTIONAL,
                        raw_version=version,
                        extras=extras,
                        marker=marker,
                        group_name=str(group),
                        line=None,
                        snippet=item,
                        fingerprint=configuration_fingerprint,
                    )
                )

    poetry = data.get("tool", {}).get("poetry") if isinstance(data.get("tool"), dict) else None
    if isinstance(poetry, dict):
        poetry_deps = poetry.get("dependencies")
        if isinstance(poetry_deps, dict):
            for name, spec in sorted(poetry_deps.items()):
                if str(name).lower() == "python":
                    continue
                original = str(name)
                normalized = normalize_python_distribution_name(original)
                raw_version = None
                if isinstance(spec, str):
                    raw_version = spec
                elif isinstance(spec, dict):
                    version_value = spec.get("version")
                    if isinstance(version_value, str):
                        raw_version = version_value
                    else:
                        unsupported.append(
                            f"{path}:poetry.dependencies.{name}:complex_table"
                        )
                else:
                    unsupported.append(
                        f"{path}:poetry.dependencies.{name}:unsupported_spec"
                    )
                    continue
                declarations.append(
                    _declaration_from_req(
                        path=path,
                        manifest_type=DependencyManifestType.PYPROJECT_TOML,
                        original=original,
                        normalized=normalized,
                        kind=DependencyDeclarationKind.RUNTIME,
                        raw_version=raw_version,
                        extras=(),
                        marker=None,
                        group_name="poetry",
                        line=None,
                        snippet=f"{original}={raw_version}",
                        fingerprint=configuration_fingerprint,
                    )
                )
        poetry_group = poetry.get("group")
        if isinstance(poetry_group, dict):
            for group_name, group_body in sorted(poetry_group.items()):
                if not isinstance(group_body, dict):
                    continue
                group_deps = group_body.get("dependencies")
                if not isinstance(group_deps, dict):
                    continue
                kind = (
                    DependencyDeclarationKind.DEVELOPMENT
                    if str(group_name).lower() in {"dev", "test"}
                    else DependencyDeclarationKind.OPTIONAL
                )
                for name, spec in sorted(group_deps.items()):
                    original = str(name)
                    normalized = normalize_python_distribution_name(original)
                    raw_version = spec if isinstance(spec, str) else None
                    if raw_version is None and isinstance(spec, dict):
                        version_value = spec.get("version")
                        raw_version = (
                            version_value if isinstance(version_value, str) else None
                        )
                    declarations.append(
                        _declaration_from_req(
                            path=path,
                            manifest_type=DependencyManifestType.PYPROJECT_TOML,
                            original=original,
                            normalized=normalized,
                            kind=kind,
                            raw_version=raw_version,
                            extras=(),
                            marker=None,
                            group_name=f"poetry.group.{group_name}",
                            line=None,
                            snippet=f"{original}",
                            fingerprint=configuration_fingerprint,
                        )
                    )

    ordered = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.group_name or "",
                item.normalized_identity,
                item.declaration_kind.value,
                item.evidence_id,
            ),
        )
    )
    unique_unsupported = tuple(sorted(set(unsupported)))
    status = (
        DependencyParseStatus.PARTIALLY_SUCCEEDED
        if unique_unsupported
        else DependencyParseStatus.SUCCEEDED
    )
    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=PYTHON_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.PYPROJECT_TOML,
        parse_status=status if ordered or unique_unsupported else DependencyParseStatus.SUCCEEDED,
        classification=classification_for_path(path),
        declaration_count=len(ordered),
        unsupported_constructs=unique_unsupported,
        provenance=_provenance(path, configuration_fingerprint, "toml_parse"),
    )
    return manifest, ordered


def parse_requirements_text(
    *,
    path: str,
    text: str,
    file_texts: Mapping[str, str],
    configuration_fingerprint: str = "",
    _stack: tuple[str, ...] = (),
    max_include_depth: int = 5,
) -> tuple[DependencyManifestEvidence, tuple[DependencyDeclarationEvidence, ...]]:
    declarations: list[DependencyDeclarationEvidence] = []
    unsupported: list[str] = []
    diagnostics: list[str] = []
    if path in _stack:
        diagnostics.append(f"requirements_include_cycle:{'->'.join(_stack+(path,))}")
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=PYTHON_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.PYTHON,
            manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
            parse_status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
            classification=classification_for_path(path),
            diagnostics=tuple(diagnostics),
            provenance=_provenance(path, configuration_fingerprint, "requirements_parse"),
        )
        return manifest, ()

    if len(_stack) >= max_include_depth:
        diagnostics.append(f"requirements_include_depth_exceeded:{path}")
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=PYTHON_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.PYTHON,
            manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
            parse_status=DependencyParseStatus.PARTIALLY_SUCCEEDED,
            classification=classification_for_path(path),
            diagnostics=tuple(diagnostics),
            provenance=_provenance(path, configuration_fingerprint, "requirements_parse"),
        )
        return manifest, ()

    parent = str(PurePosixPath(path).parent)
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        include = _INCLUDE.match(line)
        if include is not None:
            target = include.group("target").strip()
            if "://" in target or target.startswith("http"):
                unsupported.append(f"{path}:{line_no}:remote_include:{target}")
                continue
            if target.startswith("/"):
                unsupported.append(f"{path}:{line_no}:absolute_include:{target}")
                continue
            included_path = (
                target
                if parent in {"", "."}
                else str(PurePosixPath(parent) / target)
            )
            included_path = included_path.replace("\\", "/")
            included_text = file_texts.get(included_path)
            if included_text is None:
                unsupported.append(f"{path}:{line_no}:missing_include:{included_path}")
                continue
            _child_manifest, child_decls = parse_requirements_text(
                path=included_path,
                text=included_text,
                file_texts=file_texts,
                configuration_fingerprint=configuration_fingerprint,
                _stack=_stack + (path,),
                max_include_depth=max_include_depth,
            )
            declarations.extend(child_decls)
            unsupported.extend(_child_manifest.unsupported_constructs)
            diagnostics.extend(_child_manifest.diagnostics)
            continue
        if _UNSUPPORTED_DIRECTIVE.match(line):
            unsupported.append(f"{path}:{line_no}:directive:{line[:120]}")
            continue
        if line.startswith("-e ") or line.startswith("--editable"):
            target = line.split(None, 1)[1] if " " in line else line
            is_local = target.startswith(".") or target.startswith("/")
            if "://" in target and not target.startswith("git+file"):
                unsupported.append(f"{path}:{line_no}:remote_editable:{target[:120]}")
                continue
            identity = normalize_python_distribution_name(
                PurePosixPath(target.rstrip("/")).name or target
            )
            declarations.append(
                _declaration_from_req(
                    path=path,
                    manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                    original=target,
                    normalized=identity,
                    kind=DependencyDeclarationKind.RUNTIME,
                    raw_version=None,
                    extras=(),
                    marker=None,
                    group_name=None,
                    line=line_no,
                    snippet=line,
                    fingerprint=configuration_fingerprint,
                    is_editable=True,
                    is_local_path=is_local,
                )
            )
            continue
        if line.startswith(".") or line.startswith("/"):
            identity = normalize_python_distribution_name(
                PurePosixPath(line.split(";", 1)[0].strip()).name or line
            )
            declarations.append(
                _declaration_from_req(
                    path=path,
                    manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                    original=line,
                    normalized=identity,
                    kind=DependencyDeclarationKind.RUNTIME,
                    raw_version=None,
                    extras=(),
                    marker=None,
                    group_name=None,
                    line=line_no,
                    snippet=line,
                    fingerprint=configuration_fingerprint,
                    is_local_path=True,
                )
            )
            continue
        if "://" in line:
            unsupported.append(f"{path}:{line_no}:url_requirement:{line[:120]}")
            continue
        original, normalized, extras, version, marker = _parse_requirement_token(line)
        declarations.append(
            _declaration_from_req(
                path=path,
                manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
                original=original,
                normalized=normalized,
                kind=DependencyDeclarationKind.RUNTIME,
                raw_version=version,
                extras=extras,
                marker=marker,
                group_name=None,
                line=line_no,
                snippet=line,
                fingerprint=configuration_fingerprint,
            )
        )

    ordered = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.source.path,
                item.source.line_start or 0,
                item.normalized_identity,
                item.evidence_id,
            ),
        )
    )
    unique_unsupported = tuple(sorted(set(unsupported)))
    status = (
        DependencyParseStatus.PARTIALLY_SUCCEEDED
        if unique_unsupported or diagnostics
        else DependencyParseStatus.SUCCEEDED
    )
    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=PYTHON_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.PYTHON,
        manifest_type=DependencyManifestType.REQUIREMENTS_TXT,
        parse_status=status,
        classification=classification_for_path(path),
        declaration_count=len(ordered),
        unsupported_constructs=unique_unsupported,
        diagnostics=tuple(sorted(set(diagnostics))),
        provenance=_provenance(path, configuration_fingerprint, "requirements_parse"),
    )
    return manifest, ordered


def collect_python_dependency_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str],
    max_files: int = 500,
    max_file_chars: int = 500_000,
    configuration_fingerprint: str = "",
) -> DependencyEvidenceBundle:
    paths, excluded = select_manifest_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
        ecosystems=(DependencyEcosystem.PYTHON,),
    )
    texts = texts_for_paths(paths, file_texts)
    manifests: list[DependencyManifestEvidence] = []
    declarations: list[DependencyDeclarationEvidence] = []
    diagnostics: list[str] = []
    for path in paths:
        classified = classify_manifest_basename(path)
        if classified is None:
            continue
        _ecosystem, manifest_type = classified
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"python_text_missing:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"python_truncated:{path}")
        if manifest_type is DependencyManifestType.PYPROJECT_TOML:
            manifest, decls = parse_pyproject_text(
                path=path,
                text=text,
                configuration_fingerprint=configuration_fingerprint,
            )
        else:
            manifest, decls = parse_requirements_text(
                path=path,
                text=text,
                file_texts=texts,
                configuration_fingerprint=configuration_fingerprint,
            )
        manifests.append(manifest)
        declarations.extend(decls)

    manifests_t = tuple(sorted(manifests, key=lambda item: item.path))
    declarations_t = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.source.path,
                item.source.line_start or 0,
                item.normalized_identity,
                item.evidence_id,
            ),
        )
    )
    parsed = sum(
        1
        for item in manifests_t
        if item.parse_status is DependencyParseStatus.SUCCEEDED
    )
    partial = sum(
        1
        for item in manifests_t
        if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
    )
    failed = sum(
        1 for item in manifests_t if item.parse_status is DependencyParseStatus.FAILED
    )
    unsupported_count = sum(len(item.unsupported_constructs) for item in manifests_t)
    unresolved_count = sum(len(item.unresolved_expressions) for item in manifests_t)
    if failed and not parsed and not partial:
        status = DependencyParseStatus.FAILED
    elif manifests_t and (partial or failed or unsupported_count or unresolved_count):
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    elif manifests_t:
        status = DependencyParseStatus.SUCCEEDED
    else:
        status = DependencyParseStatus.NOT_APPLICABLE
    coverage = DependencyEvidenceCoverage(
        manifests_discovered=len(paths) + excluded,
        manifests_supported=len(paths),
        manifests_parsed=parsed,
        manifests_partially_parsed=partial,
        manifests_failed=failed,
        manifests_excluded=excluded,
        declarations_collected=len(declarations_t),
        unsupported_construct_count=unsupported_count,
        unresolved_expression_count=unresolved_count,
    )
    return DependencyEvidenceBundle(
        provider_id=PYTHON_PROVIDER_ID,
        provider_version=PYTHON_PROVIDER_VERSION,
        ecosystem=DependencyEcosystem.PYTHON,
        status=status,
        manifests=manifests_t,
        declarations=declarations_t,
        coverage=coverage,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
