"""SV.5 assessment report verification runner."""

from __future__ import annotations

import time
from pathlib import Path

from verification.assessment_report.artifact_parity import (
    check_artifact_inventory,
    check_artifact_parity,
    inventory_artifacts,
)
from verification.assessment_report.contract import (
    ReportVerificationContract,
    default_contract,
)
from verification.assessment_report.credibility import check_credibility
from verification.assessment_report.determinism import check_determinism
from verification.assessment_report.findings_json import check_findings_json
from verification.assessment_report.html_structure import check_html_structure
from verification.assessment_report.inputs import PreparedRun, prepare_assessment_inputs
from verification.assessment_report.loaders import AssessmentRunArtifacts, load_run_directory
from verification.assessment_report.models import RunVerification, VerificationReport
from verification.assessment_report.recommendations_json import check_recommendations_json
from verification.assessment_report.report_json import bounded_counts, check_report_json
from verification.assessment_report.reporting import report_contains_forbidden_leak
from verification.assessment_report.scenarios import check_negative_scenarios
from verification.assessment_report.traceability import check_traceability
from verification.cli_installation.environment import engine_root_from_package


def _verify_run(run: AssessmentRunArtifacts) -> RunVerification:
    structural = (
        check_artifact_inventory(run)
        + check_report_json(run)
        + check_findings_json(run)
        + check_recommendations_json(run)
    )
    trace = check_traceability(run)
    parity = check_artifact_parity(run)
    html = check_html_structure(run)
    credibility = check_credibility(run)
    privacy = [c for c in credibility if c.category == "privacy"]
    credibility = [c for c in credibility if c.category != "privacy"]

    all_checks = structural + trace + parity + html + credibility + privacy
    failures = [f"{c.name}:{c.detail}" for c in all_checks if not c.ok]
    assessment = run.report.get("assessment") if isinstance(run.report.get("assessment"), dict) else {}
    schema = str(run.report.get("schema_version") or assessment.get("schema_version") or "")

    return RunVerification(
        run_id=run.run_id,
        source=run.source,
        repository_id=run.repository_id,
        project_name=run.project_name,
        github_repository=run.github_repository,
        qualified_revision_type=run.qualified_revision_type,
        qualified_revision_value=run.qualified_revision_value,
        assessment_run_reference=run.assessment_run_reference,
        ok=not failures,
        artifact_inventory=inventory_artifacts(run),
        report_schema_version=schema,
        structural_checks=tuple(structural),
        traceability_checks=tuple(trace),
        parity_checks=tuple(parity),
        html_checks=tuple(html),
        credibility_checks=tuple(credibility),
        determinism_checks=(),
        privacy_checks=tuple(privacy),
        counts=bounded_counts(run),
        failures=tuple(failures),
    )


def _load_prepared(prepared: PreparedRun) -> AssessmentRunArtifacts:
    return load_run_directory(
        prepared.run_directory,
        run_id=prepared.label,
        source=prepared.source,
        assessment_run_reference=prepared.assessment_run_reference,
        repository_id=prepared.repository_id,
        project_name=prepared.project_name,
        github_repository=prepared.github_repository,
        qualified_revision_type=prepared.qualified_revision_type,
        qualified_revision_value=prepared.qualified_revision_value,
    )


def _with_determinism(
    item: RunVerification,
    det: list,
) -> RunVerification:
    failures = list(item.failures)
    failures.extend(f"{c.name}:{c.detail}" for c in det if not c.ok)
    return RunVerification(
        run_id=item.run_id,
        source=item.source,
        repository_id=item.repository_id,
        project_name=item.project_name,
        github_repository=item.github_repository,
        qualified_revision_type=item.qualified_revision_type,
        qualified_revision_value=item.qualified_revision_value,
        assessment_run_reference=item.assessment_run_reference,
        ok=item.ok and all(c.ok for c in det),
        artifact_inventory=item.artifact_inventory,
        report_schema_version=item.report_schema_version,
        structural_checks=item.structural_checks,
        traceability_checks=item.traceability_checks,
        parity_checks=item.parity_checks,
        html_checks=item.html_checks,
        credibility_checks=item.credibility_checks,
        determinism_checks=tuple(det),
        privacy_checks=item.privacy_checks,
        counts=item.counts,
        failures=tuple(failures),
        warnings=item.warnings,
        limitations=item.limitations,
    )


def run_assessment_report_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    local_only: bool = False,
    with_catalog_network: bool = False,
    keep_output: bool = True,
    artifact_dirs: list[Path] | None = None,
    contract: ReportVerificationContract | None = None,
) -> VerificationReport:
    started = time.perf_counter()
    contract = contract or default_contract()
    engine_root = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or (engine_root / "reports" / "verification")).resolve()
    out.mkdir(parents=True, exist_ok=True)

    limitations: list[str] = list(contract.notes)
    defects: list[str] = []
    warnings: list[str] = []
    run_results: list[RunVerification] = []
    loaded: list[AssessmentRunArtifacts] = []

    if artifact_dirs:
        for idx, path in enumerate(artifact_dirs):
            prepared = PreparedRun(
                label=path.name or f"artifact-{idx}",
                source="provided",
                run_directory=path,
                assessment_run_reference=f"provided/{path.name}",
            )
            art = _load_prepared(prepared)
            loaded.append(art)
            run_results.append(_verify_run(art))
    else:
        prepared_list, _work_root = prepare_assessment_inputs(
            engine_root=engine_root,
            work_root=out / "assessment-report-runs",
            local_only=local_only,
            with_catalog_network=with_catalog_network and not local_only,
            keep_output=keep_output,
        )
        if local_only:
            limitations.append(
                "catalog-backed CleanArchitecture report skipped (--local-only)"
            )
        for prepared in prepared_list:
            art = _load_prepared(prepared)
            loaded.append(art)
            if prepared.source == "local_fixture_repeat":
                continue
            run_results.append(_verify_run(art))

        primary = next((a for a in loaded if a.source == "local_fixture"), None)
        repeat = next((a for a in loaded if a.source == "local_fixture_repeat"), None)
        if primary is not None and repeat is not None:
            det = check_determinism(primary, repeat)
            run_results = [
                _with_determinism(item, det)
                if item.source == "local_fixture" and item.run_id == primary.run_id
                else item
                for item in run_results
            ]

    negatives = check_negative_scenarios()
    for item in run_results:
        if not item.ok:
            defects.extend(item.failures)
    defects.extend(f"{c.name}:{c.detail}" for c in negatives if not c.ok)

    ok = (
        not defects
        and all(item.ok for item in run_results)
        and all(c.ok for c in negatives)
    )
    report = VerificationReport(
        ok=ok,
        verdict="pass" if ok else "fail",
        runs=tuple(run_results),
        negative_scenarios=tuple(negatives),
        defects=tuple(defects),
        warnings=tuple(warnings),
        limitations=tuple(dict.fromkeys(limitations)),
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )
    leaks = report_contains_forbidden_leak(report.to_dict())
    if leaks:
        report = VerificationReport(
            ok=False,
            verdict="fail_privacy_leak",
            runs=tuple(run_results),
            negative_scenarios=tuple(negatives),
            defects=tuple([*defects, f"privacy_leak:{','.join(leaks)}"]),
            warnings=tuple(warnings),
            limitations=tuple(dict.fromkeys(limitations)),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
    report.write_json(out / "assessment-report-verification.json")
    return report
