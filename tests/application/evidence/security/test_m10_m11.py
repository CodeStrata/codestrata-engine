"""M10/M11 fixtures: secrets, placeholders, TLS/auth/CORS/debug (E06.1)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.repository_sensitive.artifacts import (
    assert_redacted_payload,
    write_repository_sensitive_evidence_artifact,
)
from codestrata.application.evidence.repository_sensitive.service import (
    RepositorySensitiveEvidenceService,
)
from codestrata.application.evidence.security.consumer import (
    ConsumerContractError,
    consume_envelope,
)
from codestrata.application.evidence.security.envelope import (
    EnvelopeError,
    parse_envelope_payload,
    seal_security_envelope,
)
from codestrata.application.evidence.security.projections import (
    project_security_html,
    project_security_json,
    project_security_sarif,
)
from codestrata.application.rules.security.rules import (
    CredentialLiteralRule,
    DebugEnabledRule,
    PlaceholderCredentialRule,
    PrivateKeyMaterialRule,
    TlsVerificationDisabledRule,
)
from codestrata.application.rules.security.yaml_catalog import catalog_digests
from codestrata.config.settings import RepositorySensitiveEvidenceSettings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ConfigurationFormat,
    ConfigurationKeyFamily,
    ContentClassification,
    PlaceholderStatus,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
    ConfigurationFactEvidence,
)
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleSeverity
from codestrata.services.artifact_serialization import dumps_stable_json

CANARY = "cs_e061_canary_MIIEvg_do_not_emit"
SYNTHETIC_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCsyntheticfixture\n"
    f"{CANARY}\n"
    "-----END PRIVATE KEY-----\n"
)
PLACEHOLDER_PEM = "-----BEGIN PRIVATE KEY-----\nREPLACE_ME\n-----END PRIVATE KEY-----\n"
PUBLIC_LOOKALIKE = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n"
    "-----END PUBLIC KEY-----\n"
)
ENCODED_UNSUPPORTED = (
    "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUVqZ0lCQURBTkJnc3hFCi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0K"
    * 2
)


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _context(
    evidence: AggregatedRepositorySensitiveEvidence,
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        repository_sensitive_evidence=evidence,
    )


def _collect(paths: tuple[str, ...], texts: dict[str, str]):
    service = RepositorySensitiveEvidenceService(RepositorySensitiveEvidenceSettings(enabled=True))
    return service.collect(repository_id="fixture", relative_paths=paths, file_texts=texts)


def test_synthetic_placeholder_and_lookalike_are_distinct() -> None:
    evidence = _collect(
        ("tls/server.key", "tls/placeholder.key", "tls/public.pem", "notes.key"),
        {
            "tls/server.key": SYNTHETIC_PEM,
            "tls/placeholder.key": PLACEHOLDER_PEM,
            "tls/public.pem": PUBLIC_LOOKALIKE,
            "notes.key": "This document mentions BEGIN PRIVATE KEY without headers.\n",
        },
    )
    by_path = {item.path: item for item in evidence.artifacts}
    assert (
        ContentClassification.PRIVATE_KEY_MATERIAL
        in by_path["tls/server.key"].content_classifications
    )
    assert (
        ContentClassification.PLACEHOLDER_ONLY
        in by_path["tls/placeholder.key"].content_classifications
    )
    assert (
        ContentClassification.PRIVATE_KEY_MATERIAL
        not in by_path["tls/public.pem"].content_classifications
    )
    result = PrivateKeyMaterialRule().evaluate(_context(evidence))
    assert result.matched
    paths = {item.evidence[0].attributes["path"] for item in result.matches}
    assert paths == {"tls/server.key"}
    payload = dumps_stable_json({"s": [item.summary for item in result.matches]})
    assert CANARY not in payload
    assert "BEGIN PRIVATE KEY" not in payload or "[REDACTED]" in str(
        result.matches[0].evidence[0].attributes
    )


def test_encoded_unsupported_is_not_a_clean_private_key_claim() -> None:
    evidence = _collect(("encoded.pem",), {"encoded.pem": ENCODED_UNSUPPORTED})
    artifact = evidence.artifacts[0]
    assert ContentClassification.PRIVATE_KEY_MATERIAL not in artifact.content_classifications
    assert artifact.metadata.get("unsupported_encoding") == "true"
    result = PrivateKeyMaterialRule().evaluate(_context(evidence))
    assert result.matches == ()


def test_duplicate_literals_have_path_identity_not_raw_bytes() -> None:
    evidence = _collect(
        ("a.key", "b.key"),
        {"a.key": SYNTHETIC_PEM, "b.key": SYNTHETIC_PEM},
    )
    result = PrivateKeyMaterialRule().evaluate(_context(evidence))
    assert len(result.matches) == 2
    ids = {item.evidence[0].attributes["evidence_id"] for item in result.matches}
    assert len(ids) == 2
    assert evidence.artifacts[0].content_fingerprint == evidence.artifacts[1].content_fingerprint
    joined = dumps_stable_json({"k": [list(item.subject_keys) for item in result.matches]})
    assert CANARY not in joined


def test_zero_raw_secret_canary_leakage(tmp_path: Path) -> None:
    evidence = _collect(
        ("tls/server.key", ".env"),
        {
            "tls/server.key": SYNTHETIC_PEM,
            ".env": f"PASSWORD={CANARY}\n",
        },
    )
    write = write_repository_sensitive_evidence_artifact(
        evidence, tmp_path, extra_canaries=(CANARY,)
    )
    body = write.path.read_text(encoding="utf-8")
    assert CANARY not in body
    matches = PrivateKeyMaterialRule().evaluate(_context(evidence)).matches
    matches += CredentialLiteralRule().evaluate(_context(evidence)).matches
    envelope = seal_security_envelope(
        repository_id="fixture",
        catalog_digest=catalog_digests()["pack"],
        matches=matches,
    )
    dumped = dumps_stable_json(envelope.model_dump(mode="json"))
    json_proj = dumps_stable_json(project_security_json(envelope))
    html = project_security_html(envelope)
    sarif = dumps_stable_json(project_security_sarif(envelope))
    for blob in (dumped, json_proj, html, sarif, body):
        assert CANARY not in blob
        assert_redacted_payload(blob, extra_canaries=(CANARY,))


def test_placeholder_and_literal_credentials_are_split() -> None:
    evidence = _collect(
        ("app.properties",),
        {
            "app.properties": (
                "db.password=not-a-placeholder-value\n"
                "api_token=changeme\n"
                "other_secret=********\n"
                "access_key=AKIAIOSFODNN7EXAMPLE\n"
            )
        },
    )
    literals = CredentialLiteralRule().evaluate(_context(evidence))
    placeholders = PlaceholderCredentialRule().evaluate(_context(evidence))
    assert len(literals.matches) == 1
    assert literals.matches[0].evidence[0].attributes["normalized_key"] in {
        "db_password",
        "password",
    }
    keys = {item.evidence[0].attributes["normalized_key"] for item in placeholders.matches}
    assert "api_token" in keys or "token" in str(keys)
    serialized = dumps_stable_json(
        {"l": [item.summary for item in literals.matches + placeholders.matches]}
    )
    assert "not-a-placeholder-value" not in serialized


def test_tls_auth_cors_debug_true_false_and_unknown_context() -> None:
    evidence = _collect(
        (
            "app.properties",
            "application-prod.properties",
            "src/test/resources/app.properties",
        ),
        {
            "app.properties": (
                "verify_ssl=false\n"
                "verify_ssl_ok=true\n"
                "authentication_enabled=false\n"
                "cors.allowed_origins=*\n"
                "debug=true\n"
            ),
            "application-prod.properties": "debug=false\n",
            "src/test/resources/app.properties": "debug=true\n",
        },
    )
    tls = TlsVerificationDisabledRule().evaluate(_context(evidence))
    debug = DebugEnabledRule().evaluate(_context(evidence))
    assert len(tls.matches) == 1
    assert "exploit" not in tls.matches[0].summary.lower()
    assert tls.matches[0].severity is RuleSeverity.HIGH
    assert len(debug.matches) == 2
    statuses = {item.evidence[0].attributes["production_context_status"] for item in debug.matches}
    assert "production" in statuses
    assert "non_production" in statuses
    envelope = seal_security_envelope(
        repository_id="fixture",
        catalog_digest=catalog_digests()["pack"],
        matches=tls.matches + debug.matches,
    )
    consume_envelope(envelope.model_dump(mode="json"))
    assert envelope.body.counts.m11_tls_disabled == 1
    assert envelope.body.counts.m11_debug_production >= 1
    assert envelope.body.git_history_scanned is False


def test_placeholder_conditional_and_unsupported_config_are_not_tls_findings() -> None:
    evidence = _collect(
        ("application.yml", "app.properties"),
        {
            "application.yml": (
                "spring:\n  profiles: prod\nserver:\n    ssl:\n      verify_ssl: ${VERIFY_SSL}\n"
            ),
            "app.properties": ("verify_ssl=#{environment.acceptsSsl}\ndebug={{ env.debug }}\n"),
        },
    )
    tls = TlsVerificationDisabledRule().evaluate(_context(evidence))
    debug = DebugEnabledRule().evaluate(_context(evidence))
    assert tls.matches == ()
    assert debug.matches == ()
    kinds = {item.value_kind for item in evidence.configuration_facts}
    assert ValueKind.ENVIRONMENT_REFERENCE in kinds or ValueKind.UNKNOWN in kinds


def test_conflicting_debug_settings_are_both_evidenced() -> None:
    evidence = _collect(
        ("application.properties", "application-prod.properties"),
        {
            "application.properties": "debug=true\n",
            "application-prod.properties": "debug=false\n",
        },
    )
    debug_facts = [
        item
        for item in evidence.configuration_facts
        if item.key_family is ConfigurationKeyFamily.DEBUG
    ]
    assert len(debug_facts) == 2
    result = DebugEnabledRule().evaluate(_context(evidence))
    assert len(result.matches) == 1
    assert result.matches[0].evidence[0].attributes["literal_boolean"] == "true"


def test_yaml_severity_is_not_rewritten_for_test_paths() -> None:
    fact = ConfigurationFactEvidence(
        evidence_id="cfg:src/test/resources/app.properties:password",
        path="src/test/resources/app.properties",
        classification=SourceClassification.TEST,
        format=ConfigurationFormat.PROPERTIES,
        normalized_key="password",
        key_family=ConfigurationKeyFamily.CREDENTIAL,
        redacted_preview="[REDACTED]",
        value_fingerprint="abc",
        value_length=12,
        value_kind=ValueKind.LITERAL,
        placeholder_status=PlaceholderStatus.NOT_APPLICABLE,
        provenance=_prov(),
    )
    evidence = AggregatedRepositorySensitiveEvidence(
        repository_id="fixture",
        configuration_facts=(fact,),
        evidence_fingerprint="x",
    )
    result = CredentialLiteralRule().evaluate(_context(evidence))
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.severity is RuleSeverity.HIGH
    assert match.base_severity is RuleSeverity.HIGH
    assert match.calibrated_severity is RuleSeverity.HIGH
    assert match.severity_basis == ("yaml_catalog_default",)
    assert match.evidence[0].attributes["security_context"] == "test"
    assert match.evidence[0].attributes["production_context_status"] == "non_production"


def test_corrupt_envelope_and_wrong_schema_are_rejected() -> None:
    evidence = _collect(("app.properties",), {"app.properties": "debug=true\n"})
    matches = DebugEnabledRule().evaluate(_context(evidence)).matches
    envelope = seal_security_envelope(
        repository_id="fixture",
        catalog_digest="abc",
        matches=matches,
    )
    payload = envelope.model_dump(mode="json")
    payload["schema_name"] = "not.a.schema"
    try:
        parse_envelope_payload(payload)
        raise AssertionError("expected schema rejection")
    except EnvelopeError:
        pass
    broken = envelope.model_dump(mode="json")
    broken["body_digest"] = "0" * 64
    try:
        consume_envelope(broken)
        raise AssertionError("expected consumer rejection")
    except ConsumerContractError:
        pass


def test_projections_copy_counts_without_health_or_raw_secrets() -> None:
    evidence = _collect(("tls/server.key",), {"tls/server.key": SYNTHETIC_PEM})
    matches = PrivateKeyMaterialRule().evaluate(_context(evidence)).matches
    envelope = seal_security_envelope(
        repository_id="fixture",
        catalog_digest=catalog_digests()["security.private-key-material"],
        matches=matches,
    )
    consume_envelope(envelope.model_dump(mode="json"))
    json_proj = project_security_json(envelope)
    assert json_proj["health_verdict"] == "none"
    assert json_proj["git_history_scanned"] is False
    finding = json_proj["findings"][0]
    assert finding["detector_id"]
    assert finding["safe_secret_type"]
    assert "[REDACTED]" in finding["redacted_span"]
    assert CANARY not in dumps_stable_json(json_proj)
    html = project_security_html(envelope)
    assert "health_verdict: none" in html
    assert "Static configuration observations only" in html
    assert "runtime exploit claim" in html
    sarif = project_security_sarif(envelope)
    assert sarif["runs"][0]["results"][0]["properties"]["detector_id"]
    from codestrata.application.rules.execution.family_bind import security_launch_body
    from codestrata.application.rules.execution.projections import JSON_SCHEMA

    launch = security_launch_body(envelope)
    assert json_proj["launch_projection_schema"] == JSON_SCHEMA
    assert json_proj["launch_catalog_body_digest"] == launch.content_digest()
    assert json_proj["launch_catalog"]["health_verdict"] == "none"
    assert f"launch_catalog_body_digest: {launch.content_digest()}" in html
    assert sarif["runs"][0]["properties"]["launch_catalog_body_digest"] == launch.content_digest()
