"""SV.10 curated repository validation runner."""

from __future__ import annotations

import json
import shutil
import traceback
from pathlib import Path
from typing import Iterable

from verification.cli_installation.environment import engine_root_from_package
from verification.curated_repository_validation.assessment import (
    build_assessment_env,
    cleanup_venv,
    install_codestrata_cli,
    run_customer_workflow,
)
from verification.curated_repository_validation.artifacts import (
    discover_run_dir,
    preserve_run_artifacts,
    validate_artifacts,
)
from verification.curated_repository_validation.batches import (
    resolve_batches,
    select_determinism_sample,
)
from verification.curated_repository_validation.catalog import (
    ReleaseValidationEntry,
    assert_readiness_pass,
    load_catalog_document,
    load_release_validation_entries,
    monorepo_root_from_engine,
)
from verification.curated_repository_validation.clone import cleanup_clone, clone_release_entry
from verification.curated_repository_validation.contract import (
    DATASET_DISCLAIMER,
    RELEASE_VALIDATION_TARGET,
    TIER_ORDER,
    default_contract,
)
from verification.curated_repository_validation.determinism import compare_assessment_runs
from verification.curated_repository_validation.models import RepositoryValidationResult
from verification.curated_repository_validation.records import (
    list_repository_records,
    write_repository_record,
)
from verification.curated_repository_validation.retries import retry_once, should_retry_clone
from verification.curated_repository_validation.safety import available_disk_gb, check_disk_for_tier
from verification.curated_repository_validation.source_integrity import (
    capture_source_inventory,
    verify_checkout_unchanged,
    verify_source_integrity,
)
from verification.curated_repository_validation.summary import (
    build_final_report,
    build_tier_summary,
    write_tier_summary,
)
from verification.curated_repository_validation.timeouts import (
    assessment_timeout_for_tier,
    clone_timeout_for_tier,
    is_timeout_exit,
)
from verification.curated_repository_validation.workspace import (
    cleanup_workspace,
    create_workspace,
    ensure_external,
)
from verification.repository_assessment.clone import CloneResult


def _default_output_dir(engine_root: Path) -> Path:
    return engine_root / "reports" / "verification" / "sv10"


def _classify_failure(
    *,
    stage: str,
    exit_code: int | None,
    artifact_class: str | None,
    source_ok: bool,
    clone_ok: bool,
) -> tuple[str, str]:
    if not clone_ok:
        return "clone_failure", "environment_limitation"
    if stage == "doctor":
        return "doctor_failure", "engine_product"
    if stage in {"init", "init_config_missing"}:
        return "initialization_failure", "engine_product"
    if is_timeout_exit(exit_code):
        return "timeout", "environment_limitation"
    if artifact_class:
        scope = (
            "engine_product"
            if artifact_class
            in {"schema_failure", "traceability_failure", "privacy_failure", "artifact_malformed"}
            else "repository_specific"
        )
        return artifact_class, scope
    if not source_ok:
        return "source_integrity_failure", "engine_product"
    if exit_code not in (0, None):
        return "assessment_failure", "engine_product"
    return "assessment_failure", "engine_product"


