"""Security hygiene rules tests (Phase 4.5.3)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.repository_sensitive.service import (
    RepositorySensitiveEvidenceService,
)
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.security.helpers import (
    authentication_disabled,
    debug_enabled,
    evidence_configuration,
    has_private_key_material,
    hostname_verification_disabled,
    is_literal_credential,
    is_placeholder_credential,
    permissive_cors_origin,
    tls_verification_disabled,
)
from codestrata.application.rules.security.pack import SecurityRulePack, security_rules
from codestrata.application.rules.security.registration import register_security_pack
from codestrata.application.rules.security.rules import (
    CredentialLiteralRule,
    DebugEnabledRule,
    PrivateKeyMaterialRule,
    TlsVerificationDisabledRule,
)
from codestrata.application.security.assessment.artifacts import (
    write_security_assessment_artifact,
)
from codestrata.application.security.assessment.assembler import SecurityAssessmentAssembler
from codestrata.config import load_settings
from codestrata.config.settings import RepositorySensitiveEvidenceSettings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ContentClassification,
    InspectionStatus,
    PlaceholderStatus,
    SensitiveArtifactKind,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
    ConfigurationFactEvidence,
    SensitiveArtifactEvidence,
)
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.security.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.security.ids import HYGIENE_RULE_IDS, PACK_ID
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _artifact(
    *,
    path: str,
    classifications: tuple[ContentClassification, ...],
    status: InspectionStatus = InspectionStatus.INSPECTED,
    kind: SensitiveArtifactKind = SensitiveArtifactKind.PRIVATE_KEY,
) -> SensitiveArtifactEvidence:
    return SensitiveArtifactEvidence(
        evidence_id=f"art:{path}",
        path=path,
        kind=kind,
        inspection_status=status,
        content_classifications=classifications,
        classification=SourceClassification.SOURCE,
        provenance=_prov(),
    )


def _fact(
    *,
    path: str,
    key: str,
    family: ConfigurationKeyFamily,
    value_kind: ValueKind = ValueKind.LITERAL,
    placeholder: PlaceholderStatus = PlaceholderStatus.NOT_APPLICABLE,
    is_empty: bool = False,
    literal_boolean: bool | None = None,
    is_wildcard: bool = False,
    redacted: str = "[REDACTED]",
    fingerprint: str = "abc",
    role: SourceClassification = SourceClassification.SOURCE,
) -> ConfigurationFactEvidence:
    return ConfigurationFactEvidence(
        evidence_id=f"cfg:{path}:{key}",
        path=path,
        classification=role,
        format=ConfigurationFormat.PROPERTIES,
        normalized_key=key,
        key_family=family,
        redacted_preview=redacted,
        value_fingerprint=fingerprint,
        value_length=8,
        value_kind=value_kind,
        placeholder_status=placeholder,
        is_empty=is_empty,
        literal_boolean=literal_boolean,
        is_wildcard_origin=is_wildcard,
        provenance=_prov(),
    )


def _bundle(
    *,
    artifacts: tuple[SensitiveArtifactEvidence, ...] = (),
    facts: tuple[ConfigurationFactEvidence, ...] = (),
) -> AggregatedRepositorySensitiveEvidence:
    return AggregatedRepositorySensitiveEvidence(
        repository_id="fixture",
        artifacts=artifacts,
        configuration_facts=facts,
        evidence_fingerprint="deadbeef",
    )


def _context(
    evidence: AggregatedRepositorySensitiveEvidence | None,
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("java",)),
        repository_sensitive_evidence=evidence,
    )


def test_pack_registration_and_catalog() -> None:
    registry = RuleRegistry()
    pack = register_security_pack(registry)
    assert pack.pack_id == PACK_ID
    assert len(security_rules()) == len(HYGIENE_RULE_IDS)
    assert registry.size == len(HYGIENE_RULE_IDS)


def test_private_key_rule_precision() -> None:
    rule = PrivateKeyMaterialRule()
    pem = _artifact(
        path="tls/server.key",
        classifications=(ContentClassification.PRIVATE_KEY_MATERIAL,),
    )
    openssh = _artifact(
        path="id_ed25519",
        classifications=(ContentClassification.PRIVATE_KEY_MATERIAL,),
        kind=SensitiveArtifactKind.SSH_PRIVATE_KEY,
    )
    cert = _artifact(
        path="tls/server.crt",
        classifications=(ContentClassification.PUBLIC_CERTIFICATE_MATERIAL,),
        kind=SensitiveArtifactKind.PUBLIC_CERTIFICATE,
    )
    filename_only = _artifact(
        path="server.key",
        classifications=(ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,),
    )
    binary = _artifact(
        path="store/app.jks",
        classifications=(ContentClassification.UNKNOWN,),
        status=InspectionStatus.UNSUPPORTED_BINARY,
        kind=SensitiveArtifactKind.KEYSTORE,
    )
    assert has_private_key_material(pem)
    assert has_private_key_material(openssh)
    assert not has_private_key_material(cert)
    assert not has_private_key_material(filename_only)
    assert not has_private_key_material(binary)

    result = rule.evaluate(
        _context(_bundle(artifacts=(pem, openssh, cert, filename_only, binary)))
    )
    assert result.matched
    assert len(result.matches) == 2
    payload = dumps_stable_json(
        {
            "summaries": [item.summary for item in result.matches],
            "attrs": [dict(item.evidence[0].attributes) for item in result.matches],
        }
    )
    assert "BEGIN PRIVATE KEY" not in payload
    assert "MIIE" not in payload


def test_credential_literal_and_placeholder_precision() -> None:
    literal = _fact(
        path="app.properties",
        key="db_password",
        family=ConfigurationKeyFamily.CREDENTIAL,
        value_kind=ValueKind.LITERAL,
    )
    token = _fact(
        path="app.properties",
        key="api_token",
        family=ConfigurationKeyFamily.SECRET,
        value_kind=ValueKind.LITERAL,
    )
    env_ref = _fact(
        path="app.properties",
        key="db_password",
        family=ConfigurationKeyFamily.CREDENTIAL,
        value_kind=ValueKind.ENVIRONMENT_REFERENCE,
        placeholder=PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
        redacted="${DB_PASS}",
    )
    empty = _fact(
        path="app.properties",
        key="db_password",
        family=ConfigurationKeyFamily.CREDENTIAL,
        value_kind=ValueKind.EMPTY,
        placeholder=PlaceholderStatus.EMPTY,
        is_empty=True,
        redacted="[empty]",
    )
    placeholder = _fact(
        path="app.properties",
        key="db_password",
        family=ConfigurationKeyFamily.CREDENTIAL,
        value_kind=ValueKind.PLACEHOLDER,
        placeholder=PlaceholderStatus.PLACEHOLDER_LITERAL,
        redacted="changeme",
    )
    assert is_literal_credential(literal)
    assert is_literal_credential(token)
    assert not is_literal_credential(env_ref)
    assert not is_literal_credential(empty)
    assert not is_literal_credential(placeholder)
    assert is_placeholder_credential(placeholder)

    ci_expr = _fact(
        path=".github/workflows/ci.yml",
        key="api_token",
        family=ConfigurationKeyFamily.SECRET,
        value_kind=ValueKind.ENVIRONMENT_REFERENCE,
        placeholder=PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
        redacted="${{ secrets.API_TOKEN }}",
    )
    assert not is_literal_credential(ci_expr)

    result = CredentialLiteralRule().evaluate(
        _context(_bundle(facts=(literal, token, env_ref, empty, placeholder, ci_expr)))
    )
    assert len(result.matches) == 2
    serialized = dumps_stable_json(
        {"m": [item.summary for item in result.matches]}
    )
    assert "super-secret" not in serialized
    for item in result.matches:
        assert item.severity.value == "high"
        assert "Context: Production source" in item.summary
        assert item.evidence[0].attributes.get("security_context") == "production"


def test_credential_literal_ci_expression_is_not_a_live_credential() -> None:
    from codestrata.domain.rules.enums import RuleResultStatus

    gha = _fact(
        path=".github/workflows/pr.yml",
        key="env_github_token",
        family=ConfigurationKeyFamily.SECRET,
        value_kind=ValueKind.ENVIRONMENT_REFERENCE,
        placeholder=PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
        redacted="${{ secrets.GITHUB_TOKEN }}",
    )
    # Even a mis-tagged literal kind must not fire when preview is a CI expression.
    gha_misclassified = _fact(
        path=".github/workflows/pr.yml",
        key="env_github_token",
        family=ConfigurationKeyFamily.SECRET,
        value_kind=ValueKind.LITERAL,
        redacted="${{ secrets.GITHUB_TOKEN }}",
    )
    assert not is_literal_credential(gha)
    assert not is_literal_credential(gha_misclassified)
    result = CredentialLiteralRule().evaluate(
        _context(_bundle(facts=(gha, gha_misclassified)))
    )
    assert result.status is RuleResultStatus.NOT_MATCHED
    assert result.matches == ()


def test_transport_auth_cors_debug_rules() -> None:
    tls_off = _fact(
        path="app.properties",
        key="verify_ssl",
        family=ConfigurationKeyFamily.TLS_VERIFICATION,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=False,
        redacted="false",
    )
    tls_on = _fact(
        path="app.properties",
        key="verify_ssl",
        family=ConfigurationKeyFamily.TLS_VERIFICATION,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=True,
        redacted="true",
    )
    host_off = _fact(
        path="app.properties",
        key="hostname_verification",
        family=ConfigurationKeyFamily.HOSTNAME_VERIFICATION,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=False,
        redacted="false",
    )
    auth_off = _fact(
        path="app.properties",
        key="authentication_enabled",
        family=ConfigurationKeyFamily.AUTHENTICATION,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=False,
        redacted="false",
    )
    cors_star = _fact(
        path="app.properties",
        key="cors_allowed_origins",
        family=ConfigurationKeyFamily.CORS_ORIGIN,
        value_kind=ValueKind.LITERAL,
        is_wildcard=True,
        redacted="*",
    )
    cors_ok = _fact(
        path="app.properties",
        key="cors_allowed_origins",
        family=ConfigurationKeyFamily.CORS_ORIGIN,
        value_kind=ValueKind.LITERAL,
        is_wildcard=False,
        redacted="https://example.com",
    )
    debug_prod = _fact(
        path="app.properties",
        key="debug",
        family=ConfigurationKeyFamily.DEBUG,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=True,
        redacted="true",
        role=SourceClassification.SOURCE,
    )
    debug_test = _fact(
        path="src/test/resources/app.properties",
        key="debug",
        family=ConfigurationKeyFamily.DEBUG,
        value_kind=ValueKind.BOOLEAN,
        literal_boolean=True,
        redacted="true",
        role=SourceClassification.TEST,
    )
    assert tls_verification_disabled(tls_off)
    assert not tls_verification_disabled(tls_on)
    assert hostname_verification_disabled(host_off)
    assert authentication_disabled(auth_off)
    assert permissive_cors_origin(cors_star)
    assert not permissive_cors_origin(cors_ok)
    assert debug_enabled(debug_prod)
    assert debug_enabled(debug_test)

    tls_result = TlsVerificationDisabledRule().evaluate(
        _context(_bundle(facts=(tls_off, tls_on, host_off)))
    )
    assert len(tls_result.matches) == 1
    debug_result = DebugEnabledRule().evaluate(
        _context(_bundle(facts=(debug_prod, debug_test)))
    )
    assert len(debug_result.matches) == 2


def test_finding_category_mapping_and_no_raw_values(tmp_path: Path) -> None:
    evidence = _bundle(
        artifacts=(
            _artifact(
                path="tls/server.key",
                classifications=(ContentClassification.PRIVATE_KEY_MATERIAL,),
            ),
        ),
        facts=(
            _fact(
                path="app.properties",
                key="password",
                family=ConfigurationKeyFamily.CREDENTIAL,
            ),
        ),
    )
    context = _context(evidence)
    matches = []
    for rule in security_rules():
        applicability = rule.evaluate_applicability(context)
        if not applicability.applicable:
            continue
        matches.extend(rule.evaluate(context).matches)
    assert matches
    mapper = RuleFindingMapper()
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.SECURITY for rid in HYGIENE_RULE_IDS},
    )
    assert findings
    assert all(item.category is FindingCategory.SECURITY for item in findings)
    text = dumps_stable_json(
        {
            "ids": [item.id for item in findings],
            "meta": [dict(item.metadata) for item in findings],
        }
    )
    assert "/Users/" not in text
    assert "BEGIN PRIVATE" not in text

    assembler = SecurityAssessmentAssembler()
    section = assembler.assemble(
        repository_id="fixture",
        findings=findings,
        pack_enabled=True,
        evidence_enabled=True,
        evidence_available=True,
        evidence_pipeline="repository_sensitive",
        evidence_fingerprint="deadbeef",
        repository_sensitive_evidence=evidence,
        rule_execution_facts=(),
        rules_executed=len(HYGIENE_RULE_IDS),
    )
    assert section.section_version == SECTION_SCHEMA_VERSION
    assert section.section_version == "1.3.0"
    assert section.status.value == "succeeded"
    assert len(section.all_finding_ids) >= 1
    assert set(section.finding_ids).issubset(set(section.all_finding_ids))
    write = write_security_assessment_artifact(section, tmp_path)
    again = write_security_assessment_artifact(section, tmp_path)
    assert write.path.read_bytes() == again.path.read_bytes()
    body = write.path.read_text(encoding="utf-8")
    assert "risk_score" not in body
    assert "security_score" not in body
    assert "recommendation_groups" not in body
    assert section.synthesis.status.value in {"succeeded", "empty"}


def test_evidence_configuration_sets_line_end_with_line_start() -> None:
    from codestrata.domain.security.taxonomy import SecurityCategory

    item = ConfigurationFactEvidence(
        evidence_id="cfg:app.properties:debug",
        path="config/app.properties",
        classification=SourceClassification.SOURCE,
        format=ConfigurationFormat.PROPERTIES,
        normalized_key="debug",
        key_family=ConfigurationKeyFamily.DEBUG,
        redacted_preview="true",
        value_fingerprint="abc",
        value_length=4,
        value_kind=ValueKind.BOOLEAN,
        placeholder_status=PlaceholderStatus.NOT_APPLICABLE,
        is_empty=False,
        literal_boolean=True,
        is_wildcard_origin=False,
        line_start=3,
        provenance=_prov(),
    )
    evidence = evidence_configuration(
        item=item,
        message="debug enabled",
        security_category=SecurityCategory.CONFIGURATION,
    )
    assert evidence.line_start == 3
    assert evidence.line_end == 3


def test_gates_and_evidence_independence(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_sensitive]
        enabled = true
        [rules]
        enabled = false
        [rules.security]
        enabled = false
        [assessment.sections.security]
        enabled = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_sensitive.enabled is True
    assert settings.rules.security.enabled is False
    assert settings.assessment.sections.security.enabled is False

    # Evidence-only still works.
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("app.properties",),
        file_texts={"app.properties": "password=secret123\ndebug=true\n"},
    )
    assert evidence.configuration_facts
    assert all(
        fact.key_family
        in {
            ConfigurationKeyFamily.CREDENTIAL,
            ConfigurationKeyFamily.DEBUG,
            ConfigurationKeyFamily.SECRET,
        }
        for fact in evidence.configuration_facts
    )


def test_evidence_diagnostic_never_becomes_finding() -> None:
    from codestrata.domain.evidence.repository_sensitive.models import (
        RepositorySensitiveDiagnostic,
    )
    from codestrata.domain.rules.enums import RuleApplicabilityStatus, RuleResultStatus

    evidence = AggregatedRepositorySensitiveEvidence(
        repository_id="fixture",
        diagnostics=(
            RepositorySensitiveDiagnostic(
                diagnostic_id="d1",
                diagnostic_code="malformed_yaml",
                message="malformed",
                path="k8s/db.yml",
            ),
        ),
        evidence_fingerprint="x",
    )
    result = PrivateKeyMaterialRule().evaluate_applicability(_context(evidence))
    assert result.status is RuleApplicabilityStatus.NOT_APPLICABLE
    assert not evidence.artifacts
    assert not evidence.configuration_facts
    # Diagnostics alone never become Findings.
    evaluated = PrivateKeyMaterialRule().evaluate(_context(_bundle()))
    assert evaluated.status is RuleResultStatus.NOT_MATCHED
    assert evaluated.matches == ()

def test_pack_descriptor() -> None:
    pack = SecurityRulePack()
    assert pack.pack_id == "security.core"
    assert "security.private-key-material" in pack.included_rule_ids
    assert pack.deferred_rule_ids
