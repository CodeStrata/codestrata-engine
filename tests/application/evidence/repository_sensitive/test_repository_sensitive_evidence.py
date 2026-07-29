"""Repository-sensitive evidence tests (Phase 4.5.2)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.evidence.repository_sensitive.artifacts import (
    repository_sensitive_evidence_payload,
    write_repository_sensitive_evidence_artifact,
)
from codestrata.application.evidence.repository_sensitive.config_parsers import (
    parse_configuration,
    parse_dotenv,
    parse_json,
    parse_properties,
    parse_toml,
    parse_yaml,
)
from codestrata.application.evidence.repository_sensitive.discovery import (
    classify_candidate,
    discover_candidates,
    is_ignored_path,
)
from codestrata.application.evidence.repository_sensitive.service import (
    RepositorySensitiveEvidenceService,
)
from codestrata.application.evidence.repository_sensitive.signatures import (
    classify_text_signatures,
)
from codestrata.application.evidence.repository_sensitive.values import (
    REDACTED_PREVIEW,
    classify_placeholder,
    value_facts,
)
from codestrata.config import load_settings
from codestrata.config.settings import RepositorySensitiveEvidenceSettings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.repository_sensitive.enums import (
    ContentClassification,
    InspectionStatus,
    PlaceholderStatus,
    RepositorySensitiveParseStatus,
    SensitiveArtifactKind,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import (
    REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_FILENAME,
    REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION,
)
from codestrata.services.artifact_serialization import dumps_stable_json


def test_settings_disabled_by_default(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    settings = load_settings(config)
    assert settings.evidence.repository_sensitive.enabled is False


def test_settings_can_enable(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_sensitive]
        enabled = true
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.evidence.repository_sensitive.enabled is True


def test_independent_of_security_gates(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [evidence.repository_sensitive]
        enabled = true
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


def test_artifact_discovery_patterns_and_source_role() -> None:
    paths = (
        ".env",
        ".env.example",
        "id_rsa",
        "certs/server.pem",
        "certs/server.crt",
        "store/app.jks",
        "store/trust.p12",
        ".aws/credentials",
        ".npmrc",
        "src/test/resources/id_ed25519",
        "node_modules/.env",
        "readme.md",
        "long-random-string.txt",
    )
    found = discover_candidates(paths)
    by_path = {path: (kind, bases) for path, kind, bases in found}
    assert ".env" in by_path
    assert by_path[".env"][0] is SensitiveArtifactKind.ENVIRONMENT_FILE
    assert ".env.example" in by_path
    assert "id_rsa" in by_path
    assert "certs/server.pem" in by_path
    assert "certs/server.crt" in by_path
    assert "store/app.jks" in by_path
    assert "store/trust.p12" in by_path
    assert ".aws/credentials" in by_path
    assert ".npmrc" in by_path
    assert "node_modules/.env" not in by_path
    assert "readme.md" not in by_path
    assert is_ignored_path("node_modules/.env", ignore_markers=("/node_modules/",))
    test_role = classify_candidate("src/test/resources/id_ed25519")
    assert test_role[0] is SensitiveArtifactKind.SSH_PRIVATE_KEY
    ordered = [path for path, _, _ in found]
    assert ordered == sorted(ordered)


def test_candidate_filename_does_not_imply_content() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("id_rsa",),
        file_texts={"id_rsa": "not a key file\njust notes\n"},
    )
    assert len(evidence.artifacts) == 1
    artifact = evidence.artifacts[0]
    assert artifact.content_classifications == (
        ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
    )
    assert "BEGIN PRIVATE KEY" not in dumps_stable_json(
        repository_sensitive_evidence_payload(evidence)
    )


def test_pem_and_openssh_and_certificate_signatures() -> None:
    private = "-----BEGIN RSA PRIVATE KEY-----\nAABB\n-----END RSA PRIVATE KEY-----\n"
    openssh = "-----BEGIN OPENSSH PRIVATE KEY-----\nxx\n-----END OPENSSH PRIVATE KEY-----\n"
    cert = "-----BEGIN CERTIFICATE-----\nyy\n-----END CERTIFICATE-----\n"
    long_string = "a" * 5000

    assert (
        ContentClassification.PRIVATE_KEY_MATERIAL
        in classify_text_signatures(private)
    )
    assert (
        ContentClassification.PRIVATE_KEY_MATERIAL
        in classify_text_signatures(openssh)
    )
    assert (
        ContentClassification.PUBLIC_CERTIFICATE_MATERIAL
        in classify_text_signatures(cert)
    )
    assert ContentClassification.PRIVATE_KEY_MATERIAL not in classify_text_signatures(
        cert
    )
    assert classify_text_signatures(long_string) == (
        ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
    )
    assert classify_text_signatures("") == (
        ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
    )
    assert (
        ContentClassification.CREDENTIAL_ENTRIES
        in classify_text_signatures("PASSWORD=example\n")
    )
    assert (
        ContentClassification.CREDENTIAL_ENTRIES
        in classify_text_signatures("CODESTRATA_GITHUB_TOKEN=x\n")
    )
    assert classify_text_signatures(
        "# CODESTRATA_GITHUB_TOKEN=\nCODESTRATA_LOG_LEVEL=WARNING\n"
    ) == (
        ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
    )


def test_no_private_key_content_serialized() -> None:
    material = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7SECRETVALUE\n"
        "-----END PRIVATE KEY-----\n"
    )
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("tls/server.key",),
        file_texts={"tls/server.key": material},
    )
    payload = dumps_stable_json(repository_sensitive_evidence_payload(evidence))
    assert "SECRETVALUE" not in payload
    assert "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7" not in payload
    assert evidence.artifacts[0].kind is SensitiveArtifactKind.PRIVATE_KEY
    assert (
        ContentClassification.PRIVATE_KEY_MATERIAL
        in evidence.artifacts[0].content_classifications
    )


def test_binary_keystore_metadata_only() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    raw = b"\x00\x01\xfeJKS-BINARY-NOT-A-SECRET"
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("store/app.jks", "store/app.p12", "store/app.pfx"),
        file_texts={},
        file_binaries={
            "store/app.jks": raw,
            "store/app.p12": raw,
            "store/app.pfx": raw,
        },
    )
    assert len(evidence.artifacts) == 3
    for artifact in evidence.artifacts:
        assert artifact.inspection_status is InspectionStatus.UNSUPPORTED_BINARY
        assert artifact.content_fingerprint is not None
        assert artifact.size_bytes == len(raw)
    payload = dumps_stable_json(repository_sensitive_evidence_payload(evidence))
    assert "JKS-BINARY-NOT-A-SECRET" not in payload
    assert evidence.coverage.unsupported_binaries == 3
    assert evidence.coverage.metadata_only_files == 3


def test_configuration_parsers_collect_literals_not_findings() -> None:
    props, _ = parse_properties(
        "server.ssl.enabled=true\n"
        "app.password=changeme\n"
        "app.debug=true\n"
        "cors.allowed_origins=*\n"
        "endpoint=http://example.local/api\n"
    )
    keys = {item["normalized_key"] for item in props}
    assert "app_password" in keys or "password" in str(keys)
    assert any(item["redacted_preview"] == REDACTED_PREVIEW for item in props)
    assert any(
        item["placeholder_status"] is PlaceholderStatus.PLACEHOLDER_LITERAL
        for item in props
    )

    dotenv, _ = parse_dotenv("API_TOKEN=${API_TOKEN}\nDEBUG=true\n")
    assert any(
        item["value_kind"] is ValueKind.ENVIRONMENT_REFERENCE for item in dotenv
    )

    yaml_facts, _ = parse_yaml(
        "spring:\n  datasource:\n    password: secret\n  profiles: prod\n"
    )
    assert yaml_facts
    assert all(item["redacted_preview"] != "secret" for item in yaml_facts)

    json_facts, _ = parse_json('{"client_secret":"abc123","debug":false}')
    assert json_facts
    assert all("abc123" not in str(item["redacted_preview"]) for item in json_facts)

    toml_facts, _ = parse_toml('[auth]\ntoken = "sample"\n')
    assert toml_facts

    fmt, facts, diags = parse_configuration(
        "application.properties", "db.password=\n"
    )
    assert fmt.value == "properties"
    assert facts
    assert not diags


def test_malformed_json_diagnostic_safe() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    bad = '{"password": "should-not-leak"'
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("config.json",),
        file_texts={"config.json": bad},
    )
    payload = dumps_stable_json(repository_sensitive_evidence_payload(evidence))
    assert "should-not-leak" not in payload
    assert any(d.diagnostic_code == "malformed_json" for d in evidence.diagnostics)
    assert evidence.coverage.malformed_files >= 1


def test_placeholders_and_redaction() -> None:
    assert classify_placeholder("")[0] is PlaceholderStatus.EMPTY
    assert classify_placeholder("changeme")[0] is PlaceholderStatus.PLACEHOLDER_LITERAL
    assert (
        classify_placeholder("${ENV_VAR}")[0]
        is PlaceholderStatus.ENVIRONMENT_INTERPOLATION
    )
    assert classify_placeholder("$ENV_VAR")[0] is PlaceholderStatus.ENVIRONMENT_INTERPOLATION
    assert (
        classify_placeholder("${MYSQL_PASS:petclinic}")[0]
        is PlaceholderStatus.ENVIRONMENT_INTERPOLATION
    )
    facts = value_facts("super-secret-value-xyz", sensitive=True)
    assert facts["redacted_preview"] == REDACTED_PREVIEW
    assert facts["value_fingerprint"] is not None
    assert "super-secret" not in json.dumps(facts, default=str)
    empty = value_facts("", sensitive=True)
    assert empty["is_empty"] is True
    assert empty["redacted_preview"] == "[EMPTY]"
    assert empty["placeholder_status"] is PlaceholderStatus.EMPTY


def test_oversized_and_coverage_reconcile() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(".env", "store/app.jks"),
        file_texts={},
        file_binaries={"store/app.jks": b"\x00\x01"},
        load_errors={".env": "file_too_large"},
    )
    assert evidence.coverage.candidate_files_discovered == 2
    assert evidence.coverage.skipped_files >= 1
    assert evidence.coverage.unsupported_binaries == 1
    assert evidence.coverage.configuration_facts_collected == len(
        evidence.configuration_facts
    )
    assert all(
        "Finding" not in item.summary for item in evidence.limitations
    )


def test_determinism_and_no_absolute_paths(tmp_path: Path) -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    paths = (".env", "tls/server.crt", "app.properties")
    texts = {
        ".env": "PASSWORD=example\n",
        "tls/server.crt": "-----BEGIN CERTIFICATE-----\nAA\n-----END CERTIFICATE-----\n",
        "app.properties": "ssl.enabled=true\ndebug=false\n",
    }
    first = service.collect(
        repository_id="fixture", relative_paths=paths, file_texts=texts
    )
    second = service.collect(
        repository_id="fixture", relative_paths=paths, file_texts=texts
    )
    a = dumps_stable_json(repository_sensitive_evidence_payload(first))
    b = dumps_stable_json(repository_sensitive_evidence_payload(second))
    assert a == b
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assert str(tmp_path) not in a
    assert "/Users/" not in a
    assert first.schema_version == REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION

    write = write_repository_sensitive_evidence_artifact(first, tmp_path)
    assert write.path.name == REPOSITORY_SENSITIVE_EVIDENCE_ARTIFACT_FILENAME
    again = write_repository_sensitive_evidence_artifact(second, tmp_path)
    assert write.path.read_bytes() == again.path.read_bytes()
    assert REPOSITORY_SENSITIVE_EVIDENCE_SCHEMA_VERSION == "1.1.0"


def test_disabled_gate_skips_collection() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=False)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=(".env",),
        file_texts={".env": "PASSWORD=secret\n"},
    )
    assert evidence.status is RepositorySensitiveParseStatus.NOT_APPLICABLE
    assert evidence.artifacts == ()
    assert evidence.configuration_facts == ()


def test_source_role_preserved() -> None:
    service = RepositorySensitiveEvidenceService(
        RepositorySensitiveEvidenceSettings(enabled=True)
    )
    evidence = service.collect(
        repository_id="fixture",
        relative_paths=("src/main/resources/.env", "src/test/resources/.env"),
        file_texts={
            "src/main/resources/.env": "TOKEN=test\n",
            "src/test/resources/.env": "TOKEN=test\n",
        },
    )
    roles = {item.path: item.classification for item in evidence.artifacts}
    assert roles["src/test/resources/.env"] is SourceClassification.TEST


def test_no_security_domain_import_in_collectors() -> None:
    import codestrata.application.evidence.repository_sensitive.collector as collector_mod
    import codestrata.application.evidence.repository_sensitive.service as service_mod

    for module in (collector_mod, service_mod):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "codestrata.domain.security" not in source
        assert "from codestrata.domain.findings" not in source
        assert "FindingCategory" not in source
        assert "emit_finding" not in source.lower()