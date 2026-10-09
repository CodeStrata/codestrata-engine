"""M14 fixtures: SPDX license metadata and configured allow/deny (E06.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from codestrata.application.evidence.supply_chain.consumer import consume_envelope
from codestrata.application.evidence.supply_chain.envelope import SupplyChainEnvelope
from codestrata.application.evidence.supply_chain.licenses import parse_spdx_expression
from codestrata.application.evidence.supply_chain.models import (
    LicenseDecision,
    LicenseExpressionStatus,
    LicensePolicy,
    LicenseRecord,
    SupplyChainEvidence,
)
from codestrata.application.evidence.supply_chain.service import SupplyChainEvidenceService
from codestrata.application.rules.security.rules import LicenseDisallowedRule
from codestrata.application.rules.security.yaml_catalog import (
    LICENSE_DISALLOWED_RULE_ID,
    catalog_digests,
    load_license_disallowed_rule,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity

EVAL = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
POLICY = LicensePolicy(version="1.0.0", allow=("MIT", "Apache-2.0"), deny=("GPL-3.0-only",))


def _run(
    paths: tuple[str, ...],
    texts: dict[str, str],
    *,
    policy: LicensePolicy | None = POLICY,
    overlay: tuple[LicenseRecord, ...] = (),
) -> tuple[SupplyChainEvidence, SupplyChainEnvelope]:
    return SupplyChainEvidenceService().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        evaluation_time=EVAL,
        snapshot_payload={
            "provider_id": "osv.dev",
            "published_at": "2026-09-12T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
            "license": "CC-BY-4.0",
            "advisories": [],
        },
        catalog_digest=catalog_digests()[LICENSE_DISALLOWED_RULE_ID],
        license_policy=policy,
        license_overlay=overlay,
    )


def _composer(packages: list[dict[str, object]]) -> str:
    import json

    return json.dumps({"packages": packages})


def test_allowed_denied_and_absent_policy_is_metadata_only() -> None:
    lock = _composer(
        [
            {"name": "vendor/mit", "version": "1.0.0", "license": ["MIT"]},
            {"name": "vendor/gpl", "version": "1.0.0", "license": ["GPL-3.0-only"]},
        ]
    )
    evidence, envelope = _run(("composer.lock",), {"composer.lock": lock})
    by_name = {item.package_name: item for item in evidence.licenses}
    assert by_name["vendor/mit"].decision is LicenseDecision.ALLOWED
    assert by_name["vendor/gpl"].decision is LicenseDecision.DISALLOWED
    assert by_name["vendor/gpl"].decision_rule == "configured_deny"
    assert evidence.license_summary.legal_compliance_verdict is False
    rule = LicenseDisallowedRule()
    matched = rule.evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("php",)),
            assessment_graph=evidence,
        )
    )
    assert matched.status is RuleResultStatus.MATCHED
    assert matched.matches[0].severity is RuleSeverity.MEDIUM
    assert "legal compliance" in matched.matches[0].summary.lower()
    consume_envelope(envelope.model_dump(mode="json"))
    missing_policy, _ = _run(("composer.lock",), {"composer.lock": lock}, policy=None)
    assert all(item.decision is LicenseDecision.METADATA_ONLY for item in missing_policy.licenses)
    absent = rule.evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("php",)),
            assessment_graph=missing_policy,
        )
    )
    assert absent.status is RuleResultStatus.NOT_MATCHED


def test_dual_license_or_is_allowed_when_one_option_is_allowed() -> None:
    lock = _composer(
        [
            {
                "name": "vendor/dual",
                "version": "2.0.0",
                "license": "MIT OR GPL-3.0-only",
            }
        ]
    )
    evidence, _ = _run(("composer.lock",), {"composer.lock": lock})
    record = evidence.licenses[0]
    assert record.expression_status is LicenseExpressionStatus.SPDX
    assert record.decision is LicenseDecision.ALLOWED
    tree, status, ids = parse_spdx_expression("MIT OR Apache-2.0")
    assert status is LicenseExpressionStatus.SPDX
    assert set(ids) == {"MIT", "Apache-2.0"}
    assert tree is not None


def test_malformed_missing_and_unsupported_are_unknown() -> None:
    lock = _composer(
        [
            {"name": "vendor/bad", "version": "1.0.0", "license": ["MIT/Apache"]},
            {"name": "vendor/none", "version": "1.0.0"},
            {"name": "vendor/custom", "version": "1.0.0", "license": ["Proprietary"]},
        ]
    )
    evidence, _ = _run(("composer.lock",), {"composer.lock": lock})
    by_name = {item.package_name: item for item in evidence.licenses}
    assert by_name["vendor/bad"].expression_status is LicenseExpressionStatus.MALFORMED
    assert by_name["vendor/bad"].decision is LicenseDecision.UNKNOWN
    assert by_name["vendor/none"].expression_status is LicenseExpressionStatus.MISSING
    assert by_name["vendor/none"].decision is LicenseDecision.UNKNOWN
    assert by_name["vendor/custom"].expression_status is LicenseExpressionStatus.UNSUPPORTED
    assert by_name["vendor/custom"].decision is LicenseDecision.UNKNOWN
    rule = LicenseDisallowedRule().evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("php",)),
            assessment_graph=evidence,
        )
    )
    assert rule.status is RuleResultStatus.NOT_MATCHED


def test_conflicting_metadata_is_unknown() -> None:
    lock = _composer([{"name": "vendor/conflict", "version": "1.0.0", "license": ["MIT"]}])
    overlay = (
        LicenseRecord(
            license_id="overlay",
            ecosystem="composer",
            package_name="vendor/conflict",
            resolved_version="1.0.0",
            lock_path="NOTICE",
            raw_expression="GPL-3.0-only",
            normalized_expression="GPL-3.0-only",
            expression_status=LicenseExpressionStatus.SPDX,
            decision=LicenseDecision.UNKNOWN,
            decision_rule="overlay",
            license_source="NOTICE",
        ),
    )
    evidence, _ = _run(("composer.lock",), {"composer.lock": lock}, overlay=overlay)
    assert len(evidence.licenses) == 1
    assert evidence.licenses[0].expression_status is LicenseExpressionStatus.CONFLICT
    assert evidence.licenses[0].decision is LicenseDecision.UNKNOWN
    assert evidence.license_summary.conflicting == 1


def test_and_expression_denied_if_any_conjunct_denied() -> None:
    lock = _composer(
        [
            {
                "name": "vendor/and",
                "version": "1.0.0",
                "license": "MIT AND GPL-3.0-only",
            }
        ]
    )
    evidence, _ = _run(("composer.lock",), {"composer.lock": lock})
    assert evidence.licenses[0].decision is LicenseDecision.DISALLOWED


def test_yaml_rule_and_catalog() -> None:
    loaded = load_license_disallowed_rule()
    assert loaded["rule_id"] == LICENSE_DISALLOWED_RULE_ID
    assert loaded["measurement"] == "M14"
    assert loaded["default_severity"] is RuleSeverity.MEDIUM
    assert LICENSE_DISALLOWED_RULE_ID in catalog_digests()


def test_deterministic_license_repeat() -> None:
    lock = _composer([{"name": "vendor/mit", "version": "1.0.0", "license": ["MIT"]}])
    files = {"composer.lock": lock}
    first, env1 = _run(("composer.lock",), files)
    second, env2 = _run(("composer.lock",), files)
    third, env3 = _run(("composer.lock",), files)
    assert env1.body_digest == env2.body_digest == env3.body_digest
    assert first.license_summary.known_spdx == 1
    assert "license_not_legal_compliance" in env1.body.limitations
