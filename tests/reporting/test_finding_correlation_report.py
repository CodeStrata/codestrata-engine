"""Slice 5.12 — report serialization and correlation-aware recommendations."""

from __future__ import annotations

from codestrata.application.findings.correlation import correlate_findings
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
)
from types import SimpleNamespace

from codestrata.domain.recommendations.enums import RecommendationCategory
from codestrata.services.recommendations.providers.builtin import (
    CorrelationAwareDependencyNormalizationRecommendation,
    CorrelationAwareTransportVerificationRecommendation,
)


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
    category: FindingCategory = FindingCategory.SECURITY,
    metadata: dict | None = None,
) -> Finding:
    return Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description="test",
        severity=FindingSeverity.HIGH,
        category=category,
        subject_keys=(rule_id, path, symbol),
        evidence=(
            FindingEvidence(evidence_type="config", source_id=symbol, path=path),
        ),
        metadata=metadata
        or {
            "subject_keys": f"{rule_id},{path},{symbol}",
            "normalized_key": symbol,
        },
    )


def test_transport_provider_emits_one_recommendation() -> None:
    a = _finding(
        rule_id="security.tls-verification-disabled",
        path="ssl.yml",
        symbol="verify",
        metadata={"subject_keys": "ssl.yml,verify"},
    )
    b = _finding(
        rule_id="security.hostname-verification-disabled",
        path="ssl.yml",
        symbol="hostname",
        metadata={"subject_keys": "ssl.yml,hostname"},
    )
    result = correlate_findings((a, b))
    findings = result.findings
    context = SimpleNamespace(findings=findings)
    provider = CorrelationAwareTransportVerificationRecommendation()
    emitted = []
    for item in findings:
        if item.rule_id in provider.supported_finding_rule_ids():
            emitted.extend(provider.recommend(item, context))  # type: ignore[arg-type]
    assert len(emitted) == 1
    rec = emitted[0]
    assert set(rec.supporting_finding_ids) == {item.id for item in findings}
    assert rec.metadata.get("correlation_aware") == "true"


def test_dependency_provider_emits_one_recommendation() -> None:
    a = _finding(
        rule_id="dependency.duplicate-declaration",
        path="pom.xml",
        symbol="lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "pom.xml,lib",
            "dependency_identity": "maven:com.example:lib",
        },
    )
    b = _finding(
        rule_id="dependency.conflicting-exact-versions",
        path="pom.xml",
        symbol="lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "pom.xml,lib",
            "dependency_identity": "maven:com.example:lib",
        },
    )
    result = correlate_findings((a, b))
    findings = result.findings
    context = SimpleNamespace(findings=findings)
    provider = CorrelationAwareDependencyNormalizationRecommendation()
    emitted = []
    for item in findings:
        if item.rule_id in provider.supported_finding_rule_ids():
            emitted.extend(provider.recommend(item, context))  # type: ignore[arg-type]
    assert len(emitted) == 1
    assert emitted[0].category is RecommendationCategory.DEPENDENCY


def test_no_automatic_recommendation_for_every_correlation() -> None:
    a = _finding(
        rule_id="technical_debt.excessive-branching",
        path="a.py",
        symbol="fn",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "a.py,fn",
            "qualified_signature": "fn",
        },
    )
    b = _finding(
        rule_id="technical_debt.deep-nesting",
        path="a.py",
        symbol="fn",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "a.py,fn",
            "qualified_signature": "fn",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1
    context = SimpleNamespace(findings=result.findings)
    transport = CorrelationAwareTransportVerificationRecommendation()
    dependency = CorrelationAwareDependencyNormalizationRecommendation()
    assert not any(
        transport.recommend(item, context) for item in result.findings  # type: ignore[arg-type]
    )
    assert not any(
        dependency.recommend(item, context) for item in result.findings  # type: ignore[arg-type]
    )


def test_finding_correlation_canonical_dict_is_safe() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="app.env",
        symbol="API_KEY",
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="app.env",
        symbol="API_KEY",
    )
    result = correlate_findings((a, b))
    assert result.correlations
    payload = result.correlations[0].canonical_dict()
    text = str(payload)
    assert "password" not in text.lower() or "API_KEY" in text
    assert "/tmp/" not in text
    assert "correlation_id" in payload
    assert "finding_ids" in payload
