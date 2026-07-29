"""Tests for static-analysis service orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.models import Repository, Technology
from codestrata.models.enums import FindingCategory, FindingSource, Severity, TechnologyCategory
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.static_analysis.exceptions import StaticAnalysisProviderError
from codestrata.static_analysis.models import (
    StaticAnalysisContext,
    StaticAnalysisResult,
    StaticAnalysisStatus,
)
from codestrata.static_analysis.service import StaticAnalysisService


class _StubProvider:
    def __init__(
        self,
        provider_id: str,
        *,
        available: bool = True,
        applicable: bool = True,
        result: StaticAnalysisResult | None = None,
        raise_error: bool = False,
    ) -> None:
        self._provider_id = provider_id
        self._available = available
        self._applicable = applicable
        self._result = result
        self._raise_error = raise_error

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return self._provider_id.upper()

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"Java"})

    def is_available(self) -> bool:
        return self._available

    def is_applicable(self, context: StaticAnalysisContext) -> bool:
        del context
        return self._applicable

    def analyze(self, context: StaticAnalysisContext) -> StaticAnalysisResult:
        del context
        if self._raise_error:
            raise RuntimeError("boom")
        assert self._result is not None
        return self._result


def _finding(rule_id: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        title=rule_id,
        description="desc",
        category=FindingCategory.MAINTAINABILITY,
        severity=Severity.MEDIUM,
        source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
        evidence=[Evidence(file_path="A.java", line_number=1)],
        metadata={"provider_id": "pmd", "external_rule_id": rule_id},
    )


def test_disabled_subsystem_returns_disabled_status(tmp_path: Path) -> None:
    service = StaticAnalysisService(providers=[], enabled=False)
    results, findings = service.analyze(
        repository=Repository(name="r", path=tmp_path, files=[]),
        technologies=[],
    )
    assert findings == []
    assert len(results) == 1
    assert results[0].status == StaticAnalysisStatus.DISABLED
    assert results[0].provider_name == "PMD"


def test_disabled_subsystem_with_providers_skips_execution(tmp_path: Path) -> None:
    provider = _StubProvider("pmd", available=True, raise_error=True)
    service = StaticAnalysisService(providers=[provider], enabled=False)
    results, findings = service.analyze(
        repository=Repository(name="r", path=tmp_path, files=["A.java"]),
        technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
    )
    assert findings == []
    assert results[0].status == StaticAnalysisStatus.DISABLED
    assert results[0].provider_id == "pmd"


def test_unavailable_provider_non_strict(tmp_path: Path) -> None:
    provider = _StubProvider("pmd", available=False)
    service = StaticAnalysisService(providers=[provider], enabled=True)
    results, findings = service.analyze(
        repository=Repository(name="r", path=tmp_path, files=["A.java"]),
        technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
    )
    assert findings == []
    assert results[0].status == StaticAnalysisStatus.UNAVAILABLE


def test_unavailable_provider_strict_mode(tmp_path: Path) -> None:
    provider = _StubProvider("pmd", available=False)
    service = StaticAnalysisService(
        providers=[provider],
        enabled=True,
        fail_on_provider_error=True,
    )
    with pytest.raises(StaticAnalysisProviderError):
        service.analyze(
            repository=Repository(name="r", path=tmp_path, files=["A.java"]),
            technologies=[
                Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
            ],
        )


def test_completed_provider_merges_findings(tmp_path: Path) -> None:
    result = StaticAnalysisResult(
        provider_id="pmd",
        provider_name="PMD",
        status=StaticAnalysisStatus.COMPLETED,
        findings=[_finding("PMD.JAVA.BESTPRACTICES.A")],
    )
    provider = _StubProvider("pmd", result=result)
    service = StaticAnalysisService(providers=[provider], enabled=True)
    results, findings = service.analyze(
        repository=Repository(name="r", path=tmp_path, files=["A.java"]),
        technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
    )
    assert results[0].status == StaticAnalysisStatus.COMPLETED
    assert len(findings) == 1


def test_non_applicable_provider_omitted(tmp_path: Path) -> None:
    provider = _StubProvider("pmd", applicable=False)
    service = StaticAnalysisService(providers=[provider], enabled=True)
    results, findings = service.analyze(
        repository=Repository(name="r", path=tmp_path, files=[]),
        technologies=[],
    )
    assert results == []
    assert findings == []
