"""Project resolved Python imports onto slash-prefix operator edges.

The matcher and operator are unchanged. Dotted package units are not emitted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from codestrata.application.evidence.language.python_imports import (
    DISCOVERY_RULE,
    MAX_PYTHON_FILE_CHARS,
    MAX_PYTHON_FILES,
    ImportCoverageLimitation,
    ImportDisposition,
    PythonImportRecord,
    discover_python_source_roots,
    extract_python_imports,
    resolve_python_imports,
)
from codestrata.application.rules.prepared.models import OperatorFactKind, PreparedOperatorFacts
from codestrata.domain.rules.operators.models import OperatorContext, OperatorEdge, OperatorGraph

BOUNDED_STATIC_PASS_STATEMENT = (
    "No crossing import was found in the bounded static-import coverage of the recorded roots. "
    "This does not prove the absence of undetectable dynamic imports "
    "or of files outside that coverage."
)
COVERAGE_SCOPE = "bounded_static_imports"


@dataclass(frozen=True, slots=True)
class ScanBoundaryCoverage:
    collection_truncated: bool = False
    excluded_python_paths: tuple[str, ...] = ()
    boundary_exclude_paths: tuple[str, ...] = ()
    pruned_directories: tuple[str, ...] = ()
    coverage_diagnostics_capped: bool = False


def scan_boundary_coverage_inputs(
    metadata: Mapping[str, object] | None,
) -> ScanBoundaryCoverage:
    """Return scan-boundary coverage inputs for import projection."""

    if not metadata:
        return ScanBoundaryCoverage()
    boundary = metadata.get("scan_boundary")
    if not isinstance(boundary, dict):
        return ScanBoundaryCoverage()
    truncated = bool(boundary.get("collection_truncated"))
    excluded_raw = boundary.get("excluded_python_paths")
    excluded: tuple[str, ...] = ()
    if isinstance(excluded_raw, list):
        excluded = tuple(
            _posix(str(path))
            for path in excluded_raw
            if str(path).endswith(".py")
        )
    exclude_raw = boundary.get("exclude_paths")
    exclude_paths: tuple[str, ...] = ()
    if isinstance(exclude_raw, list):
        exclude_paths = tuple(_posix(str(path)).rstrip("/") for path in exclude_raw if str(path))
    pruned_raw = boundary.get("pruned_directories")
    pruned: tuple[str, ...] = ()
    if isinstance(pruned_raw, list):
        pruned = tuple(_posix(str(path)).rstrip("/") for path in pruned_raw if str(path))
    diagnostics_capped = bool(
        boundary.get("excluded_python_paths_capped") or boundary.get("pruned_directories_capped")
    )
    return ScanBoundaryCoverage(
        collection_truncated=truncated,
        excluded_python_paths=excluded,
        boundary_exclude_paths=exclude_paths,
        pruned_directories=pruned,
        coverage_diagnostics_capped=diagnostics_capped,
    )


def project_python_import_facts(
    files: Sequence[str],
    texts: Mapping[str, str],
    *,
    source_roots: tuple[str, ...] | None = None,
    external_import_names: tuple[str, ...] = (),
    excluded_paths: Sequence[str] = (),
    unreadable_paths: Sequence[str] = (),
    scan_collection_truncated: bool = False,
    boundary_exclude_paths: Sequence[str] = (),
    pruned_directories: Sequence[str] = (),
    coverage_diagnostics_capped: bool = False,
    total_files: int | None = None,
    max_files: int = MAX_PYTHON_FILES,
    max_file_chars: int = MAX_PYTHON_FILE_CHARS,
) -> PreparedOperatorFacts:
    """Build operator facts from inventoried Python files.

    ``source_roots is None`` discovers roots. A supplied tuple, including an
    empty one, is caller configuration and is not extended.
    """

    inventory = tuple(_posix(path) for path in files)
    python_files = tuple(path for path in inventory if path.endswith(".py"))
    if not python_files:
        return PreparedOperatorFacts(kind=OperatorFactKind.MISSING)
    if source_roots is None:
        roots = discover_python_source_roots(python_files)
        discovery = "discovered"
        rule = DISCOVERY_RULE
    else:
        roots = tuple(_posix(root).rstrip("/") for root in source_roots)
        discovery = "caller"
        rule = ""
    limitations: list[ImportCoverageLimitation] = []
    if not roots:
        limitations.append(ImportCoverageLimitation(code="discovery_failed"))
        return _incomplete(
            roots=roots,
            discovery=discovery,
            rule=rule,
            names=external_import_names,
            limitations=limitations,
        )
    excluded = {_posix(path) for path in excluded_paths}
    unreadable = {_posix(path) for path in unreadable_paths}
    excluded.update(
        _boundary_excluded(python_files, exclude_paths=tuple(boundary_exclude_paths))
    )
    in_root = tuple(path for path in python_files if _under_any(path, roots))
    inventory_python = set(python_files)
    for path in excluded:
        if path.endswith(".py") and _under_any(path, roots) and path not in inventory_python:
            limitations.append(ImportCoverageLimitation(code="excluded_under_root", path=path))
    for directory in pruned_directories:
        pruned = _posix(str(directory)).rstrip("/")
        if pruned and _pruned_overlaps_any_root(pruned, roots):
            limitations.append(ImportCoverageLimitation(code="pruned_under_root", path=pruned))
    if coverage_diagnostics_capped:
        limitations.append(
            ImportCoverageLimitation(code="coverage_diagnostics_capped", detail="scan_boundary")
        )
    for path in python_files:
        if path not in in_root:
            limitations.append(ImportCoverageLimitation(code="outside_roots", path=path))
    readable: list[str] = []
    for path in in_root:
        if path in excluded:
            limitations.append(ImportCoverageLimitation(code="excluded_under_root", path=path))
            continue
        readable.append(path)
    if scan_collection_truncated:
        limitations.append(
            ImportCoverageLimitation(code="file_limit", detail="scan_collection_truncated")
        )
    elif total_files is not None and total_files > len(inventory):
        limitations.append(
            ImportCoverageLimitation(
                code="file_limit",
                detail=f"inventory {len(inventory)} of {total_files}",
            )
        )
    selected = readable
    if len(readable) > max_files:
        limitations.append(ImportCoverageLimitation(code="file_limit", detail=str(max_files)))
        selected = readable[:max_files]
    parsed_files: list[str] = []
    extracted: list[PythonImportRecord] = []
    supplied = {_posix(path): text for path, text in texts.items()}
    for path in selected:
        if path in unreadable or path not in supplied:
            limitations.append(ImportCoverageLimitation(code="unreadable", path=path))
            continue
        text = supplied[path]
        if len(text) > max_file_chars:
            limitations.append(ImportCoverageLimitation(code="text_limit", path=path))
            continue
        file_records = extract_python_imports(path, text)
        if any(record.reason == "syntax_error" for record in file_records):
            extracted.extend(file_records)
            parsed_files.append(path)
            continue
        extracted.extend(file_records)
        parsed_files.append(path)
    resolved = resolve_python_imports(
        extracted,
        files=parsed_files,
        source_roots=roots,
        root_discovery=discovery,
        discovery_rule=rule,
        external_import_names=external_import_names,
    )
    for record in resolved:
        if record.disposition is ImportDisposition.REPOSITORY:
            continue
        if record.disposition is ImportDisposition.EXTERNAL:
            continue
        limitations.append(
            ImportCoverageLimitation(
                code=record.reason or "unresolved",
                path=record.path,
                detail=record.module,
            )
        )
    edges = _edges(resolved)
    nodes = tuple(sorted({node for edge in edges for node in (edge.source, edge.target)}))
    return PreparedOperatorFacts(
        kind=OperatorFactKind.RESOLVED_IMPORTS,
        context=OperatorContext(
            resolved_graph=OperatorGraph(
                nodes=nodes,
                edges=edges,
                complete=not limitations,
            )
        ),
        import_records=resolved,
        source_roots=roots,
        root_discovery=discovery,
        discovery_rule=rule,
        coverage_scope=COVERAGE_SCOPE,
        limitations=tuple(
            sorted(limitations, key=lambda item: (item.code, item.path, item.detail))
        ),
        external_import_names=tuple(external_import_names),
    )


def _incomplete(
    *,
    roots: tuple[str, ...],
    discovery: str,
    rule: str,
    names: tuple[str, ...],
    limitations: list[ImportCoverageLimitation],
) -> PreparedOperatorFacts:
    return PreparedOperatorFacts(
        kind=OperatorFactKind.RESOLVED_IMPORTS,
        context=OperatorContext(
            resolved_graph=OperatorGraph(nodes=(), edges=(), complete=False)
        ),
        source_roots=roots,
        root_discovery=discovery,
        discovery_rule=rule,
        coverage_scope=COVERAGE_SCOPE,
        limitations=tuple(limitations),
        external_import_names=tuple(names),
    )


def _edges(records: Sequence[PythonImportRecord]) -> tuple[OperatorEdge, ...]:
    edges: list[OperatorEdge] = []
    seen: set[tuple[str, str, bool]] = set()
    for record in records:
        if record.disposition is ImportDisposition.EXTERNAL:
            continue
        if record.disposition is ImportDisposition.REPOSITORY and record.target_path:
            edge = (record.path, record.target_path, False)
            unknown = False
            target = record.target_path
        elif record.disposition in {
            ImportDisposition.UNRESOLVED,
            ImportDisposition.EXTRACTION_FAILURE,
        }:
            edge = (record.path, "unresolved", True)
            unknown = True
            target = "unresolved"
        else:
            continue
        if edge in seen or not record.path:
            continue
        seen.add(edge)
        edges.append(
            OperatorEdge(
                source=record.path,
                target=target,
                edge_type="imports",
                unknown=unknown,
            )
        )
    return tuple(sorted(edges, key=lambda item: (item.source, item.target, item.unknown)))


def _boundary_excluded(
    paths: Sequence[str],
    *,
    exclude_paths: tuple[str, ...] = (),
) -> set[str]:
    from codestrata.scan_boundary.service import BoundaryPolicy, BoundaryService

    policy = BoundaryPolicy(exclude_paths=exclude_paths) if exclude_paths else None
    boundary = BoundaryService(policy)
    return {path for path in paths if not boundary.decide(path).included}


def _under_any(path: str, roots: Sequence[str]) -> bool:
    for root in roots:
        if root == "" or _path_segments_under(_path_segments(root), _path_segments(path)):
            return True
    return False


def _pruned_overlaps_any_root(pruned: str, roots: Sequence[str]) -> bool:
    pruned_segments = _path_segments(pruned)
    if not pruned_segments:
        return False
    for root in roots:
        root_segments = _path_segments(root)
        if not root_segments:
            return True
        if _path_segments_under(pruned_segments, root_segments) or _path_segments_under(
            root_segments, pruned_segments
        ):
            return True
    return False


def _path_segments(path: str) -> tuple[str, ...]:
    normalized = _posix(path).strip("/")
    if not normalized:
        return ()
    return PurePosixPath(normalized).parts


def _path_segments_under(prefix: tuple[str, ...], path: tuple[str, ...]) -> bool:
    if len(prefix) > len(path):
        return False
    return path[: len(prefix)] == prefix


def _posix(path: str) -> str:
    return path.replace("\\", "/").strip()
