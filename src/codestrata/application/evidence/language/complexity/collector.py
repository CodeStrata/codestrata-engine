"""Collect and aggregate structural complexity evidence (Phase 4.3.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.language.complexity.csharp_extractor import (
    extract_csharp_file_complexity,
)
from codestrata.application.evidence.language.complexity.java_extractor import (
    extract_java_file_complexity,
)
from codestrata.application.evidence.language.complexity.paths import (
    DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    select_complexity_paths,
    texts_for_paths,
)
from codestrata.application.evidence.language.complexity.php_extractor import (
    extract_php_file_complexity,
)
from codestrata.application.evidence.language.complexity.python_extractor import (
    extract_python_file_complexity,
)
from codestrata.domain.evidence.language.complexity.identifiers import (
    CSHARP_COMPLEXITY_PROVIDER_ID,
    CSHARP_COMPLEXITY_PROVIDER_VERSION,
    JAVA_COMPLEXITY_PROVIDER_ID,
    JAVA_COMPLEXITY_PROVIDER_VERSION,
    PHP_COMPLEXITY_PROVIDER_ID,
    PHP_COMPLEXITY_PROVIDER_VERSION,
    PYTHON_COMPLEXITY_PROVIDER_ID,
    PYTHON_COMPLEXITY_PROVIDER_VERSION,
)
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    CallableComplexityEvidence,
    ComplexityEvidenceBundle,
    FileComplexityEvidence,
    TypeComplexityEvidence,
)


def collect_python_complexity_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    configuration_fingerprint: str = "",
) -> ComplexityEvidenceBundle:
    paths, excluded = select_complexity_paths(
        relative_paths,
        language="python",
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    texts = texts_for_paths(paths, file_texts)
    files: list[FileComplexityEvidence] = []
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    diagnostics: list[str] = []
    analyzed = 0
    failed = 0
    for path in paths:
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"missing_text:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"truncated:{path}")
        result = extract_python_file_complexity(
            path=path,
            text=text,
            configuration_fingerprint=configuration_fingerprint,
        )
        files.append(result.file)
        types.extend(result.types)
        callables.extend(result.callables)
        analyzed += 1
        if result.failed:
            failed += 1
            if result.diagnostic:
                diagnostics.append(result.diagnostic)
    return ComplexityEvidenceBundle(
        provider_id=PYTHON_COMPLEXITY_PROVIDER_ID,
        provider_version=PYTHON_COMPLEXITY_PROVIDER_VERSION,
        language="python",
        files=tuple(sorted(files, key=lambda item: item.path)),
        types=tuple(
            sorted(types, key=lambda item: (item.path, item.qualified_name))
        ),
        callables=tuple(
            sorted(
                callables,
                key=lambda item: (
                    item.path,
                    item.span.line_start or 0,
                    item.qualified_signature,
                ),
            )
        ),
        files_considered=len(paths),
        files_analyzed=analyzed,
        files_excluded=excluded,
        files_failed=failed,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def collect_java_complexity_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    configuration_fingerprint: str = "",
) -> ComplexityEvidenceBundle:
    paths, excluded = select_complexity_paths(
        relative_paths,
        language="java",
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    texts = texts_for_paths(paths, file_texts)
    files: list[FileComplexityEvidence] = []
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    diagnostics: list[str] = []
    analyzed = 0
    failed = 0
    for path in paths:
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"missing_text:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"truncated:{path}")
        result = extract_java_file_complexity(
            path=path,
            text=text,
            configuration_fingerprint=configuration_fingerprint,
        )
        files.append(result.file)
        types.extend(result.types)
        callables.extend(result.callables)
        analyzed += 1
        if result.failed:
            failed += 1
            if result.diagnostic:
                diagnostics.append(result.diagnostic)
    return ComplexityEvidenceBundle(
        provider_id=JAVA_COMPLEXITY_PROVIDER_ID,
        provider_version=JAVA_COMPLEXITY_PROVIDER_VERSION,
        language="java",
        files=tuple(sorted(files, key=lambda item: item.path)),
        types=tuple(
            sorted(types, key=lambda item: (item.path, item.qualified_name))
        ),
        callables=tuple(
            sorted(
                callables,
                key=lambda item: (
                    item.path,
                    item.span.line_start or 0,
                    item.qualified_signature,
                ),
            )
        ),
        files_considered=len(paths),
        files_analyzed=analyzed,
        files_excluded=excluded,
        files_failed=failed,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def collect_php_complexity_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    configuration_fingerprint: str = "",
) -> ComplexityEvidenceBundle:
    paths, excluded = select_complexity_paths(
        relative_paths,
        language="php",
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    texts = texts_for_paths(paths, file_texts)
    files: list[FileComplexityEvidence] = []
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    diagnostics: list[str] = []
    analyzed = 0
    failed = 0
    for path in paths:
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"missing_text:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"truncated:{path}")
        result = extract_php_file_complexity(
            path=path,
            text=text,
            configuration_fingerprint=configuration_fingerprint,
        )
        files.append(result.file)
        types.extend(result.types)
        callables.extend(result.callables)
        analyzed += 1
        if result.failed:
            failed += 1
            if result.diagnostic:
                diagnostics.append(result.diagnostic)
    return ComplexityEvidenceBundle(
        provider_id=PHP_COMPLEXITY_PROVIDER_ID,
        provider_version=PHP_COMPLEXITY_PROVIDER_VERSION,
        language="php",
        files=tuple(sorted(files, key=lambda item: item.path)),
        types=tuple(
            sorted(types, key=lambda item: (item.path, item.qualified_name))
        ),
        callables=tuple(
            sorted(
                callables,
                key=lambda item: (
                    item.path,
                    item.span.line_start or 0,
                    item.qualified_signature,
                ),
            )
        ),
        files_considered=len(paths),
        files_analyzed=analyzed,
        files_excluded=excluded,
        files_failed=failed,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def collect_csharp_complexity_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str] = DEFAULT_COMPLEXITY_IGNORE_MARKERS,
    max_files: int = 2000,
    max_file_chars: int = 100_000,
    configuration_fingerprint: str = "",
) -> ComplexityEvidenceBundle:
    paths, excluded = select_complexity_paths(
        relative_paths,
        language="csharp",
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    texts = texts_for_paths(paths, file_texts)
    files: list[FileComplexityEvidence] = []
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    diagnostics: list[str] = []
    analyzed = 0
    failed = 0
    for path in paths:
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"missing_text:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"truncated:{path}")
        result = extract_csharp_file_complexity(
            path=path,
            text=text,
            configuration_fingerprint=configuration_fingerprint,
        )
        files.append(result.file)
        types.extend(result.types)
        callables.extend(result.callables)
        analyzed += 1
        if result.failed:
            failed += 1
            if result.diagnostic:
                diagnostics.append(result.diagnostic)
    return ComplexityEvidenceBundle(
        provider_id=CSHARP_COMPLEXITY_PROVIDER_ID,
        provider_version=CSHARP_COMPLEXITY_PROVIDER_VERSION,
        language="csharp",
        files=tuple(sorted(files, key=lambda item: item.path)),
        types=tuple(
            sorted(types, key=lambda item: (item.path, item.qualified_name))
        ),
        callables=tuple(
            sorted(
                callables,
                key=lambda item: (
                    item.path,
                    item.span.line_start or 0,
                    item.qualified_signature,
                ),
            )
        ),
        files_considered=len(paths),
        files_analyzed=analyzed,
        files_excluded=excluded,
        files_failed=failed,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def aggregate_complexity_bundles(
    *,
    repository_id: str,
    bundles: Sequence[ComplexityEvidenceBundle],
) -> AggregatedComplexityEvidence:
    ordered = tuple(sorted(bundles, key=lambda item: (item.language, item.provider_id)))
    files: list[FileComplexityEvidence] = []
    types: list[TypeComplexityEvidence] = []
    callables: list[CallableComplexityEvidence] = []
    diagnostics: list[str] = []
    providers: list[str] = []
    for bundle in ordered:
        providers.append(bundle.provider_id)
        diagnostics.extend(bundle.diagnostics)
        files.extend(bundle.files)
        types.extend(bundle.types)
        callables.extend(bundle.callables)
    return AggregatedComplexityEvidence(
        repository_id=repository_id,
        bundles=ordered,
        files=tuple(sorted(files, key=lambda item: (item.language, item.path))),
        types=tuple(
            sorted(types, key=lambda item: (item.language, item.path, item.qualified_name))
        ),
        callables=tuple(
            sorted(
                callables,
                key=lambda item: (
                    item.language,
                    item.path,
                    item.span.line_start or 0,
                    item.qualified_signature,
                ),
            )
        ),
        contributing_provider_ids=tuple(sorted(set(providers))),
        diagnostics=tuple(sorted(set(diagnostics))),
    )
