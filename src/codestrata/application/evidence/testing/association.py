"""M19 static source-to-test association. Not runtime coverage."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.quality.maps import language_for_path
from codestrata.application.evidence.testing.capability import ASSOCIATION_FORMULA_VERSION
from codestrata.application.evidence.testing.models import (
    AssociationConfidence,
    AssociationMethod,
    AssociationMetric,
    AssociationRecord,
    CoverageScope,
    FrameworkCount,
    MetricStatusName,
    TestDeclaration,
)
from codestrata.application.evidence.testing.paths import (
    convention_stems,
    eligible_production,
    is_generated_path,
    is_test_like,
    java_type_from_path,
    module_from_python_path,
    normalize_relative_path,
    production_stem,
    resolve_relative_specifier,
    unsupported_language_for_path,
)

_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", re.MULTILINE)
_JS_IMPORT = re.compile(
    r"(?:from|import|require)\s*\(?\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)


def _python_imports(text: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return tuple(dict.fromkeys(names))


def _js_specifiers(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_JS_IMPORT.findall(text)))


def _match_python_module(module: str, production: Mapping[str, str]) -> str | None:
    exact = [path for path, key in production.items() if key == module]
    if len(exact) == 1:
        return exact[0]
    prefix = module + "."
    nested = [path for path, key in production.items() if key == module or key.startswith(prefix)]
    if len(nested) == 1:
        return nested[0]
    return None


def _match_java_type(imported: str, production: Mapping[str, str]) -> str | None:
    exact = [path for path, key in production.items() if key == imported]
    if len(exact) == 1:
        return exact[0]
    suffix = "." + imported.split(".")[-1]
    named = [path for path, key in production.items() if key.endswith(suffix) or key == imported]
    if len(named) == 1:
        return named[0]
    return None


def _js_candidates(test_path: str, specifier: str) -> tuple[str, ...]:
    if specifier.startswith("."):
        base = resolve_relative_specifier(test_path, specifier)
    else:
        base = specifier.replace("\\", "/")
    stems = [base]
    for extra in (".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts"):
        if not base.endswith(extra):
            stems.append(base + extra)
    return tuple(stems)


def collect_association_metric(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    tests: Sequence[TestDeclaration],
    notes: list[str],
) -> AssociationMetric:
    production: dict[str, str] = {}
    production_language: dict[str, str] = {}
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not eligible_production(path):
            continue
        language = language_for_path(path)
        if language is None:
            continue
        production_language[path] = language
        if language == "python":
            production[path] = module_from_python_path(path)
        elif language == "java":
            production[path] = java_type_from_path(path)
        else:
            production[path] = path

    test_files = [
        normalize_relative_path(raw)
        for raw in relative_paths
        if is_test_like(normalize_relative_path(raw))
    ]
    unsupported = sorted(
        {
            language
            for path in test_files
            if (language := unsupported_language_for_path(path)) is not None
        }
    )
    generated_tests = sum(1 for item in tests if item.generated)
    framework_counts = _framework_counts(tests)

    if not production:
        return AssociationMetric(
            status=MetricStatusName.NOT_APPLICABLE,
            associated=0,
            eligible=0,
            full_scope_status=CoverageScope.NOT_APPLICABLE,
            reason="no_eligible_production_units",
            formula_version=ASSOCIATION_FORMULA_VERSION,
            framework_counts=framework_counts,
            unsupported_frameworks=tuple(item for item in unsupported if item),
            generated_tests=generated_tests,
        )

    by_path: dict[str, list[TestDeclaration]] = defaultdict(list)
    for item in tests:
        by_path[item.path].append(item)

    associations: list[AssociationRecord] = []
    associated_units: set[str] = set()

    for test_path in test_files:
        language = language_for_path(test_path)
        text = file_texts.get(test_path, "")
        test_ids = tuple(item.test_id for item in by_path.get(test_path, ()))
        primary_test_id = test_ids[0] if test_ids else None
        generated = is_generated_path(test_path) or any(
            item.generated for item in by_path.get(test_path, ())
        )
        referenced = _direct_references(
            test_path=test_path,
            language=language,
            text=text,
            production=production,
            production_language=production_language,
        )
        if generated:
            for prod in referenced:
                associations.append(
                    _record(
                        prod,
                        test_path,
                        primary_test_id,
                        AssociationMethod.GENERATED,
                        AssociationConfidence.NONE,
                        "generated_test",
                    )
                )
            notes.append(f"generated_tests:{test_path}")
            continue
        if referenced:
            for prod in referenced:
                associations.append(
                    _record(
                        prod,
                        test_path,
                        primary_test_id,
                        AssociationMethod.IMPORT_REFERENCE,
                        AssociationConfidence.HIGH,
                        f"import:{prod}",
                    )
                )
                associated_units.add(prod)
            continue
        stems = convention_stems(test_path, language or "")
        stem_keys = {item.lower() for item in stems}
        matches = [
            path
            for path, lang in production_language.items()
            if (
                (language is None or lang == language)
                and (
                    production_stem(path) in stems
                    or production_stem(path).lower() in stem_keys
                )
            )
        ]
        if len(matches) == 1:
            prod = matches[0]
            associations.append(
                _record(
                    prod,
                    test_path,
                    primary_test_id,
                    AssociationMethod.NAMING_CONVENTION,
                    AssociationConfidence.MEDIUM,
                    f"convention:{PurePosixPath(test_path).name}",
                )
            )
            associated_units.add(prod)
        elif len(matches) > 1:
            for prod in sorted(matches):
                associations.append(
                    _record(
                        prod,
                        test_path,
                        primary_test_id,
                        AssociationMethod.AMBIGUOUS,
                        AssociationConfidence.LOW,
                        f"ambiguous:{','.join(sorted(matches))}",
                    )
                )
            notes.append(f"ambiguous_association:{test_path}")

    if unsupported:
        notes.append("unsupported_framework_unknown_scope")
        for language in unsupported:
            if language:
                notes.append(f"unsupported_framework:{language}")

    eligible = len(production)
    associated = len(associated_units)
    unassociated = tuple(sorted(path for path in production if path not in associated_units))
    serialized = f"{associated / eligible:.6f}"
    unknown_scope = bool(unsupported) or generated_tests > 0
    if unknown_scope:
        status = MetricStatusName.UNKNOWN
        scope = CoverageScope.UNKNOWN
        reason = (
            "unsupported_framework_unknown_scope"
            if unsupported
            else "generated_tests_unknown_scope"
        )
    else:
        status = MetricStatusName.VALUE
        scope = CoverageScope.COMPLETE
        reason = "static_association_not_runtime_coverage"

    associations.sort(key=lambda item: item.association_id)
    return AssociationMetric(
        status=status,
        associated=associated,
        eligible=eligible,
        serialized=serialized,
        full_scope_status=scope,
        reason=reason,
        formula_version=ASSOCIATION_FORMULA_VERSION,
        runtime_coverage=None,
        framework_counts=framework_counts,
        associations=tuple(associations),
        unassociated=unassociated,
        unsupported_frameworks=tuple(item for item in unsupported if item),
        generated_tests=generated_tests,
    )


def _direct_references(
    *,
    test_path: str,
    language: str | None,
    text: str,
    production: Mapping[str, str],
    production_language: Mapping[str, str],
) -> tuple[str, ...]:
    found: list[str] = []
    if language == "python":
        for module in _python_imports(text):
            matched = _match_python_module(module, production)
            if matched:
                found.append(matched)
    elif language == "java":
        for imported in _JAVA_IMPORT.findall(text):
            matched = _match_java_type(imported, production)
            if matched:
                found.append(matched)
    elif language in {"javascript", "typescript"}:
        production_paths = set(production)
        for specifier in _js_specifiers(text):
            for candidate in _js_candidates(test_path, specifier):
                normalized = normalize_relative_path(candidate)
                if normalized in production_paths:
                    found.append(normalized)
                    break
                for extra in (normalized + ".js", normalized + ".ts", normalized + ".tsx"):
                    if extra in production_paths:
                        found.append(extra)
                        break
    return tuple(dict.fromkeys(found))


def _framework_counts(tests: Sequence[TestDeclaration]) -> tuple[FrameworkCount, ...]:
    counts: dict[str, int] = defaultdict(int)
    for item in tests:
        if item.unsupported_framework:
            continue
        counts[item.framework] += 1
    return tuple(
        FrameworkCount(framework=name, count=counts[name]) for name in sorted(counts)
    )


def _record(
    production_path: str,
    test_path: str,
    test_id: str | None,
    method: AssociationMethod,
    confidence: AssociationConfidence,
    witness: str,
) -> AssociationRecord:
    return AssociationRecord(
        association_id=f"assoc:{production_path}:{test_path}:{method.value}",
        production_path=production_path,
        test_path=test_path,
        test_id=test_id,
        method=method,
        confidence=confidence,
        witness=witness,
        formula_version=ASSOCIATION_FORMULA_VERSION,
    )


__all__ = ["collect_association_metric"]
