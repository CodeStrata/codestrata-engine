"""E01.2 descriptors, envelopes, identity, hotspot and aggregation contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from codestrata.domain.contracts.aggregation import SubjectEvaluation, aggregate_family
from codestrata.domain.contracts.catalog import PACKAGE_REVISION, load_launch_ratification
from codestrata.domain.contracts.descriptors import launch_descriptors
from codestrata.domain.contracts.driver_manifest import (
    build_outcome_driver_manifest,
    dump_outcome_driver_yaml,
    outcome_driver_manifest_digest,
)
from codestrata.domain.contracts.enums import (
    ContributorRole,
    HotspotListKind,
    ResultStatus,
    SeverityOverrideSource,
)
from codestrata.domain.contracts.envelope import EnvelopeError, parse_envelope
from codestrata.domain.contracts.examples import EXAMPLE_BUILDERS
from codestrata.domain.contracts.facts import FindingRecord
from codestrata.domain.contracts.hotspot import EngineeringHotspot
from codestrata.domain.contracts.identity_map import (
    IDENTITY_MAP,
    canonical_finding_id,
    file_subject_id,
    published_identity_map,
    repository_subject_id,
)
from codestrata.domain.contracts.serialization import (
    digest_canonical,
    dumps_canonical,
    require_supported_major,
)
from codestrata.domain.contracts.severity_contract import (
    ContextSeverityDefault,
    SeverityOverride,
    VersionedSeverityBinding,
    apply_context_default,
    rewrite_after_override_rejected,
)
from codestrata.domain.findings.enums import FindingSeverity

ENGINE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e01.2"
SCHEMA_DIR = ENGINE_ROOT / "schemas" / "contracts" / "codestrata.io" / "v1.2"
DOCS_MANIFEST = ENGINE_ROOT / "docs" / "contracts" / "outcome-driver-manifest-v1.yaml"


def test_descriptors_declare_required_surfaces() -> None:
    descriptors = launch_descriptors()
    assert {item.family for item in descriptors} == {
        "inventory",
        "architecture",
        "security",
        "quality",
        "maintainability",
    }
    ratification = load_launch_ratification()
    for item in descriptors:
        dumped = item.model_dump(mode="json")
        assert dumped["reads"]
        assert dumped["emits"]
        assert dumped["applicability"]
        assert dumped["depth"]
        assert dumped["schemas"]
        assert dumped["budgets"]["yaml_aliases_enabled"] is False
        assert dumped["budgets"]["rule_hard_deadline_seconds"] == (
            ratification.budgets.rule_hard_deadline_seconds
        )
        assert dumped["network"]["mode"] == "offline"
        assert dumped["network"]["silent_online_fallback"] is False
        assert dumped["coverage"]["required_capability_ids"]
        assert dumped["failures"]
        assert dumped["no_opaque_score"] is True
        failure_codes = {entry["code"] for entry in dumped["failures"]}
        assert "budget_exceeded" in failure_codes
        assert "unsupported_major_version" in failure_codes


def test_outcome_driver_manifest_consumes_e01_1() -> None:
    manifest = build_outcome_driver_manifest()
    ratification = load_launch_ratification()
    assert manifest.package_revision == PACKAGE_REVISION
    assert manifest.no_opaque_score is True
    assert manifest.drivers == ratification.outcome_drivers
    for driver in manifest.drivers:
        assert driver.id
        assert driver.family
        assert driver.outcome_or_context_role
        assert driver.applicability
        assert driver.direction
        assert driver.comparison_unit
        assert driver.epsilon
        assert driver.coverage_requirement
        assert driver.empty_scope
    hotspot = next(item for item in manifest.drivers if item.id == "M22.hotspot")
    assert hotspot.contributor_role is ContributorRole.RANKING
    published = yaml.safe_load(dump_outcome_driver_yaml())
    documented = yaml.safe_load(DOCS_MANIFEST.read_bytes())
    assert published == documented
    assert outcome_driver_manifest_digest() == digest_canonical(manifest.model_dump(mode="json"))


def test_identity_map_reuses_existing_forms() -> None:
    kinds = {item.kind.value for item in IDENTITY_MAP}
    assert {"repository", "file", "finding", "evidence"} <= kinds
    document = published_identity_map()
    assert document.package_revision == PACKAGE_REVISION
    assert document.mappings == IDENTITY_MAP
    repo = repository_subject_id("example-repo")
    assert repo == "repo:example-repo"
    assert file_subject_id("example-repo", "src/A.java").endswith(":file:src/A.java")
    finding = canonical_finding_id(
        "architecture.dependency-cycle",
        ("repo:example-repo:module:services/orders",),
        occurrence_key="symbol:Handler.handle",
    )
    assert finding.startswith("finding:architecture.dependency-cycle:")
    moved = canonical_finding_id(
        "architecture.dependency-cycle",
        ("repo:example-repo:module:services/orders",),
        occurrence_key="symbol:Handler.handle",
    )
    assert moved == finding
    with pytest.raises(ValueError, match="line number"):
        canonical_finding_id(
            "architecture.dependency-cycle",
            ("repo:example-repo:module:services/orders",),
            occurrence_key="12",
        )


def test_envelope_splits_operational_metadata() -> None:
    envelope = EXAMPLE_BUILDERS["complete"]()
    assert envelope.body_digest
    assert envelope.operational.run_id
    assert envelope.operational.generated_at
    body = envelope.body.model_dump(mode="json")
    assert "run_id" not in body
    assert "generated_at" not in body
    assert "signature" not in body
    assert body["health_score"] is None
    again = EXAMPLE_BUILDERS["complete"]()
    assert again.body_digest == envelope.body_digest


@pytest.mark.parametrize("name", ["complete", "partial", "unknown", "no-baseline"])
def test_example_envelopes_match_fixtures(name: str) -> None:
    envelope = EXAMPLE_BUILDERS[name]()
    expected = json.loads((FIXTURE_DIR / f"envelope-{name}.json").read_text(encoding="utf-8"))
    actual = json.loads(dumps_canonical(envelope.model_dump(mode="json")))
    assert actual == expected
    parsed = parse_envelope(expected)
    assert parsed.body_digest == envelope.body_digest
    if name == "complete":
        hotspot = envelope.body.hotspots[0]
        assert hotspot.list_kind is HotspotListKind.COMPLETE_COMPARABLE
        assert "formula_version=" in hotspot.priority_explanation
        assert envelope.body.ownership[0].scope.value == "repository"
        assert envelope.body.change_summary is not None
        assert envelope.body.change_summary.crossed_boundary_count == 1
    if name == "partial":
        assert envelope.body.coverage[0].execution_state.value == "partial"
        extra = [
            item for item in envelope.body.hotspots[0].contributors if item.name == "ownership"
        ]
        assert extra[0].role is ContributorRole.CONTEXT_ONLY
        assert extra[0].value is None
    if name == "unknown":
        assert envelope.body.coverage[0].coverage_ratio is None
        assert envelope.body.coverage[0].coverage_reason == "unknown_denominator"
        assert envelope.body.hotspots[0].list_kind is HotspotListKind.PARTIAL_OR_UNKNOWN
        summary = envelope.body.change_summary
        assert summary is not None
        assert summary.boundary_spread_status is ResultStatus.UNKNOWN
        assert summary.boundary_spread_count is None
    if name == "no-baseline":
        assert envelope.body.comparison.has_baseline is False
        assert envelope.body.comparison.reason_code == "no_baseline"


def test_unknown_fields_and_unsupported_major_reject() -> None:
    payload = EXAMPLE_BUILDERS["complete"]().model_dump(mode="json")
    payload["extra_field"] = "nope"
    with pytest.raises(EnvelopeError):
        parse_envelope(payload)
    payload = EXAMPLE_BUILDERS["complete"]().model_dump(mode="json")
    payload["schema_version"] = "2.0.0"
    with pytest.raises(EnvelopeError):
        parse_envelope(payload)
    with pytest.raises(ValueError, match="unsupported"):
        require_supported_major("2.0.0")
    tenant = EXAMPLE_BUILDERS["complete"]().model_dump(mode="json")
    tenant["body"]["tenant_id"] = "t-1"
    with pytest.raises(EnvelopeError):
        parse_envelope(tenant)


def test_aggregation_preserves_failures_and_required_scopes() -> None:
    violation = "finding:architecture.dependency-cycle:abcd"
    subjects = (
        SubjectEvaluation(
            subject_id="a",
            required_scope=True,
            result=ResultStatus.FAIL,
            finding_ids=(violation,),
        ),
        SubjectEvaluation(
            subject_id="b",
            required_scope=True,
            result=ResultStatus.UNKNOWN,
        ),
    )
    aggregate = aggregate_family("architecture", subjects, known_violation_ids=(violation,))
    assert aggregate.result is ResultStatus.FAIL
    assert aggregate.coverage == "partial"
    assert violation in aggregate.retained_finding_ids

    with pytest.raises(ValueError, match="cannot disappear"):
        aggregate_family(
            "architecture",
            (
                SubjectEvaluation(
                    subject_id="a",
                    required_scope=True,
                    result=ResultStatus.NOT_APPLICABLE,
                ),
            ),
        )
    with pytest.raises(ValueError, match="cannot disappear"):
        aggregate_family(
            "architecture",
            (
                SubjectEvaluation(
                    subject_id="a",
                    required_scope=True,
                    result=ResultStatus.PASS,
                ),
            ),
            known_violation_ids=(violation,),
        )
    empty = aggregate_family("quality", (), driver_set_empty_or_disabled=True)
    assert empty.result is ResultStatus.NOT_APPLICABLE


def test_severity_binding_freezes_approved_override() -> None:
    binding = VersionedSeverityBinding(
        rule_id="architecture.dependency-cycle",
        contract_version="1.0.0",
        default_severity=FindingSeverity.HIGH,
        context_defaults=(
            ContextSeverityDefault(
                contract_version="1.0.0",
                context_class="test",
                default_severity=FindingSeverity.LOW,
                basis="context_cap",
                notes="Versioned default only.",
            ),
        ),
        approved_override=None,
        effective_severity=FindingSeverity.HIGH,
    )
    capped = apply_context_default(binding, context_class="test")
    assert capped.effective_severity is FindingSeverity.LOW
    overridden = VersionedSeverityBinding(
        rule_id="architecture.dependency-cycle",
        contract_version="1.0.0",
        default_severity=FindingSeverity.HIGH,
        approved_override=SeverityOverride(
            source=SeverityOverrideSource.APPROVED_CONFIG,
            effective_severity=FindingSeverity.MEDIUM,
            provenance_id="config:override:1",
            approved=True,
        ),
        effective_severity=FindingSeverity.MEDIUM,
    )
    still = apply_context_default(overridden, context_class="test")
    assert still.effective_severity is FindingSeverity.MEDIUM
    with pytest.raises(ValueError, match="hidden rewrite"):
        rewrite_after_override_rejected(overridden, attempted_severity=FindingSeverity.LOW)


def test_hotspot_rejects_missing_as_zero_and_opaque_score() -> None:
    envelope = EXAMPLE_BUILDERS["complete"]()
    payload = envelope.body.hotspots[0].model_dump()
    payload["opaque_score"] = True
    with pytest.raises(ValidationError):
        EngineeringHotspot.model_validate(payload)
    payload = envelope.body.hotspots[0].model_dump()
    payload["contributors"][0]["value"] = None
    with pytest.raises(ValidationError):
        EngineeringHotspot.model_validate(payload)


def test_finding_evidence_references_must_exist() -> None:
    envelope = EXAMPLE_BUILDERS["complete"]().model_dump(mode="json")
    envelope["body"]["findings"][0]["evidence_ids"] = ["evidence:missing:deadbeef"]
    with pytest.raises(EnvelopeError):
        parse_envelope(envelope)
    with pytest.raises(ValidationError):
        FindingRecord(
            finding_id="finding:architecture.dependency-cycle:x",
            rule_id="architecture.dependency-cycle",
            subject_id="repo:example-repo:module:services/orders",
            result="fail",
            default_severity="high",
            effective_severity="high",
            confidence="high",
            evidence_ids=(),
        )


def test_published_json_schemas_exist() -> None:
    for name in (
        "AnalyzerDescriptor",
        "CanonicalEnvelope",
        "FactRecord",
        "EvidenceRecord",
        "GraphRecord",
        "EngineeringHotspot",
        "OwnershipConcentration",
        "ChangeSummary",
        "CapabilityCoverage",
        "OutcomeDriverManifest",
    ):
        path = SCHEMA_DIR / f"{name}.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert schema.get("required")


def test_negative_fixture_payloads_are_rejected() -> None:
    for name in (
        "invalid-unknown-field.json",
        "invalid-major-version.json",
        "invalid-tenant-body.json",
    ):
        payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
        with pytest.raises(EnvelopeError):
            parse_envelope(payload)
