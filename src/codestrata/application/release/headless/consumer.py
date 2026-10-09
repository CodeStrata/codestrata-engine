"""Independent schema consumer for headless artifact bundles (E14.3).

Validates contract shapes and relationships only. Does not invoke analyzers,
operators, or compilers.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from codestrata.application.release.headless.detached_signing import canonical_manifest_bytes
from codestrata.application.release.headless.models import (
    DetachedResultSignature,
    HeadlessArtifactRef,
    HeadlessRunManifest,
)
from codestrata.application.release.verification.crypto import (
    decode_b64,
    load_public_key_from_pem,
    verify_ed25519,
)
from codestrata.application.release.verification.models import (
    OfflineTrustEntry,
    RevocationInventory,
)
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.invocation import parse_local_job
from codestrata.domain.contracts.rules import parse_effective_ruleset
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.telemetry.signed_projection import parse_original_package

FORBIDDEN_ANALYZER_KEYS = frozenset(
    {
        "health_score",
        "overall_score",
        "synthetic_zero",
        "invented_trend",
    }
)


class HeadlessConsumerError(ValueError):
    """Artifact bundle failed independent consumer validation."""


def consume_headless_bundle(
    output_dir: Path,
    *,
    trust_store: tuple[OfflineTrustEntry, ...] = (),
    revocation: RevocationInventory | None = None,
    evaluation_time: str = "2026-09-22T00:00:00Z",
    require_signature: bool = True,
) -> HeadlessRunManifest:
    """Read a headless output directory using schema parsers only."""

    manifest_path = output_dir / "headless-run-manifest.json"
    if not manifest_path.is_file():
        raise HeadlessConsumerError("missing headless-run-manifest.json")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        manifest = HeadlessRunManifest.model_validate(manifest_payload)
    except ValidationError as error:
        raise HeadlessConsumerError("invalid headless run manifest") from error

    if digest_canonical(manifest_payload) != digest_canonical(manifest.model_dump(mode="json")):
        raise HeadlessConsumerError("manifest is not canonical")

    for ref in manifest.artifacts:
        _validate_artifact_ref(output_dir, ref)

    effective_path = output_dir / "EffectiveRuleSet.json"
    if effective_path.is_file():
        effective = parse_effective_ruleset(json.loads(effective_path.read_text(encoding="utf-8")))
        if effective.effective_ruleset_digest != manifest.effective_ruleset_digest:
            raise HeadlessConsumerError("effective ruleset digest mismatch")

    job_path = output_dir / "local-job-state.json"
    if job_path.is_file():
        job = parse_local_job(json.loads(job_path.read_text(encoding="utf-8")))
        if job.terminal is not None and job.terminal.successful:
            if job.terminal.assessment_body_digest != manifest.effective_ruleset_digest:
                raise HeadlessConsumerError("completed job digest mismatch")

    projection_path = output_dir / "export-projection.json"
    if projection_path.is_file():
        projection_payload = json.loads(projection_path.read_text(encoding="utf-8"))
        _walk_forbidden(projection_payload)
        body = projection_payload.get("body")
        if not isinstance(body, dict) or "export_mode" not in body:
            raise HeadlessConsumerError("export projection missing body.export_mode")

    original_path = output_dir / "export-original.json"
    if original_path.is_file():
        parse_original_package(json.loads(original_path.read_text(encoding="utf-8")))

    if manifest.export_transmission_performed:
        raise HeadlessConsumerError("export transmission must remain false for local headless runs")
    if manifest.hosted_calls_performed:
        raise HeadlessConsumerError("hosted calls must remain false")
    if manifest.consent_required:
        raise HeadlessConsumerError("consent must not be required for this local profile")

    signature_path = output_dir / "detached-signature.json"
    if require_signature:
        if not signature_path.is_file():
            raise HeadlessConsumerError("missing detached-signature.json")
        signature = DetachedResultSignature.model_validate(
            json.loads(signature_path.read_text(encoding="utf-8")),
        )
        if signature.manifest_digest != digest_canonical(manifest_payload):
            raise HeadlessConsumerError("detached signature manifest digest mismatch")
        _verify_detached_signature(
            manifest,
            signature,
            trust_store=trust_store,
            revocation=revocation,
            evaluation_time=evaluation_time,
        )
    return manifest


def _validate_artifact_ref(output_dir: Path, ref: HeadlessArtifactRef) -> None:
    path = output_dir / ref.filename
    if not path.is_file():
        raise HeadlessConsumerError(f"missing artifact file {ref.filename}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    _walk_forbidden(payload)
    if digest_canonical(payload) != ref.content_digest:
        raise HeadlessConsumerError(f"artifact digest mismatch for {ref.filename}")


def _walk_forbidden(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_ANALYZER_KEYS:
                raise HeadlessConsumerError(f"forbidden analyzer field at {path}.{key_text}")
            _walk_forbidden(item, path=f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_forbidden(item, path=f"{path}[{index}]")


def _verify_detached_signature(
    manifest: HeadlessRunManifest,
    signature: DetachedResultSignature,
    *,
    trust_store: tuple[OfflineTrustEntry, ...],
    revocation: RevocationInventory | None,
    evaluation_time: str,
) -> None:
    body = canonical_manifest_bytes(manifest)
    sig_bytes = decode_b64(signature.signature_b64, label="signature")
    if not trust_store:
        raise HeadlessConsumerError("trust store required for detached signature verification")
    entry = next((item for item in trust_store if item.key_id == signature.key_id), None)
    if entry is None:
        raise HeadlessConsumerError("trust entry missing for detached signature")
    public = load_public_key_from_pem(entry.public_key_pem)
    if not verify_ed25519(public, sig_bytes, body):
        raise HeadlessConsumerError("detached Ed25519 signature mismatch")
    if entry.purpose.value != signature.purpose:
        raise HeadlessConsumerError("preview signer cannot authorize production purpose")
    production_request = manifest.requested_purpose == ExecutionPurpose.PRODUCTION.value
    if production_request and entry.purpose is not ExecutionPurpose.PRODUCTION:
        raise HeadlessConsumerError("preview signer cannot authorize production purpose")
    _ = evaluation_time, revocation
