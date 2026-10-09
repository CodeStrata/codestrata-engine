"""E14.3 headless runner, detached signing, and schema consumer interoperability."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from codestrata.application.release.headless import (
    assert_analysis_has_no_signer_access,
    consume_headless_bundle,
    run_headless_invocation,
    sign_manifest_in_isolated_process,
)
from codestrata.application.release.headless.consumer import HeadlessConsumerError
from codestrata.application.release.headless.detached_signing import SIGNER_ENV
from codestrata.application.release.standalone.operational import (
    read_local_health_status,
    retention_config,
)
from codestrata.domain.contracts.enums import ExecutionPurpose, ExportMode
from codestrata.domain.contracts.examples_e01_3 import example_invocation, example_pinned
from codestrata.domain.contracts.rules import EffectiveRuleSet
from codestrata.telemetry.export_modes import ExportMode as TelemetryExportMode
from tests.application.release.support.headless_fixtures import (
    PREVIEW_KEY_ID,
    PRODUCTION_KEY_ID,
    generate_ed25519_pem_pair,
    preview_invocation_for_package,
    production_invocation,
    trust_entry,
    write_customer_production_package,
    write_preview_package,
)


@pytest.fixture()
def production_signer() -> tuple[str, str, str]:
    private_pem, public_pem = generate_ed25519_pem_pair()
    return private_pem, public_pem, PRODUCTION_KEY_ID


@pytest.fixture()
def preview_signer() -> tuple[str, str, str]:
    private_pem, public_pem = generate_ed25519_pem_pair()
    return private_pem, public_pem, PREVIEW_KEY_ID


def test_production_customer_package_runs_and_consumer_reads(
    tmp_path: Path,
    production_signer: tuple[str, str, str],
) -> None:
    private_pem, public_pem, key_id = production_signer
    package = tmp_path / "customer-production"
    write_customer_production_package(package)
    output = tmp_path / "out-production"
    outcome = run_headless_invocation(
        production_invocation(),
        package_dir=package,
        output_dir=output,
        signer_private_pem=private_pem,
        signer_key_id=key_id,
    )
    assert outcome.ok is True
    assert outcome.admission_admitted is True
    assert outcome.job_successful is True
    assert (output / "EffectiveRuleSet.json").is_file()
    assert (output / "detached-signature.json").is_file()
    trust = (
        trust_entry(
            key_id=key_id,
            public_pem=public_pem,
            purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    manifest = consume_headless_bundle(output, trust_store=trust)
    assert manifest.requested_purpose == ExecutionPurpose.PRODUCTION.value
    health = read_local_health_status(output)
    assert health.ok is True
    assert health.database is False
    assert retention_config().get("preserve_active_baseline") is True


def test_preview_purpose_run_in_separate_context(
    tmp_path: Path,
    preview_signer: tuple[str, str, str],
) -> None:
    private_pem, public_pem, key_id = preview_signer
    package = tmp_path / "preview-package"
    write_preview_package(package)
    output = tmp_path / "out-preview"
    outcome = run_headless_invocation(
        preview_invocation_for_package(package),
        package_dir=package,
        output_dir=output,
        signer_private_pem=private_pem,
        signer_key_id=key_id,
    )
    assert outcome.ok is True
    assert (output / "CandidateRunResult.json").is_file()
    trust = (
        trust_entry(
            key_id=key_id,
            public_pem=public_pem,
            purpose=ExecutionPurpose.PREVIEW,
        ),
    )
    manifest = consume_headless_bundle(output, trust_store=trust)
    assert manifest.package_purpose == ExecutionPurpose.PREVIEW.value
    assert (output / "export-projection.json").is_file()


def test_preview_only_package_rejected_for_production_purpose(tmp_path: Path) -> None:
    package = tmp_path / "preview-package"
    write_preview_package(package)
    effective = EffectiveRuleSet.model_validate(
        json.loads((package / "EffectiveRuleSet.json").read_text(encoding="utf-8")),
    )
    invocation = example_invocation(purpose=ExecutionPurpose.PRODUCTION)
    invocation = invocation.model_copy(update={"pinned_inputs": example_pinned(effective)})
    outcome = run_headless_invocation(
        invocation.model_dump(mode="json"),
        package_dir=package,
        output_dir=tmp_path / "out-reject",
        sign=False,
    )
    assert outcome.ok is False
    assert outcome.admission_reason == "preview_cannot_authorize_production"


def test_preview_signer_cannot_authorize_production_manifest(
    tmp_path: Path,
    production_signer: tuple[str, str, str],
    preview_signer: tuple[str, str, str],
) -> None:
    prod_private, prod_public, prod_key = production_signer
    preview_private, _preview_public, preview_key = preview_signer
    package = tmp_path / "customer-production"
    write_customer_production_package(package)
    output = tmp_path / "out-prod"
    outcome = run_headless_invocation(
        production_invocation(),
        package_dir=package,
        output_dir=output,
        signer_private_pem=prod_private,
        signer_key_id=prod_key,
    )
    assert outcome.ok and outcome.manifest is not None
    wrong_signature = sign_manifest_in_isolated_process(
        outcome.manifest,
        private_key_pem=preview_private,
        key_id=preview_key,
        purpose=ExecutionPurpose.PREVIEW,
    )
    (output / "detached-signature.json").write_text(
        json.dumps(wrong_signature.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    production_trust = (
        trust_entry(
            key_id=prod_key,
            public_pem=prod_public,
            purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    with pytest.raises(HeadlessConsumerError, match="trust entry missing"):
        consume_headless_bundle(output, trust_store=production_trust)


def test_analysis_env_cannot_access_signer_credentials() -> None:
    env = os.environ.copy()
    env[SIGNER_ENV] = "-----BEGIN PRIVATE KEY-----"
    with pytest.raises(Exception, match="signer credentials"):
        assert_analysis_has_no_signer_access(env)


def test_no_export_retains_local_utility(
    tmp_path: Path,
    production_signer: tuple[str, str, str],
) -> None:
    private_pem, public_pem, key_id = production_signer
    package = tmp_path / "customer-production"
    write_customer_production_package(package)
    invocation = production_invocation()
    invocation["export_trust"] = {
        "export_mode": ExportMode.NONE.value,
        "trust_policy_path": "./trust-policy.yaml",
        "withheld_categories": ("source_text",),
        "allow_preview_signer_for_production": False,
    }
    output = tmp_path / "out-no-export"
    outcome = run_headless_invocation(
        invocation,
        package_dir=package,
        output_dir=output,
        signer_private_pem=private_pem,
        signer_key_id=key_id,
    )
    assert outcome.ok is True
    assert outcome.manifest is not None
    assert outcome.manifest.export_transmission_performed is False
    projection = json.loads((output / "export-projection.json").read_text(encoding="utf-8"))
    body = projection.get("body") or projection
    assert body.get("export_mode") == TelemetryExportMode.NONE.value
    trust = (
        trust_entry(
            key_id=key_id,
            public_pem=public_pem,
            purpose=ExecutionPurpose.PRODUCTION,
        ),
    )
    consume_headless_bundle(output, trust_store=trust)


def test_killed_output_is_not_successful_completion(tmp_path: Path) -> None:
    package = tmp_path / "customer-production"
    write_customer_production_package(package)
    outcome = run_headless_invocation(
        production_invocation(),
        package_dir=package,
        output_dir=tmp_path / "out-killed",
        sign=False,
        cancelled=True,
    )
    assert outcome.ok is False
    assert outcome.job_successful is False
    assert outcome.job_terminal_state == "killed"
    with pytest.raises(HeadlessConsumerError):
        consume_headless_bundle(tmp_path / "out-killed", trust_store=(), require_signature=False)