def _run_one_repository(
    entry: ReleaseValidationEntry,
    *,
    engine_root: Path,
    codestrata: Path,
    venv_dir: Path,
    output_dir: Path,
    keep_workspace: bool,
) -> RepositoryValidationResult:
    limitations: list[str] = []
    if entry.requires_submodules:
        limitations.append(
            "catalog declares submodules; assessed without initializing submodules"
        )
    if entry.requires_git_lfs:
        limitations.append("catalog declares Git LFS; LFS objects were not fetched")

    workspace = create_workspace(prefix=f"cs-sv10-{entry.repository_id}-")
    ensure_external(workspace, monorepo_root_from_engine(engine_root))
    retries: list[dict[str, str]] = []
    record = RepositoryValidationResult(
        repository_id=entry.repository_id,
        project_name=entry.project_name,
        github_repository=entry.github_repository,
        language_group=entry.language_group,
        ecosystem=entry.ecosystem,
        tier=entry.tier,
        qualified_revision=entry.qualified_revision.value,
        final_checkout_sha=None,
        clone_result="not_attempted",
        initialization_result="not_attempted",
        doctor_result="not_attempted",
        assessment_result="not_attempted",
        exit_code=None,
        duration_bucket=None,
        limitations=list(limitations),
        deterministic_mode=True,
        ai_executed=False,
        telemetry_transmitted=False,
    )

    try:
        def _clone() -> CloneResult:
            cleanup_clone(workspace.clone_dir)
            return clone_release_entry(
                entry,
                workspace.clone_dir,
                codestrata_root=monorepo_root_from_engine(engine_root),
                timeout_s=clone_timeout_for_tier(entry.tier),
            )

        clone_result, clone_retries = retry_once(
            _clone,
            should_retry=lambda result: (not result.ok) and should_retry_clone(result.detail),
        )
        retries.extend(clone_retries)
        record.retries = retries
        if not clone_result.ok:
            record.clone_result = f"fail:{clone_result.detail[:160]}"
            record.failure_classification = "clone_failure"
            record.cause_scope = "environment_limitation"
            record.verdict = "FAIL"
            return record

        record.clone_result = "pass"
        record.final_checkout_sha = clone_result.checked_out_sha
        if (clone_result.checked_out_sha or "").lower() != entry.qualified_revision.value.lower():
            record.failure_classification = "revision_mismatch"
            record.cause_scope = "catalog_metadata"
            record.verdict = "FAIL"
            return record

        before = capture_source_inventory(workspace.clone_dir)
        env = build_assessment_env(home=workspace.home_dir, venv_dir=venv_dir, offline=True)
        workflow = run_customer_workflow(
            codestrata,
            repo_cwd=workspace.clone_dir,
            env=env,
            assess_timeout_s=assessment_timeout_for_tier(entry.tier),
        )
        doctor = workflow["doctor"]
        init = workflow["init"]
        assess = workflow["assess"]
        stage = workflow["stage"]

        # Pre-init doctor may be non-zero (missing config); post-init doctor is recorded.
        record.doctor_result = (
            "pass"
            if doctor and doctor.exit_code == 0 and not doctor.has_traceback
            else (
                f"fail:exit={doctor.exit_code}"
                if doctor and doctor.exit_code != 0
                else "fail:traceback"
            )
        )
        if stage == "doctor":
            record.initialization_result = "not_run"
            record.assessment_result = "not_run"
            record.exit_code = doctor.exit_code if doctor else None
            record.failure_classification = "doctor_failure"
            record.cause_scope = "engine_product"
            record.verdict = "FAIL"
            return record

        if init is None:
            record.initialization_result = "not_run"
        else:
            record.initialization_result = (
                "pass" if init.exit_code == 0 else f"fail:exit={init.exit_code}"
            )
        if assess is None:
            record.assessment_result = "not_run"
            record.exit_code = init.exit_code if init else None
            classification, scope = _classify_failure(
                stage=stage,
                exit_code=record.exit_code,
                artifact_class=None,
                source_ok=True,
                clone_ok=True,
            )
            record.failure_classification = classification
            record.cause_scope = scope
            record.verdict = "FAIL"
            return record

        record.exit_code = assess.exit_code
        record.duration_bucket = assess.duration_bucket
        if is_timeout_exit(assess.exit_code):
            record.assessment_result = "timeout"
            record.failure_classification = "timeout"
            record.cause_scope = "environment_limitation"
            record.verdict = "FAIL"
            record.warnings.append("assessment timed out; not evidence of assessment inaccuracy")
            return record
        if assess.exit_code != 0:
            record.assessment_result = f"fail:exit={assess.exit_code}"
            record.failure_classification = "assessment_failure"
            record.cause_scope = "engine_product"
            record.verdict = "FAIL"
            record.defects.append(f"assessment_exit_{assess.exit_code}")
            return record
        record.assessment_result = "pass"

        after = capture_source_inventory(workspace.clone_dir)
        source_ok, source_failures = verify_source_integrity(before, after)
        checkout_ok, checkout_detail = verify_checkout_unchanged(
            workspace.clone_dir, entry.qualified_revision.value
        )
        if not checkout_ok:
            record.source_integrity_verdict = f"fail:{checkout_detail}"
            record.failure_classification = "revision_mismatch"
            record.cause_scope = "engine_product"
            record.verdict = "FAIL"
            return record
        if not source_ok:
            # Filter dependency/build markers as integrity failures.
            record.source_integrity_verdict = f"fail:{','.join(source_failures[:8])}"
            record.failure_classification = "source_integrity_failure"
            record.cause_scope = "engine_product"
            record.verdict = "FAIL"
            record.defects.append("unexpected_source_mutation")
            return record
        record.source_integrity_verdict = "pass"

        run_dir = discover_run_dir(workspace.clone_dir)
        if run_dir is None:
            record.artifact_validation = "artifact_missing"
            record.failure_classification = "artifact_missing"
            record.cause_scope = "engine_product"
            record.verdict = "FAIL"
            return record

        artifact = validate_artifacts(run_dir)
        record.required_artifacts = artifact.get("required_artifacts") or {}
        record.optional_artifacts = artifact.get("optional_artifacts") or {}
        record.report_schema = artifact.get("report_schema")
        record.artifact_validation = str(artifact.get("artifact_validation"))
        record.traceability_validation = str(artifact.get("traceability_validation"))
        record.ai_executed = bool(artifact.get("ai_executed"))
        # Always preserve artifacts for diagnosis (even on validation failure).
        preserve_run_artifacts(
            run_dir,
            output_dir / "artifacts" / entry.repository_id / entry.qualified_revision.value[:12],
        )
        if artifact.get("details"):
            record.warnings.extend(str(d) for d in artifact["details"][:5])
        if artifact.get("artifact_validation") != "pass":
            classification = str(artifact.get("failure_classification") or "artifact_malformed")
            record.failure_classification = classification
            record.cause_scope = (
                "engine_product"
                if classification
                in {"schema_failure", "traceability_failure", "privacy_failure", "artifact_malformed"}
                else "repository_specific"
            )
            record.verdict = "FAIL"
            record.defects.append(classification)
            return record

        if limitations or str(entry.raw.get("candidate_category") or "") == "Known Issues":
            if str(entry.raw.get("candidate_category") or "") == "Known Issues":
                note = (
                    "Known Issues repository may surface secret-shaped finding content "
                    "from intentionally vulnerable source material"
                )
                if note not in record.limitations:
                    record.limitations.append(note)
            record.verdict = "PASS_WITH_LIMITATIONS"
        else:
            record.verdict = "PASS"
        return record
    except Exception as exc:  # noqa: BLE001
        record.verdict = "error"
        record.failure_classification = "infrastructure_or_harness_failure"
        record.cause_scope = "verification_harness"
        record.defects.append(type(exc).__name__)
        record.warnings.append(str(exc)[:200])
        return record
    finally:
        cleanup_workspace(workspace, keep=keep_workspace)


