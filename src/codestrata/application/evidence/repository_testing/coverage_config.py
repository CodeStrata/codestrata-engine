"""Coverage configuration and report-reference evidence (no percentages)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.repository_testing.discovery import (
    classify_coverage_config,
    normalize_relative_path,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    CoverageFactType,
    TestFrameworkFamily,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    make_coverage_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import CoverageFactEvidence


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_coverage_collector",
        extraction_method="coverage_path_scan",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _tool_for_path(path: str, text: str | None) -> TestFrameworkFamily | None:
    lower_name = PurePosixPath(path).name.lower()
    lower_text = (text or "").lower()
    if "jacoco" in lower_name or "jacoco" in lower_text:
        return TestFrameworkFamily.JACOCO
    if lower_name == ".coveragerc" or "coverage" in lower_name:
        return TestFrameworkFamily.COVERAGE_PY
    if "nyc" in lower_name or "istanbul" in lower_text:
        return TestFrameworkFamily.NYC if "nyc" in lower_name else TestFrameworkFamily.ISTANBUL
    if "coverlet" in lower_name or "coverlet" in lower_text:
        return TestFrameworkFamily.COVERLET
    if "cobertura" in lower_name:
        return TestFrameworkFamily.UNKNOWN
    if "lcov" in lower_name:
        return TestFrameworkFamily.UNKNOWN
    if lower_name.startswith("jest.config"):
        if text is None or "coverage" in lower_text:
            return TestFrameworkFamily.JEST
        return None
    return None


def collect_coverage_facts(
    paths: Sequence[str],
    *,
    file_texts: Mapping[str, str] | None = None,
    configuration_fingerprint: str = "",
) -> tuple[CoverageFactEvidence, ...]:
    """Create coverage configuration / report-reference facts (no percentages)."""

    texts = file_texts or {}
    results: list[CoverageFactEvidence] = []
    for raw in paths:
        path = normalize_relative_path(raw)
        if not path:
            continue
        fact_type = classify_coverage_config(path)
        text = texts.get(path)
        name = PurePosixPath(path).name.lower()

        # jest.config* only when coverage is mentioned (or unknown without text).
        if name.startswith("jest.config"):
            if text is not None and "coverage" not in text.lower():
                continue
            fact_type = CoverageFactType.COVERAGE_CONFIGURATION

        # Manifest-declared coverage tooling (JaCoCo / Coverlet / coverage.py).
        if fact_type is None and text is not None:
            lower_text = text.lower()
            if "jacoco" in lower_text:
                fact_type = CoverageFactType.COVERAGE_CONFIGURATION
            elif "coverlet" in lower_text:
                fact_type = CoverageFactType.COVERAGE_CONFIGURATION
            elif name in {"pyproject.toml", "setup.cfg", ".coveragerc"} and (
                "[tool.coverage" in lower_text
                or "coverage.run" in lower_text
                or "[coverage:" in lower_text
            ):
                fact_type = CoverageFactType.COVERAGE_CONFIGURATION

        if fact_type is None:
            continue

        tool = _tool_for_path(path, text)
        if name.startswith("jest.config") and tool is None:
            continue

        kind = fact_type.value
        detail = PurePosixPath(path).name
        results.append(
            CoverageFactEvidence(
                evidence_id=make_coverage_evidence_id(path=path, kind=kind),
                path=path,
                fact_type=fact_type,
                tool=tool if tool is not TestFrameworkFamily.UNKNOWN else None,
                detail=detail,
                provenance=_provenance(
                    path, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )
    by_id = {item.evidence_id: item for item in results}
    return tuple(sorted(by_id.values(), key=lambda item: item.evidence_id))
