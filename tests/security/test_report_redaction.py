"""Report serialization redaction (Phase 5.24 / pre-merge hardening)."""

from __future__ import annotations

from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.security.redaction import REDACTED, redact_report_payload, redact_secrets
from codestrata.services.artifact_serialization import findings_payload


def test_assignment_password_and_api_key_redaction() -> None:
    text = 'password = "hunter2-secret"\napi_key=sk-live-abcdefghijklmnopqrstuvwxyz'
    sanitized = redact_secrets(text)
    assert "hunter2-secret" not in sanitized
    assert "sk-live-abcdefghijklmnopqrstuvwxyz" not in sanitized
    assert REDACTED in sanitized


def test_private_key_block_redaction() -> None:
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF6PZGFw=\n"
        "-----END RSA PRIVATE KEY-----"
    )
    sanitized = redact_secrets(f"key={pem}")
    assert "BEGIN RSA PRIVATE KEY" not in sanitized
    assert REDACTED in sanitized


def test_connection_string_and_env_export_redaction() -> None:
    text = (
        "postgres://app:SuperSecretPass@db.example/app\n"
        "export DATABASE_URL=postgres://app:SuperSecretPass@db.example/app\n"
        "export API_TOKEN=abc123tokenvalue"
    )
    sanitized = redact_secrets(text)
    assert "SuperSecretPass" not in sanitized
    assert "abc123tokenvalue" not in sanitized


def test_findings_payload_redacts_excerpts_keeps_paths() -> None:
    finding = Finding.create(
        rule_id="SEC-TEST",
        title="Hardcoded credential",
        description='Found password=SuperSecretPass in config',
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        evidence=[
            FindingEvidence(
                evidence_type="source",
                source_id="src",
                path="config/app.env",
                excerpt="API_KEY=sk-live-should-not-leak-1234567890",
            )
        ],
    )
    evaluation = RuleEvaluationResult.from_findings(
        findings=(finding,),
        rules_evaluated=("SEC-TEST",),
        rules_skipped=(),
    )
    payload = findings_payload(evaluation)
    excerpt = payload["findings"][0]["evidence"][0]["excerpt"]
    path = payload["findings"][0]["evidence"][0]["path"]
    assert path == "config/app.env"
    assert "sk-live-should-not-leak-1234567890" not in excerpt
    assert "SuperSecretPass" not in payload["findings"][0]["description"]
    assert REDACTED in excerpt


def test_report_payload_walk_preserves_ids() -> None:
    payload = {
        "id": "finding-1",
        "rule_id": "R1",
        "path": "src/main.py",
        "excerpt": "token=ghp_" + ("x" * 36),
    }
    redacted = redact_report_payload(payload)
    assert redacted["id"] == "finding-1"
    assert redacted["rule_id"] == "R1"
    assert redacted["path"] == "src/main.py"
    assert "ghp_" not in redacted["excerpt"]