def run_tier(
    tier: str,
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    codestrata: Path | None = None,
    venv_dir: Path | None = None,
    keep_workspace: bool = False,
    repository_ids: Iterable[str] | None = None,
) -> tuple[list[RepositoryValidationResult], object]:
    engine = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or _default_output_dir(engine)).resolve()
    out.mkdir(parents=True, exist_ok=True)

    assert_readiness_pass(engine)
    entries = load_release_validation_entries(engine)
    if len(entries) != RELEASE_VALIDATION_TARGET:
        raise RuntimeError(
            f"expected {RELEASE_VALIDATION_TARGET} release_validation entries, found {len(entries)}"
        )
    batches = resolve_batches(entries)
    tier_entries = list(batches.get(tier, ()))
    if repository_ids is not None:
        wanted = set(repository_ids)
        tier_entries = [e for e in tier_entries if e.repository_id in wanted]

    disk = check_disk_for_tier(tier, path=out)
    if not disk.ok:
        raise RuntimeError(disk.detail)

    own_venv = False
    if codestrata is None or venv_dir is None:
        codestrata, venv_dir = install_codestrata_cli(engine)
        own_venv = True

    results: list[RepositoryValidationResult] = []
    try:
        for entry in tier_entries:
            result = _run_one_repository(
                entry,
                engine_root=engine,
                codestrata=codestrata,
                venv_dir=venv_dir,
                output_dir=out,
                keep_workspace=keep_workspace,
            )
            write_repository_record(result, out)
            results.append(result)
    finally:
        if own_venv and venv_dir is not None:
            cleanup_venv(venv_dir)

    disk_after = available_disk_gb(out)
    summary = build_tier_summary(
        tier,
        [e.repository_id for e in tier_entries],
        results,
        disk_before=disk.available_gb,
        disk_after=round(disk_after, 2),
        cleanup_ok=True,
    )
    write_tier_summary(summary, out)
    return results, summary


