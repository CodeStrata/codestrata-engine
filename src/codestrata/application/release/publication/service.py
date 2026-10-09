"""Engine-contained publication preflight orchestration (E14.4)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.release.publication.catalog import build_publication_catalog
from codestrata.application.release.publication.models import (
    PublicationCatalog,
    PublicationPreflightSummary,
    PublicRehearsalRecord,
    R01PreflightRecord,
)
from codestrata.application.release.publication.r01_gate import (
    WorkflowPublisherView,
    build_r01_preflight_record,
)
from codestrata.application.release.publication.rehearsal import (
    DEFAULT_EVALUATION_TIME,
    REHEARSAL_IDENTITY,
    REHEARSAL_ISSUER,
    build_rehearsal_verify_payload,
)
from codestrata.application.release.standalone.service import run_build_verification
from codestrata.application.release.verification import (
    VerificationStatus,
    load_packaged_verification_policy,
    verify_payload,
)


def run_publication_preflight(
    *,
    engine_root: Path,
    output_directory: Path,
    r01_status: str,
    r01_reason: str,
    engine_only_oidc_publisher: str | None,
    required_outside_engine_change: str,
    workflows: tuple[WorkflowPublisherView, ...] = (),
    evaluation_time: str = DEFAULT_EVALUATION_TIME,
) -> PublicationPreflightSummary:
    """Build candidate artifacts, rehearse public verification, and record R01."""

    output_directory.mkdir(parents=True, exist_ok=True)
    dist = output_directory / "dist"
    build_summary = run_build_verification(
        engine_root=engine_root,
        output_directory=output_directory,
        dist_directory=dist,
    )
    r01 = build_r01_preflight_record(
        status=r01_status,
        reason=r01_reason,
        engine_only_oidc_publisher=engine_only_oidc_publisher,
        required_outside_engine_change=required_outside_engine_change,
        workflows=workflows,
    )
    policy = load_packaged_verification_policy()
    public_rehearsal: PublicRehearsalRecord | None = None
    rehearsal_ok = False
    if build_summary.ok and build_summary.provenance is not None:
        wheel_digest = build_summary.provenance.primary_artifact_digest("wheel")
        wheels = sorted(dist.glob("*.whl"))
        if wheels and wheel_digest:
            wheel_path = wheels[0]
            artifact = wheel_path.read_bytes()
            if sha256_matches(artifact, wheel_digest):
                payload = build_rehearsal_verify_payload(artifact, evaluation_time=evaluation_time)
                rehearsal_dir = output_directory / "publication-rehearsal"
                rehearsal_dir.mkdir(parents=True, exist_ok=True)
                bundle_path = rehearsal_dir / "wheel.sigstore-bundle.json"
                bundle_path.write_text(
                    json.dumps(payload["bundle"], indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                result = verify_payload(payload)
                rehearsal_ok = result.status is VerificationStatus.VERIFIED
                public_rehearsal = PublicRehearsalRecord(
                    artifact_sha256=wheel_digest,
                    verification_status=result.status.value,
                    verification_reason=result.reason,
                    expected_identity=policy.public_sigstore.expected_identity,
                    expected_issuer=policy.public_sigstore.expected_issuer,
                    oidc_identity=result.identity,
                    oidc_issuer=result.issuer,
                    transparency_log_used=result.transparency_log_used,
                )
    provenance_path = output_directory / "provenance.json"
    sbom_path = output_directory / "runtime-sbom.cdx.json"
    catalog: PublicationCatalog | None = None
    if build_summary.provenance is not None and provenance_path.is_file() and sbom_path.is_file():
        wheels = sorted(dist.glob("*.whl"))
        sdists = sorted(dist.glob("*.tar.gz"))
        bundle_file = output_directory / "publication-rehearsal" / "wheel.sigstore-bundle.json"
        if wheels and sdists:
            catalog = build_publication_catalog(
                output_directory=output_directory,
                engine_root=engine_root,
                wheel_path=wheels[0],
                sdist_path=sdists[0],
                sbom_path=sbom_path,
                provenance_path=provenance_path,
                bundle_path=bundle_file if bundle_file.is_file() else None,
            )
            (output_directory / "publication-catalog.json").write_text(
                catalog.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )

    r01_ready = r01.status == "PRESENT" and not r01.monorepo_ci_relabeled_as_publisher
    ok = (
        build_summary.ok
        and rehearsal_ok
        and not r01.monorepo_ci_relabeled_as_publisher
    )
    detail = "ok" if ok else "publication preflight incomplete"
    if r01.status == "BLOCKED":
        detail = (
            f"{detail}; r01_blocked={required_outside_engine_change or r01.reason}"
            if not ok
            else f"rehearsal_ok; r01_blocked={required_outside_engine_change or r01.reason}"
        )
    summary = PublicationPreflightSummary(
        ok=ok,
        build_ok=build_summary.ok,
        public_rehearsal_ok=rehearsal_ok,
        r01_ready=r01_ready,
        detail=detail,
        provenance=build_summary.provenance,
        catalog=catalog,
        r01=r01,
        public_rehearsal=public_rehearsal,
    )
    (output_directory / "publication-preflight-summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def sha256_matches(artifact: bytes, digest_hex: str) -> bool:
    from codestrata.application.release.standalone.digest import sha256_bytes

    return sha256_bytes(artifact) == digest_hex.lower()


def write_r01_sidecar(output_directory: Path, r01: R01PreflightRecord) -> None:
    (output_directory / "r01-preflight.json").write_text(
        r01.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "REHEARSAL_IDENTITY",
    "REHEARSAL_ISSUER",
    "run_publication_preflight",
    "write_r01_sidecar",
]
