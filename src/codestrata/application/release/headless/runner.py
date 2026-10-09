"""Neutral local headless invocation runner (E14.3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata.application.release.headless.artifacts import write_json_artifact
from codestrata.application.release.headless.detached_signing import (
    assert_analysis_has_no_signer_access,
    scrub_analysis_environ,
    sign_manifest_in_isolated_process,
    write_detached_signature,
)
from codestrata.application.release.headless.models import (
    HeadlessRunError,
    HeadlessRunManifest,
    HeadlessRunOutcome,
)
from codestrata.application.release.headless.package_loader import (
    assert_invocation_offline,
    load_prepared_effective,
    validate_pinned_inputs,
)
from codestrata.application.release.standalone.models import LocalHealthStatus
from codestrata.application.release.standalone.operational import (
    BoundedOperationalAudit,
    bind_headless_operational_limits,
    retention_config,
    write_local_health_status,
)
from codestrata.application.rules.composition.catalog import RuleCatalog
from codestrata.application.rules.effective import (
    CandidateRunRequest,
    ExecutionContext,
    admit_effective,
    execute_candidate,
    execute_preview,
    seal_bundled_community,
)
from codestrata.application.rules.effective.models import FixtureCase
from codestrata.domain.contracts.enums import (
    ExecutionPurpose,
    ExportMode,
    InvocationKind,
    JobProgressState,
    JobTerminalState,
    ResultStatus,
)
from codestrata.domain.contracts.invocation import (
    HeadlessInvocation,
    LocalJobCancellation,
    LocalJobProgress,
    LocalJobState,
    LocalJobTerminal,
    parse_invocation,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.operators.models import OperatorContext, OperatorEdge, OperatorGraph
from codestrata.telemetry.export_models import ExportCategory, parse_export_category
from codestrata.telemetry.signed_projection import run_headless_export

FIXTURE_EXPIRY = "2026-12-31T00:00:00Z"


def run_headless_invocation(
    invocation: HeadlessInvocation | dict[str, Any],
    *,
    package_dir: Path,
    output_dir: Path,
    catalog: RuleCatalog | None = None,
    now: datetime | None = None,
    sign: bool = True,
    signer_private_pem: str | None = None,
    signer_key_id: str | None = None,
    cancelled: bool = False,
) -> HeadlessRunOutcome:
    """Run analysis locally, optionally sign the manifest in a detached process."""

    assert_analysis_has_no_signer_access(scrub_analysis_environ())
    parsed = parse_invocation(invocation) if isinstance(invocation, dict) else invocation
    assert_invocation_offline(parsed)
    when = now or datetime(2026, 9, 22, tzinfo=UTC)
    output_dir.mkdir(parents=True, exist_ok=True)
    audit = BoundedOperationalAudit()
    audit.append(event_id="start", kind="headless", message="neutral local invocation started")
    write_local_health_status(
        output_dir,
        LocalHealthStatus(ok=True, phase="running", database=False, http_service=False),
    )
    _ = retention_config()

    binding = bind_headless_operational_limits(parsed)
    write_json_artifact(
        output_dir / "operational-binding.json",
        binding,
        schema_name=binding.schema_name,
    )

    if cancelled:
        return _finalize_killed(
            output_dir,
            parsed,
            audit,
            reason="cancellation_requested",
        )

    try:
        effective = load_prepared_effective(package_dir)
    except HeadlessRunError as error:
        audit.append(event_id="reject", kind="package", message=str(error))
        return HeadlessRunOutcome(
            ok=False,
            reason=str(error),
            output_directory=str(output_dir),
            admission_admitted=False,
            admission_reason="package_load_failed",
        )

    try:
        validate_pinned_inputs(effective, parsed.pinned_inputs)
    except HeadlessRunError as error:
        audit.append(event_id="reject", kind="pin", message=str(error))
        return HeadlessRunOutcome(
            ok=False,
            reason=str(error),
            output_directory=str(output_dir),
            admission_admitted=False,
            admission_reason="pinned_input_mismatch",
        )

    context = ExecutionContext(now=when, requested_purpose=parsed.requested_package_purpose)
    admission = admit_effective(effective, context)
    write_json_artifact(
        output_dir / "admission.json",
        admission,
        schema_name="codestrata.effective-admission.v1",
    )
    write_json_artifact(
        output_dir / "EffectiveRuleSet.json",
        effective,
        schema_name=effective.schema_name,
    )

    if not admission.admitted:
        audit.append(
            event_id="reject",
            kind="admission",
            message=admission.reason_code or "not_admitted",
        )
        write_local_health_status(
            output_dir,
            LocalHealthStatus(ok=False, phase="rejected", database=False, http_service=False),
        )
        return HeadlessRunOutcome(
            ok=False,
            reason=admission.reason_code or "not_admitted",
            output_directory=str(output_dir),
            admission_admitted=False,
            admission_reason=admission.reason_code,
        )

    if parsed.kind in {InvocationKind.CANDIDATE_VALIDATE, InvocationKind.PREVIEW}:
        candidate_effective, active_catalog = seal_bundled_community(
            purpose=ExecutionPurpose.CANDIDATE_VALIDATION,
        )
        if catalog is not None:
            active_catalog = catalog
        request = _fixture_request(candidate_effective)
        if parsed.kind is InvocationKind.PREVIEW:
            candidate_result = execute_preview(request, active_catalog, context=context)
        else:
            candidate_result = execute_candidate(request, active_catalog, context=context)
        write_json_artifact(
            output_dir / "CandidateRunResult.json",
            candidate_result,
            schema_name="codestrata.candidate-run-result.v1",
        )
        write_json_artifact(
            output_dir / "CandidateValidation.json",
            candidate_result.validation,
            schema_name=candidate_result.validation.schema_name,
        )

    withheld = _export_withheld_categories(parsed)
    export = run_headless_export(
        parsed.export_trust.export_mode,
        artifact_digest=effective.effective_ruleset_digest,
        purpose=effective.execution_purpose,
        withheld_categories=withheld or None,
    )
    write_json_artifact(
        output_dir / "export-original.json",
        export.original.to_manifest_dict(),
        schema_name=export.original.schema,
    )
    write_json_artifact(
        output_dir / "export-projection.json",
        export.projection.to_manifest_dict(),
        schema_name=export.projection.schema,
    )

    job = _completed_job(parsed, effective.effective_ruleset_digest)
    write_json_artifact(output_dir / "local-job-state.json", job, schema_name=job.schema_name)
    write_json_artifact(
        output_dir / "operational-audit.json",
        {"events": [event.model_dump(mode="json") for event in audit.events]},
        schema_name="codestrata.headless-operational-audit.v1",
    )
    write_local_health_status(
        output_dir,
        LocalHealthStatus(ok=True, phase="completed", database=False, http_service=False),
    )

    invocation_digest = digest_canonical(parsed.model_dump(mode="json"))
    artifacts = _collect_artifact_refs(output_dir, exclude=frozenset())
    manifest = HeadlessRunManifest(
        invocation_digest=invocation_digest,
        effective_ruleset_digest=effective.effective_ruleset_digest,
        package_purpose=effective.execution_purpose.value,
        requested_purpose=parsed.requested_package_purpose.value,
        export_mode=parsed.export_trust.export_mode.value,
        artifacts=artifacts,
        export_transmission_performed=export.transmission_performed,
        hosted_calls_performed=False,
        consent_required=False,
        analysis_signer_isolated=True,
    )
    write_json_artifact(
        output_dir / "headless-run-manifest.json",
        manifest,
        schema_name=manifest.schema_name,
    )

    signature = None
    if sign:
        if not signer_private_pem or not signer_key_id:
            raise HeadlessRunError("detached signing requires signer_private_pem and signer_key_id")
        signature = sign_manifest_in_isolated_process(
            manifest,
            private_key_pem=signer_private_pem,
            key_id=signer_key_id,
            purpose=effective.execution_purpose,
        )
        write_detached_signature(output_dir / "detached-signature.json", signature)

    audit.append(event_id="done", kind="headless", message="completed without egress")
    return HeadlessRunOutcome(
        ok=True,
        reason="ok",
        output_directory=str(output_dir),
        manifest=manifest,
        detached_signature=signature,
        admission_admitted=True,
        admission_reason=None,
        job_terminal_state=JobTerminalState.COMPLETED.value,
        job_successful=True,
    )


def _finalize_killed(
    output_dir: Path,
    invocation: HeadlessInvocation,
    audit: BoundedOperationalAudit,
    *,
    reason: str,
) -> HeadlessRunOutcome:
    audit.append(event_id="kill", kind="cancellation", message=reason)
    job_id = digest_canonical({"invocation": invocation.kind.value})[:16]
    job = LocalJobState(
        progress=LocalJobProgress(
            local_job_id=job_id,
            state=JobProgressState.TERMINAL,
            phase="killed",
        ),
        cancellation=LocalJobCancellation(
            local_job_id=job_id,
            requested=True,
            grace_seconds=2,
            process_enforced_hard_cap=True,
        ),
        terminal=LocalJobTerminal(
            local_job_id=job_id,
            terminal_state=JobTerminalState.KILLED,
            successful=False,
            failure_code=reason,
        ),
    )
    write_json_artifact(output_dir / "local-job-state.json", job, schema_name=job.schema_name)
    write_local_health_status(
        output_dir,
        LocalHealthStatus(ok=False, phase="killed", database=False, http_service=False),
    )
    return HeadlessRunOutcome(
        ok=False,
        reason=reason,
        output_directory=str(output_dir),
        admission_admitted=None,
        job_terminal_state=JobTerminalState.KILLED.value,
        job_successful=False,
    )


def _completed_job(invocation: HeadlessInvocation, assessment_digest: str) -> LocalJobState:
    job_id = digest_canonical({"invocation": invocation.kind.value})[:16]
    return LocalJobState(
        progress=LocalJobProgress(
            local_job_id=job_id,
            state=JobProgressState.TERMINAL,
            phase="completed",
        ),
        terminal=LocalJobTerminal(
            local_job_id=job_id,
            terminal_state=JobTerminalState.COMPLETED,
            successful=True,
            assessment_body_digest=assessment_digest,
        ),
    )


def _fixture_request(effective: object) -> CandidateRunRequest:
    from codestrata.domain.contracts.rules import EffectiveRuleSet

    if not isinstance(effective, EffectiveRuleSet):
        raise HeadlessRunError("fixture execution requires EffectiveRuleSet")
    return CandidateRunRequest(
        effective=effective,
        expiry=FIXTURE_EXPIRY,
        permitted_paths=("./fixture",),
        snapshot_only=True,
        fixtures=(
            FixtureCase(
                name="compliant",
                expected_status=ResultStatus.PASS,
                operator_context=_acyclic(),
                path="fixture/ok.py",
            ),
            FixtureCase(
                name="violating",
                expected_status=ResultStatus.FAIL,
                operator_context=_cyclic(),
                path="fixture/bad.py",
            ),
        ),
    )


def _acyclic() -> OperatorContext:
    return OperatorContext(
        declared_graph=OperatorGraph(
            nodes=("a", "b"),
            edges=(OperatorEdge(source="a", target="b", edge_type="imports"),),
            complete=True,
        )
    )


def _cyclic() -> OperatorContext:
    return OperatorContext(
        declared_graph=OperatorGraph(
            nodes=("a", "b", "c"),
            edges=(
                OperatorEdge(source="a", target="b", edge_type="imports"),
                OperatorEdge(source="b", target="c", edge_type="imports"),
                OperatorEdge(source="c", target="a", edge_type="imports"),
            ),
            complete=True,
        )
    )


def _known_withheld_categories(invocation: HeadlessInvocation) -> tuple[str, ...]:
    parsed: list[str] = []
    for item in invocation.export_trust.withheld_categories:
        category = parse_export_category(item)
        if category is not None:
            parsed.append(category.value)
    return tuple(sorted(set(parsed)))


def _export_withheld_categories(invocation: HeadlessInvocation) -> tuple[str, ...]:
    withheld = _known_withheld_categories(invocation)
    if invocation.export_trust.export_mode is ExportMode.RESTRICTED and not withheld:
        return (ExportCategory.GRAPH.value,)
    return withheld


def _collect_artifact_refs(output_dir: Path, *, exclude: frozenset[str]) -> tuple[Any, ...]:
    from codestrata.application.release.headless.models import HeadlessArtifactRef

    names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file()
        and path.name not in exclude
        and path.name
        not in {
            "detached-signature.json",
            "headless-run-manifest.json",
            "codestrata-local-health.json",
        }
    )
    refs: list[HeadlessArtifactRef] = []
    for name in names:
        payload = json.loads((output_dir / name).read_text(encoding="utf-8"))
        schema = str(payload.get("schema_name") or payload.get("schema") or "unknown")
        refs.append(
            HeadlessArtifactRef(
                filename=name,
                schema_name=schema,
                content_digest=digest_canonical(payload),
            )
        )
    return tuple(refs)
