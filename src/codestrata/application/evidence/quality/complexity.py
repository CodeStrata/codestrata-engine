"""Collect M16/M17 function and file-size records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.quality.java import extract_java_functions
from codestrata.application.evidence.quality.javascript import extract_js_functions
from codestrata.application.evidence.quality.loc import nloc_count, physical_line_count
from codestrata.application.evidence.quality.maps import (
    SIZE_FORMULA_VERSION,
    SUPPORTED_COMPLEXITY_LANGUAGES,
    QualityBudgets,
    language_for_path,
)
from codestrata.application.evidence.quality.models import (
    FileRole,
    FileSizeRecord,
    FunctionDistribution,
    FunctionRecord,
    FunctionStatus,
    MetricStatusName,
)
from codestrata.application.evidence.quality.python import extract_python_functions
from codestrata.application.evidence.quality.roles import file_role, is_ignored


def collect_functions_and_sizes(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    budgets: QualityBudgets,
) -> tuple[
    tuple[FunctionRecord, ...],
    tuple[FileSizeRecord, ...],
    FunctionDistribution,
    tuple[str, ...],
    int,
]:
    functions: list[FunctionRecord] = []
    files: list[FileSizeRecord] = []
    limitations: list[str] = []
    cutoff_files = 0
    considered = 0
    for raw in sorted({item.replace("\\", "/") for item in relative_paths}):
        if not raw or is_ignored(raw):
            continue
        language = language_for_path(raw)
        role = file_role(raw)
        if raw in file_texts:
            text = file_texts[raw]
        elif raw.replace("/", "\\") in file_texts:
            text = file_texts[raw.replace("/", "\\")]
        else:
            continue
        if language is None or language not in SUPPORTED_COMPLEXITY_LANGUAGES:
            if language is not None:
                files.append(
                    FileSizeRecord(
                        path=raw,
                        language=language,
                        role=role,
                        nloc=None,
                        physical_lines=physical_line_count(text),
                        function_count=0,
                        unknown_functions=0,
                        size_version=SIZE_FORMULA_VERSION,
                        parse_status=MetricStatusName.UNKNOWN,
                        unknown_reason="unsupported_language_map",
                    )
                )
                limitations.append(f"unsupported_language:{raw}")
            continue
        payload = text.encode("utf-8")
        if len(payload) > budgets.max_file_bytes:
            files.append(
                FileSizeRecord(
                    path=raw,
                    language=language,
                    role=role,
                    nloc=None,
                    physical_lines=physical_line_count(text),
                    function_count=0,
                    unknown_functions=0,
                    size_version=SIZE_FORMULA_VERSION,
                    parse_status=MetricStatusName.UNKNOWN,
                    unknown_reason="file_over_budget",
                )
            )
            limitations.append(f"file_over_budget:{raw}")
            continue
        if considered >= budgets.max_files:
            cutoff_files += 1
            limitations.append(f"scan_cutoff:{raw}")
            continue
        considered += 1
        extracted, incomplete = _extract(language=language, path=raw, text=text, role=role)
        functions.extend(extracted)
        unknown = sum(1 for item in extracted if item.status is FunctionStatus.UNKNOWN)
        parse_status = MetricStatusName.VALUE
        reason = None
        if incomplete and not extracted:
            parse_status = MetricStatusName.UNKNOWN
            reason = "malformed_syntax"
            limitations.append(f"malformed_syntax:{raw}")
        elif incomplete:
            parse_status = MetricStatusName.UNKNOWN
            reason = "partial_parse"
            limitations.append(f"partial_parse:{raw}")
        files.append(
            FileSizeRecord(
                path=raw,
                language=language,
                role=role,
                nloc=nloc_count(text, language=language),
                physical_lines=physical_line_count(text),
                function_count=len(extracted),
                unknown_functions=unknown,
                size_version=SIZE_FORMULA_VERSION,
                parse_status=parse_status,
                unknown_reason=reason,
            )
        )
    languages = tuple(sorted({item.language for item in functions}))
    distribution = FunctionDistribution(
        measured=sum(1 for item in functions if item.status is FunctionStatus.MEASURED),
        unknown=sum(1 for item in functions if item.status is FunctionStatus.UNKNOWN),
        languages=languages,
    )
    ordered_functions = tuple(
        sorted(functions, key=lambda item: (item.path, item.span.line_start, item.qualified_name))
    )
    ordered_files = tuple(sorted(files, key=lambda item: item.path))
    notes = tuple(sorted(set(limitations)))
    return ordered_functions, ordered_files, distribution, notes, cutoff_files


def _extract(
    *, language: str, path: str, text: str, role: FileRole
) -> tuple[tuple[FunctionRecord, ...], bool]:
    if language == "java":
        return extract_java_functions(path=path, text=text, role=role)
    if language in {"javascript", "typescript"}:
        return extract_js_functions(path=path, text=text, role=role, language=language)
    if language == "python":
        return extract_python_functions(path=path, text=text, role=role)
    return (), True


__all__ = ["collect_functions_and_sizes"]
