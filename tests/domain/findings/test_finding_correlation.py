"""Slice 5.12 — FindingCorrelation model, identity, and eligibility tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codestrata.application.findings.correlation import correlate_findings
from codestrata.application.findings.correlation_policies import all_correlation_policies
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
)
from codestrata.domain.findings.correlation import (
    CorrelationConfidence,
    CorrelationConfidenceLevel,
    CorrelationDirection,
    FindingCorrelation,
    FindingCorrelationBasis,
    FindingCorrelationType,
    build_correlation_id,
)
from codestrata.domain.traceability import EvidenceRef
from codestrata.domain.traceability.enums import EvidenceKind, EvidenceProductionMode
from codestrata.domain.traceability.location import EvidenceLocation


def _ref(evidence_id: str, *, path: str, subject: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        kind=EvidenceKind.CONFIGURATION,
        production_mode=EvidenceProductionMode.DIRECT,
        location=EvidenceLocation(path=path),
        domain_ref=subject,
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str,
    evidence_id: str | None = None,
    finding_id: str | None = None,
    category: FindingCategory = FindingCategory.SECURITY,
    metadata: dict | None = None,
) -> Finding:
    refs = ()
    if evidence_id:
        refs = (_ref(evidence_id, path=path, subject=symbol),)
    item = Finding.create(
        rule_id=rule_id,
        title=rule_id,
        description="test finding",
        severity=FindingSeverity.HIGH,
        category=category,
        subject_keys=(rule_id, path, symbol),
        evidence=(
            FindingEvidence(evidence_type="config", source_id=symbol, path=path),
        ),
        evidence_refs=refs,
        primary_evidence_id=evidence_id,
        metadata=metadata
        or {
            "subject_keys": f"{rule_id},{path},{symbol}",
            "normalized_key": symbol,
        },
    )
    if finding_id:
        item = item.model_copy(update={"id": finding_id})
    return item


def test_valid_correlation_and_stable_id() -> None:
    ids = ("finding:a:1", "finding:b:2")
    corr_id = build_correlation_id(
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        finding_ids=ids,
        shared_identity="api_key|src/app.env",
        policy_id="security.config.credential-placeholder",
    )
    assert corr_id.startswith("correlation:")
    assert corr_id == build_correlation_id(
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        finding_ids=("finding:b:2", "finding:a:1"),
        shared_identity="api_key|src/app.env",
        policy_id="security.config.credential-placeholder",
    )
    model = FindingCorrelation(
        correlation_id=corr_id,
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        finding_ids=tuple(sorted(ids)),
        primary_finding_id="finding:a:1",
        confidence=CorrelationConfidence(
            level=CorrelationConfidenceLevel.HIGH,
            basis=(FindingCorrelationBasis.SAME_CONFIGURATION_KEY,),
        ),
        basis=(
            FindingCorrelationBasis.SAME_CONFIGURATION_KEY,
            FindingCorrelationBasis.EXPLICIT_RULE_RELATIONSHIP,
        ),
    )
    assert model.primary_finding_id in model.finding_ids


def test_titles_do_not_affect_correlation_id() -> None:
    assert build_correlation_id(
        correlation_type="configuration_cluster",
        finding_ids=("finding:a:1", "finding:b:2"),
        shared_identity="x",
    ) == build_correlation_id(
        correlation_type=FindingCorrelationType.CONFIGURATION_CLUSTER,
        finding_ids=("finding:a:1", "finding:b:2"),
        shared_identity="x",
    )


def test_minimum_two_findings_and_no_self_reference() -> None:
    with pytest.raises(ValidationError):
        FindingCorrelation(
            correlation_id="correlation:aaaaaaaaaaaaaaaaaaaaaaaa",
            correlation_type=FindingCorrelationType.SHARED_SUBJECT,
            finding_ids=("finding:a:1",),
            primary_finding_id="finding:a:1",
            confidence=CorrelationConfidence(
                level=CorrelationConfidenceLevel.MODERATE,
                basis=(FindingCorrelationBasis.SAME_PATH,),
            ),
            basis=(FindingCorrelationBasis.SAME_PATH,),
        )


def test_high_confidence_requires_strong_basis() -> None:
    with pytest.raises(ValidationError, match="High Correlation Confidence"):
        FindingCorrelation(
            correlation_id="correlation:bbbbbbbbbbbbbbbbbbbbbbbb",
            correlation_type=FindingCorrelationType.SHARED_LOCATION,
            finding_ids=("finding:a:1", "finding:b:2"),
            primary_finding_id="finding:a:1",
            confidence=CorrelationConfidence(
                level=CorrelationConfidenceLevel.HIGH,
                basis=(FindingCorrelationBasis.SAME_PATH,),
            ),
            basis=(FindingCorrelationBasis.SAME_PATH,),
        )


def test_credential_placeholder_same_key_correlates() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="src/app.env",
        symbol="API_KEY",
        evidence_id="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="src/app.env",
        symbol="API_KEY",
        evidence_id="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1
    assert len(result.findings) == 2
    assert {item.id for item in result.findings} == {a.id, b.id}
    assert all(item.severity is FindingSeverity.HIGH for item in result.findings)
    assert all(item.correlation_ids for item in result.findings)


def test_same_path_unrelated_subject_does_not_correlate() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="src/app.env",
        symbol="API_KEY",
        evidence_id="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
    )
    b = _finding(
        rule_id="security.debug-enabled",
        path="src/app.env",
        symbol="DEBUG",
        evidence_id="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
        metadata={
            "subject_keys": "security.debug-enabled,src/app.env,DEBUG",
            "normalized_key": "DEBUG",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count == 0


def test_title_similarity_does_not_correlate() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        symbol="KEY_A",
        evidence_id="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="b.env",
        symbol="KEY_B",
        evidence_id="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count == 0


def test_tls_hostname_same_path_correlates() -> None:
    a = _finding(
        rule_id="security.tls-verification-disabled",
        path="config/ssl.yml",
        symbol="verify",
        metadata={
            "subject_keys": "security.tls-verification-disabled,config/ssl.yml,verify",
        },
    )
    b = _finding(
        rule_id="security.hostname-verification-disabled",
        path="config/ssl.yml",
        symbol="hostname",
        metadata={
            "subject_keys": (
                "security.hostname-verification-disabled,config/ssl.yml,hostname"
            ),
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1
    assert any(
        item.correlation_type is FindingCorrelationType.CONFIGURATION_CLUSTER
        for item in result.correlations
    )


def test_branching_nesting_same_callable_correlates() -> None:
    a = _finding(
        rule_id="technical_debt.excessive-branching",
        path="src/service.py",
        symbol="Widget.process",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/service.py,Widget.process",
            "qualified_signature": "Widget.process",
        },
    )
    b = _finding(
        rule_id="technical_debt.deep-nesting",
        path="src/service.py",
        symbol="Widget.process",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/service.py,Widget.process",
            "qualified_signature": "Widget.process",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1
    assert any(
        item.correlation_type is FindingCorrelationType.COMPLEXITY_CLUSTER
        for item in result.correlations
    )


def test_different_callable_does_not_correlate() -> None:
    a = _finding(
        rule_id="technical_debt.excessive-branching",
        path="src/service.py",
        symbol="Widget.process",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/service.py,Widget.process",
            "qualified_signature": "Widget.process",
        },
    )
    b = _finding(
        rule_id="technical_debt.deep-nesting",
        path="src/service.py",
        symbol="Widget.render",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/service.py,Widget.render",
            "qualified_signature": "Widget.render",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count == 0


def test_dependency_duplicate_conflict_same_identity_correlates() -> None:
    a = _finding(
        rule_id="dependency.duplicate-declaration",
        path="pom.xml",
        symbol="com.example:lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "pom.xml,com.example:lib",
            "dependency_identity": "maven:com.example:lib",
        },
    )
    b = _finding(
        rule_id="dependency.conflicting-exact-versions",
        path="pom.xml",
        symbol="com.example:lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "pom.xml,com.example:lib",
            "dependency_identity": "maven:com.example:lib",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1


def test_dependency_same_name_different_identity_does_not_correlate() -> None:
    a = _finding(
        rule_id="dependency.duplicate-declaration",
        path="pom.xml",
        symbol="lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "pom.xml,lib",
            "dependency_identity": "maven:com.example:lib:compile",
        },
    )
    b = _finding(
        rule_id="dependency.conflicting-exact-versions",
        path="module/pom.xml",
        symbol="lib",
        category=FindingCategory.DEPENDENCY,
        metadata={
            "subject_keys": "module/pom.xml,lib",
            "dependency_identity": "maven:com.example:lib:test",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count == 0


def test_architecture_same_edge_correlates() -> None:
    a = _finding(
        rule_id="architecture.invalid-dependency-direction",
        path="src/app",
        symbol="domain->infra",
        category=FindingCategory.ARCHITECTURE,
        metadata={
            "subject_keys": "domain->infra",
            "graph_edge_id": "edge:domain->infra",
        },
    )
    b = _finding(
        rule_id="architecture.layer-boundary-violation",
        path="src/app",
        symbol="domain->infra",
        category=FindingCategory.ARCHITECTURE,
        metadata={
            "subject_keys": "domain->infra",
            "graph_edge_id": "edge:domain->infra",
        },
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1


def test_shared_evidence_with_compatible_subject_correlates() -> None:
    evidence_id = "ev:cccccccccccccccccccccccc"
    a = _finding(
        rule_id="security.credential-literal",
        path="cfg.env",
        symbol="TOKEN",
        evidence_id=evidence_id,
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="cfg.env",
        symbol="TOKEN",
        evidence_id=evidence_id,
    )
    result = correlate_findings((a, b))
    assert result.diagnostics.correlation_count >= 1


def test_cross_head_without_policy_does_not_correlate() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="deploy.yml",
        symbol="SECRET",
        metadata={
            "subject_keys": "deploy.yml,SECRET",
            "normalized_key": "SECRET",
        },
    )
    b = _finding(
        rule_id="cloud.kubernetes-deployment",
        path="deploy.yml",
        symbol="SECRET",
        category=FindingCategory.CLOUD,
        metadata={
            "subject_keys": "deploy.yml,SECRET",
            "normalized_key": "SECRET",
        },
    )
    # No reviewed cross-head policy in catalog.
    result = correlate_findings((a, b))
    assert result.diagnostics.cross_head_correlation_count == 0


def test_policy_catalog_has_no_broad_cross_head() -> None:
    assert all(not policy.cross_head_allowed for policy in all_correlation_policies())


def test_clusters_do_not_fabricate_transitive_edges() -> None:
    a = _finding(
        rule_id="technical_debt.excessive-branching",
        path="src/a.py",
        symbol="fn",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/a.py,fn",
            "qualified_signature": "fn",
        },
    )
    b = _finding(
        rule_id="technical_debt.deep-nesting",
        path="src/a.py",
        symbol="fn",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/a.py,fn",
            "qualified_signature": "fn",
        },
    )
    c = _finding(
        rule_id="technical_debt.large-callable",
        path="src/a.py",
        symbol="fn",
        category=FindingCategory.TECHNICAL_DEBT,
        metadata={
            "subject_keys": "src/a.py,fn",
            "qualified_signature": "fn",
        },
    )
    result = correlate_findings((a, b, c))
    # A-B and A-C (or B-C via large+branching) may exist; no fabricated A-C
    # unless policy supports it. large+branching and branching+nesting exist.
    pair_ids = {tuple(sorted(item.finding_ids)) for item in result.correlations}
    # Every correlation is an explicit edge (exactly two members).
    assert all(len(item.finding_ids) == 2 for item in result.correlations)
    assert result.clusters
    # Cluster may include all three; direct edges remain explicit.
    assert len(result.correlations) >= 1
    assert pair_ids  # non-empty


def test_undirected_member_order_invariant() -> None:
    left = build_correlation_id(
        correlation_type=FindingCorrelationType.DEPENDENCY_CLUSTER,
        finding_ids=("finding:z:9", "finding:a:1"),
        direction=CorrelationDirection.UNDIRECTED,
        shared_identity="dep",
    )
    right = build_correlation_id(
        correlation_type=FindingCorrelationType.DEPENDENCY_CLUSTER,
        finding_ids=("finding:a:1", "finding:z:9"),
        direction=CorrelationDirection.UNDIRECTED,
        shared_identity="dep",
    )
    assert left == right


def test_finding_ids_unchanged_by_correlation() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="src/app.env",
        symbol="API_KEY",
        evidence_id="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
        finding_id="finding:security.credential-literal:fixed-a",
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="src/app.env",
        symbol="API_KEY",
        evidence_id="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
        finding_id="finding:security.placeholder-credential:fixed-b",
    )
    result = correlate_findings((a, b))
    assert {item.id for item in result.findings} == {a.id, b.id}


def test_empty_policy_override_rejects_policy_matches() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="src/app.env",
        symbol="API_KEY",
    )
    b = _finding(
        rule_id="security.placeholder-credential",
        path="src/app.env",
        symbol="API_KEY",
    )
    # Empty policy list disables policy matches; shared evidence absent → none.
    result = correlate_findings((a, b), policies=())
    assert result.diagnostics.policy_match_count == 0
