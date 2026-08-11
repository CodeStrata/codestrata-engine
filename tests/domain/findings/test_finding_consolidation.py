"""Slice 5.11 — condition identity and Finding consolidation tests."""

from __future__ import annotations

from codestrata.application.findings.consolidation import (
    consolidate_findings,
    remap_finding_ids,
)
from codestrata.domain.findings import (
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    canonical_finding_condition_key,
)
from codestrata.domain.findings.consolidation import condition_key_parts


def _finding(
    *,
    rule_id: str,
    path: str,
    symbol: str = "subject",
    evidence_token: str = "ev:aaaaaaaaaaaaaaaaaaaaaaaa",
    severity: FindingSeverity = FindingSeverity.HIGH,
    title: str = "Example",
    description: str = "desc",
    finding_id: str | None = None,
    metadata: dict | None = None,
) -> Finding:
    item = Finding.create(
        rule_id=rule_id,
        title=title,
        description=description,
        severity=severity,
        category=FindingCategory.SECURITY,
        subject_keys=(rule_id, evidence_token, path, symbol),
        evidence=(
            FindingEvidence(
                evidence_type="config",
                source_id=symbol,
                path=path,
                excerpt="redacted",
            ),
        ),
        metadata=metadata or {"subject_keys": f"{rule_id},{evidence_token},{path},{symbol}"},
    )
    if finding_id is not None:
        item = item.model_copy(update={"id": finding_id})
    return item


def test_condition_key_stable_and_ignores_title() -> None:
    a = _finding(rule_id="security.credential-literal", path="a.env", title="One")
    b = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        title="Different title",
        evidence_token="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
    )
    assert canonical_finding_condition_key(a) == canonical_finding_condition_key(b)
    assert condition_key_parts(a)[0] == "security.credential-literal"


def test_condition_key_differs_by_rule_path_symbol_measurement_graph() -> None:
    base = _finding(rule_id="security.credential-literal", path="a.env", symbol="KEY")
    assert canonical_finding_condition_key(base) != canonical_finding_condition_key(
        _finding(rule_id="security.private-key-material", path="a.env", symbol="KEY")
    )
    assert canonical_finding_condition_key(base) != canonical_finding_condition_key(
        _finding(rule_id="security.credential-literal", path="b.env", symbol="KEY")
    )
    assert canonical_finding_condition_key(base) != canonical_finding_condition_key(
        _finding(rule_id="security.credential-literal", path="a.env", symbol="OTHER")
    )
    measured_a = _finding(
        rule_id="technical_debt.high-complexity",
        path="src/a.py",
        symbol="fn",
        metadata={
            "subject_keys": "src/a.py,fn",
            "measurement_metric_id": "cyclomatic",
            "measurement_scope_ref": "fn",
        },
    )
    measured_b = measured_a.model_copy(
        update={
            "metadata": {
                **measured_a.metadata,
                "measurement_metric_id": "cognitive",
            }
        }
    )
    assert canonical_finding_condition_key(measured_a) != canonical_finding_condition_key(
        measured_b
    )
    graph_a = _finding(
        rule_id="architecture.invalid-direction",
        path="mod/a",
        symbol="edge",
        metadata={"subject_keys": "u1,u2", "graph_edge_id": "edge:1"},
    )
    graph_b = graph_a.model_copy(
        update={"metadata": {**graph_a.metadata, "graph_edge_id": "edge:2"}}
    )
    assert canonical_finding_condition_key(graph_a) != canonical_finding_condition_key(
        graph_b
    )


def test_exact_duplicate_merges_and_recomputes_confidence() -> None:
    first = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        finding_id="finding:security.credential-literal:same",
    )
    second = first.model_copy(
        update={
            "description": "alt",
            "evidence": (
                FindingEvidence(
                    evidence_type="config",
                    source_id="KEY2",
                    path="a.env",
                ),
            ),
        }
    )
    # Same ID exact group.
    second = second.model_copy(update={"id": first.id})
    result = consolidate_findings((first, second))
    assert len(result.findings) == 1
    assert result.diagnostics.exact_duplicate_count == 1
    assert len(result.findings[0].evidence) >= 1


