"""M18 token clone indicator: exact normalized runs, overlap-merged lines."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.quality.loc import nloc_line_numbers
from codestrata.application.evidence.quality.maps import (
    CLONE_FORMULA_VERSION,
    CLONE_MIN_LINES,
    CLONE_MIN_TOKENS,
    TOKEN_NORMALIZATION_VERSION,
    QualityBudgets,
    language_for_path,
)
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    CloneRun,
    CloneSpan,
    CoverageScope,
    FileRole,
    MetricStatusName,
)
from codestrata.application.evidence.quality.roles import clone_eligible, file_role, is_ignored
from codestrata.application.evidence.quality.tokenize import (
    clone_key,
    normalize_tokens,
    tokenize_source,
)


def collect_clone_metric(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    budgets: QualityBudgets,
) -> tuple[CloneMetric, tuple[str, ...]]:
    streams: list[tuple[str, tuple[str, ...], tuple[int, ...]]] = []
    eligible_lines: dict[str, frozenset[int]] = {}
    limitations: list[str] = []
    unsupported = 0
    tokens_used = 0
    cutoff = False
    considered = 0
    for raw in sorted({item.replace("\\", "/") for item in relative_paths}):
        if not raw:
            continue
        role = file_role(raw)
        language = language_for_path(raw)
        if raw in file_texts:
            text = file_texts[raw]
        elif raw.replace("/", "\\") in file_texts:
            text = file_texts[raw.replace("/", "\\")]
        else:
            continue
        if language is None:
            continue
        if role is FileRole.GENERATED:
            limitations.append(f"generated_excluded:{raw}")
            continue
        if role is FileRole.VENDOR:
            limitations.append(f"vendor_excluded:{raw}")
            continue
        if is_ignored(raw):
            continue
        if not clone_eligible(raw, role):
            unsupported += 1
            limitations.append(f"unsupported_tokenization:{raw}")
            continue
        if considered >= budgets.max_files:
            cutoff = True
            limitations.append(f"scan_cutoff:{raw}")
            continue
        considered += 1
        tokens = normalize_tokens(tokenize_source(text, language=language), language=language)
        if tokens_used + len(tokens) > budgets.max_tokens:
            cutoff = True
            limitations.append(f"token_cutoff:{raw}")
            continue
        tokens_used += len(tokens)
        keys = tuple(clone_key(token) for token in tokens)
        lines = tuple(token.line for token in tokens)
        streams.append((raw, keys, lines))
        eligible_lines[raw] = nloc_line_numbers(text, language=language)
    denominator = sum(len(lines) for lines in eligible_lines.values())
    if denominator == 0:
        status = MetricStatusName.NOT_APPLICABLE
        full_scope = CoverageScope.NOT_APPLICABLE
        reason = "no_eligible_lines"
        if cutoff:
            status = MetricStatusName.UNKNOWN
            full_scope = CoverageScope.UNKNOWN
            reason = "scan_cutoff"
        return (
            CloneMetric(
                status=status,
                numerator=None,
                denominator=None if status is MetricStatusName.UNKNOWN else 0,
                serialized=None,
                full_scope_status=full_scope,
                reason=reason,
                normalization_version=TOKEN_NORMALIZATION_VERSION,
                formula_version=CLONE_FORMULA_VERSION,
                min_tokens=CLONE_MIN_TOKENS,
                min_lines=CLONE_MIN_LINES,
                cutoff=cutoff,
                unsupported_files=unsupported,
            ),
            tuple(sorted(set(limitations))),
        )
    runs = _find_runs(streams)
    merged = _merge_spans(tuple(run.left for run in runs) + tuple(run.right for run in runs))
    covered: dict[str, set[int]] = defaultdict(set)
    for span in merged:
        eligible = eligible_lines.get(span.path, frozenset())
        for line in range(span.line_start, span.line_end + 1):
            if line in eligible:
                covered[span.path].add(line)
    numerator = sum(len(lines) for lines in covered.values())
    ratio = f"{numerator / denominator:.6f}"
    full_scope = CoverageScope.COMPLETE
    status = MetricStatusName.VALUE
    reason = "merged_duplicate_lines"
    if cutoff or unsupported:
        full_scope = CoverageScope.PARTIAL if numerator or denominator else CoverageScope.UNKNOWN
        reason = "scan_cutoff" if cutoff else "unsupported_tokenization"
        if cutoff:
            status = MetricStatusName.VALUE
    return (
        CloneMetric(
            status=status,
            numerator=numerator,
            denominator=denominator,
            serialized=ratio,
            full_scope_status=full_scope,
            reason=reason,
            normalization_version=TOKEN_NORMALIZATION_VERSION,
            formula_version=CLONE_FORMULA_VERSION,
            min_tokens=CLONE_MIN_TOKENS,
            min_lines=CLONE_MIN_LINES,
            runs=runs,
            merged_spans=merged,
            cutoff=cutoff,
            unsupported_files=unsupported,
        ),
        tuple(sorted(set(limitations))),
    )


def _find_runs(
    streams: Sequence[tuple[str, tuple[str, ...], tuple[int, ...]]],
) -> tuple[CloneRun, ...]:
    locations: dict[tuple[str, ...], list[tuple[int, int]]] = defaultdict(list)
    for file_index, (_path, keys, _lines) in enumerate(streams):
        if len(keys) < CLONE_MIN_TOKENS:
            continue
        for start in range(0, len(keys) - CLONE_MIN_TOKENS + 1):
            window = keys[start : start + CLONE_MIN_TOKENS]
            locations[window].append((file_index, start))
    seen: set[tuple[tuple[str, int, int], tuple[str, int, int]]] = set()
    runs: list[CloneRun] = []
    for _window, occ in locations.items():
        if len(occ) < 2:
            continue
        unique = list(dict.fromkeys(occ))
        for left_i, (left_file, left_start) in enumerate(unique):
            for right_file, right_start in unique[left_i + 1 :]:
                if left_file == right_file and left_start == right_start:
                    continue
                run = _extend(streams, left_file, left_start, right_file, right_start)
                if run is None:
                    continue
                key = (
                    (run.left.path, run.left.line_start, run.left.line_end),
                    (run.right.path, run.right.line_start, run.right.line_end),
                )
                if key in seen or (key[1], key[0]) in seen:
                    continue
                seen.add(key)
                runs.append(run)
    ordered = sorted(
        runs,
        key=lambda item: (
            item.left.path,
            item.left.line_start,
            item.right.path,
            item.right.line_start,
            -item.token_count,
        ),
    )
    return tuple(ordered)


def _extend(
    streams: Sequence[tuple[str, tuple[str, ...], tuple[int, ...]]],
    left_file: int,
    left_start: int,
    right_file: int,
    right_start: int,
) -> CloneRun | None:
    left_path, left_keys, left_lines = streams[left_file]
    right_path, right_keys, right_lines = streams[right_file]
    length = CLONE_MIN_TOKENS
    while (
        left_start + length < len(left_keys)
        and right_start + length < len(right_keys)
        and left_keys[left_start + length] == right_keys[right_start + length]
    ):
        length += 1
    left_span_lines = left_lines[left_start : left_start + length]
    right_span_lines = right_lines[right_start : right_start + length]
    left_span = max(left_span_lines) - min(left_span_lines) + 1
    right_span = max(right_span_lines) - min(right_span_lines) + 1
    if left_span < CLONE_MIN_LINES or right_span < CLONE_MIN_LINES:
        return None
    left = CloneSpan(
        path=left_path,
        line_start=min(left_span_lines),
        line_end=max(left_span_lines),
        token_count=length,
    )
    right = CloneSpan(
        path=right_path,
        line_start=min(right_span_lines),
        line_end=max(right_span_lines),
        token_count=length,
    )
    if (left.path, left.line_start, left.line_end) > (
        right.path,
        right.line_start,
        right.line_end,
    ):
        left, right = right, left
    return CloneRun(
        run_id=f"{left.path}:{left.line_start}-{left.line_end}|{right.path}:{right.line_start}-{right.line_end}",
        left=left,
        right=right,
        token_count=length,
        line_span=min(left_span, right_span),
        normalization_version=TOKEN_NORMALIZATION_VERSION,
    )


def _merge_spans(spans: Sequence[CloneSpan]) -> tuple[CloneSpan, ...]:
    by_path: dict[str, list[CloneSpan]] = defaultdict(list)
    for span in spans:
        by_path[span.path].append(span)
    merged: list[CloneSpan] = []
    for path in sorted(by_path):
        ordered = sorted(by_path[path], key=lambda item: (item.line_start, item.line_end))
        current = ordered[0]
        for span in ordered[1:]:
            if span.line_start <= current.line_end + 1:
                current = CloneSpan(
                    path=path,
                    line_start=current.line_start,
                    line_end=max(current.line_end, span.line_end),
                    token_count=current.token_count + span.token_count,
                )
            else:
                merged.append(current)
                current = span
        merged.append(current)
    return tuple(merged)


__all__ = ["collect_clone_metric"]