def run_determinism_samples(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    sample_ids: tuple[str, ...] | None = None,
    keep_workspace: bool = False,
) -> list[dict]:
    engine = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or _default_output_dir(engine)).resolve()
    entries = load_release_validation_entries(engine)
    batches = resolve_batches(entries)
    selected = sample_ids or select_determinism_sample(batches)
    by_id = {e.repository_id: e for e in entries}

    codestrata, venv_dir = install_codestrata_cli(engine)
    samples: list[dict] = []
    try:
        for repository_id in selected:
            entry = by_id[repository_id]
            first_artifact = out / "artifacts" / repository_id
            # Require a prior successful artifact from the main run.
            prior_dirs = sorted(first_artifact.glob("*")) if first_artifact.exists() else []
            if not prior_dirs:
                samples.append(
                    {
                        "repository_id": repository_id,
                        "ok": False,
                        "detail": "missing_prior_artifact_for_repeat",
                    }
                )
                continue
            prior_report = prior_dirs[-1] / "report.json"
            second = _run_one_repository(
                entry,
                engine_root=engine,
                codestrata=codestrata,
                venv_dir=venv_dir,
                output_dir=out / "determinism",
                keep_workspace=keep_workspace,
            )
            if second.verdict not in {"PASS", "PASS_WITH_LIMITATIONS"}:
                samples.append(
                    {
                        "repository_id": repository_id,
                        "ok": False,
                        "detail": f"repeat_verdict={second.verdict}",
                        "failure_classification": second.failure_classification,
                    }
                )
                continue
            repeat_dirs = sorted((out / "determinism" / "artifacts" / repository_id).glob("*"))
            if not repeat_dirs:
                samples.append(
                    {
                        "repository_id": repository_id,
                        "ok": False,
                        "detail": "missing_repeat_artifact",
                    }
                )
                continue
            comparison = compare_assessment_runs(prior_report, repeat_dirs[-1] / "report.json")
            samples.append(
                {
                    "repository_id": repository_id,
                    "ok": comparison.get("ok", False),
                    "detail": "normalized_comparison",
                    "comparison_ok": comparison.get("ok", False),
                }
            )
    finally:
        cleanup_venv(venv_dir)
    (out / "determinism-samples.json").write_text(
        json.dumps(samples, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return samples


def run_curated_repository_validation(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    tiers: tuple[str, ...] | None = None,
    keep_workspace: bool = False,
    run_determinism: bool = True,
    skip_readiness_gate: bool = False,
) -> object:
    engine = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or _default_output_dir(engine)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    contract = default_contract()

    if not skip_readiness_gate:
        readiness = assert_readiness_pass(engine)
    else:
        readiness = {}

    catalog = load_catalog_document(engine)
    entries = load_release_validation_entries(engine)
    selected_tiers = tiers or TIER_ORDER

    codestrata, venv_dir = install_codestrata_cli(engine)
    all_results: list[RepositoryValidationResult] = []
    tier_summaries = []
    blockers: list[str] = []
    defects: list[str] = []
    warnings: list[str] = [DATASET_DISCLAIMER]
    limitations: list[str] = list(contract.notes)

    try:
        for tier in selected_tiers:
            disk = check_disk_for_tier(tier, path=out)
            if not disk.ok:
                blockers.append(disk.detail)
                break
            results, summary = run_tier(
                tier,
                engine_root=engine,
                output_dir=out,
                codestrata=codestrata,
                venv_dir=venv_dir,
                keep_workspace=keep_workspace,
            )
            all_results.extend(results)
            tier_summaries.append(summary)
            for row in results:
                if row.cause_scope == "engine_product" and row.verdict not in {
                    "PASS",
                    "PASS_WITH_LIMITATIONS",
                }:
                    defects.extend(row.defects or [row.repository_id])
    finally:
        cleanup_venv(venv_dir)

    samples: list[dict] = []
    if run_determinism and not blockers:
        try:
            samples = run_determinism_samples(
                engine_root=engine,
                output_dir=out,
                keep_workspace=keep_workspace,
            )
            if any(not s.get("ok") for s in samples):
                warnings.append("determinism_sample_had_failures")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"determinism_sample_error:{type(exc).__name__}")
            blockers.append(f"determinism harness failure: {exc}")

    # Prefer records on disk if re-aggregating.
    if not all_results:
        for raw in list_repository_records(out):
            all_results.append(RepositoryValidationResult(**{
                k: raw.get(k)
                for k in RepositoryValidationResult.__dataclass_fields__
            }))

    report = build_final_report(
        catalog_id=catalog.get("catalog_id"),
        catalog_schema_version=catalog.get("schema_version"),
        target_count=RELEASE_VALIDATION_TARGET,
        tier_summaries=tier_summaries,
        records=all_results,
        determinism_samples=samples,
        defects=sorted(set(defects)),
        blockers=blockers,
        warnings=warnings,
        limitations=limitations,
    )
    report.write_json(out / "curated-repository-validation.json")
    return report