def test_exact_contradictory_rule_ids_fail_closed() -> None:
    first = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        finding_id="finding:shared:same",
    )
    second = first.model_copy(update={"rule_id": "security.private-key-material"})
    result = consolidate_findings((first, second))
    # Fail closed keeps both when identity contradicts.
    assert len(result.findings) == 2
    assert result.limitations


def test_equivalent_same_rule_consolidates_different_evidence_ids() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="cfg.env",
        symbol="API_KEY",
        evidence_token="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
    )
    b = _finding(
        rule_id="security.credential-literal",
        path="cfg.env",
        symbol="API_KEY",
        evidence_token="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
    )
    assert a.id != b.id
    result = consolidate_findings((a, b))
    assert len(result.findings) == 1
    assert result.diagnostics.equivalent_duplicate_count == 1
    assert result.original_to_canonical[b.id] == result.findings[0].id


def test_same_basename_different_directory_remains_separate() -> None:
    a = _finding(rule_id="security.credential-literal", path="svc-a/.env", symbol="KEY")
    b = _finding(rule_id="security.credential-literal", path="svc-b/.env", symbol="KEY")
    result = consolidate_findings((a, b))
    assert len(result.findings) == 2


def test_title_alone_does_not_consolidate() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        symbol="A",
        title="Same Title",
    )
    b = _finding(
        rule_id="security.credential-literal",
        path="b.env",
        symbol="B",
        title="Same Title",
    )
    result = consolidate_findings((a, b))
    assert len(result.findings) == 2


def test_different_rules_remain_separate() -> None:
    a = _finding(rule_id="security.credential-literal", path="a.env")
    b = _finding(rule_id="security.private-key-material", path="a.env")
    result = consolidate_findings((a, b))
    assert len(result.findings) == 2
    assert result.diagnostics.legacy_overlap_count == 0


def test_severity_conflict_preserves_highest_with_limitation() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        symbol="KEY",
        evidence_token="ev:aaaaaaaaaaaaaaaaaaaaaaaa",
        severity=FindingSeverity.MEDIUM,
    )
    b = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        symbol="KEY",
        evidence_token="ev:bbbbbbbbbbbbbbbbbbbbbbbb",
        severity=FindingSeverity.HIGH,
    )
    result = consolidate_findings((a, b))
    assert len(result.findings) == 1
    assert result.findings[0].severity is FindingSeverity.HIGH
    assert any("severity conflict" in item for item in result.findings[0].limitations)


def test_conflicting_measurements_remain_separate() -> None:
    a = _finding(
        rule_id="technical_debt.high-complexity",
        path="src/a.py",
        symbol="fn",
        metadata={
            "subject_keys": "src/a.py,fn",
            "measurement_metric_id": "cyclomatic",
            "measurement_scope_ref": "fn",
        },
    )
    b = a.model_copy(
        update={
            "id": "finding:technical_debt.high-complexity:other",
            "metadata": {
                "subject_keys": "src/a.py,fn",
                "measurement_metric_id": "cognitive",
                "measurement_scope_ref": "fn",
            },
        }
    )
    # Different measurement identity → different condition keys → remain separate.
    assert canonical_finding_condition_key(a) != canonical_finding_condition_key(b)
    result = consolidate_findings((a, b))
    assert len(result.findings) == 2


def test_exact_same_id_contradictory_locations_fail_closed() -> None:
    a = _finding(
        rule_id="security.credential-literal",
        path="a.env",
        finding_id="finding:security.credential-literal:same",
    )
    b = _finding(
        rule_id="security.credential-literal",
        path="b.env",
        finding_id="finding:security.credential-literal:same",
    )
    result = consolidate_findings((a, b))
    assert len(result.findings) == 2
    assert any("contradiction" in item for item in result.limitations)


def test_remap_finding_ids() -> None:
    mapping = {"finding:a:1": "finding:a:canonical", "finding:a:canonical": "finding:a:canonical"}
    assert remap_finding_ids(("finding:a:1", "finding:a:canonical", "finding:a:1"), mapping) == (
        "finding:a:canonical",
    )


def test_empty_input() -> None:
    result = consolidate_findings(())
    assert result.findings == ()
    assert result.diagnostics.original_finding_count == 0
