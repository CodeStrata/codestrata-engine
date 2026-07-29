"""MVP acceptance orchestration service (Phase 5.13)."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from codestrata.application.acceptance.models import (
    AcceptanceCheckResult,
    AcceptanceHarnessResult,
    RepositoryAcceptanceResult,
)
from codestrata.application.acceptance.qa import mcp_health_passed, questions_passed
from codestrata.application.acceptance.settings import build_acceptance_settings
from codestrata.application.acceptance.summary import write_acceptance_summaries
from codestrata.application.acceptance.targets import (
    ACCEPTANCE_TARGETS,
    LIVE_DETERMINISM_EXTRA_PATHS,
)
from codestrata.application.onboarding import OnboardingApplicationService
from codestrata.application.report_validation import validate_report_json
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.onboarding.errors import OnboardingError
from codestrata.extensions import load_acceptance_rag_helpers
from codestrata.reporting.contract.canonical import strip_volatile_fields
from codestrata.reporting.modernization_models import AssessmentMode


class MvpAcceptanceService:
    """Run live MVP acceptance against configured dogfood repositories."""

    def __init__(
        self,
        *,
        onboard_service: OnboardingApplicationService | None = None,
    ) -> None:
        self._onboard = onboard_service or OnboardingApplicationService()

    def run(
        self,
        *,
        output_directory: Path,
        config_path: Path = Path("codestrata.toml"),
        repositories: tuple[str, ...] | None = None,
        settings: CodestrataSettings | None = None,
    ) -> AcceptanceHarnessResult:
        """Execute acceptance for selected repositories and write summaries."""

        started = perf_counter()
        output_directory.mkdir(parents=True, exist_ok=True)
        selected = self._resolve_targets(repositories)
        results: list[RepositoryAcceptanceResult] = []
        for label, path in selected:
            results.append(
                self._run_repository(
                    label=label,
                    repository_path=path,
                    output_directory=output_directory,
                    config_path=config_path,
                    base_settings=settings,
                )
            )
        ok = all(not item.skipped and item.ok for item in results) and bool(results)
        failures = [
            f"{item.repository}: {item.failure_reason}"
            for item in results
            if not item.ok and not item.skipped
        ]
        harness = AcceptanceHarnessResult(
            ok=ok,
            repositories=tuple(results),
            elapsed_ms=(perf_counter() - started) * 1000.0,
            output_directory=str(output_directory),
            failure_reason="; ".join(failures) if failures else None,
        )
        write_acceptance_summaries(harness, output_directory)
        return harness

    def _resolve_targets(self, repositories: tuple[str, ...] | None) -> list[tuple[str, Path]]:
        if not repositories:
            return list(ACCEPTANCE_TARGETS)
        wanted = {name.strip().lower() for name in repositories}
        matched = [(label, path) for label, path in ACCEPTANCE_TARGETS if label in wanted]
        unknown = wanted - {label for label, _ in matched}
        if unknown:
            raise ValueError(
                "Unknown acceptance repository id(s): "
                + ", ".join(sorted(unknown))
                + ". Known: "
                + ", ".join(label for label, _ in ACCEPTANCE_TARGETS)
            )
        return matched

    def _run_repository(
        self,
        *,
        label: str,
        repository_path: Path,
        output_directory: Path,
        config_path: Path,
        base_settings: CodestrataSettings | None,
    ) -> RepositoryAcceptanceResult:
        started = perf_counter()
        checks: list[AcceptanceCheckResult] = []
        if not repository_path.is_dir():
            return RepositoryAcceptanceResult(
                repository=label,
                repository_path=str(repository_path),
                skipped=True,
                ok=False,
                onboarding_status="skipped",
                failure_reason=f"repository path missing: {repository_path}",
                elapsed_ms=(perf_counter() - started) * 1000.0,
                checks=(
                    AcceptanceCheckResult(
                        name="repository_present",
                        ok=False,
                        detail=f"missing {repository_path}",
                    ),
                ),
            )

        work_root = output_directory / label
        reports_root = work_root / "reports"
        work_root.mkdir(parents=True, exist_ok=True)
        acceptance_settings = build_acceptance_settings(
            repository_path=repository_path,
            work_root=work_root,
            config_path=config_path,
            base=base_settings,
        )

        # --- 1. Live onboard ---
        try:
            first = self._onboard.onboard(
                str(repository_path),
                config_path=config_path,
                output_directory=reports_root,
                settings=acceptance_settings,
                provider="deterministic",
                mode=AssessmentMode.DETERMINISTIC,
            )
            onboard_ok = first.status.value == "succeeded"
            checks.append(
                AcceptanceCheckResult(
                    name="onboarding",
                    ok=onboard_ok,
                    detail=first.status.value,
                )
            )
        except (OnboardingError, Exception) as error:  # noqa: BLE001
            return RepositoryAcceptanceResult(
                repository=label,
                repository_path=str(repository_path),
                onboarding_status="failed",
                ok=False,
                failure_reason=f"onboarding failed: {error}",
                elapsed_ms=(perf_counter() - started) * 1000.0,
                checks=(
                    AcceptanceCheckResult(
                        name="onboarding",
                        ok=False,
                        detail=str(error),
                    ),
                ),
            )

        json_report = (
            Path(first.manifest.json_report_path) if first.manifest.json_report_path else None
        )
        html_report = (
            Path(first.manifest.html_report_path) if first.manifest.html_report_path else None
        )
        if json_report is None or html_report is None:
            for candidate in first.summary.reports_generated:
                if candidate.endswith("report.json") and json_report is None:
                    json_report = Path(candidate)
                elif candidate.endswith("report.html") and html_report is None:
                    html_report = Path(candidate)

        findings = first.summary.findings_count
        recommendations = first.summary.recommendations_count
        roadmap = first.summary.roadmap_initiative_count
        chunks = first.summary.chunks_indexed
        languages = tuple(first.summary.languages_detected)
        frameworks = tuple(first.summary.frameworks_detected)

        # --- 2. Report validate ---
        validation_label = "not_run"
        if json_report is None or not json_report.is_file():
            checks.append(
                AcceptanceCheckResult(
                    name="report_json",
                    ok=False,
                    detail="report.json missing",
                )
            )
            validation_label = "missing"
        else:
            validation = validate_report_json(json_report)
            validation_label = "pass" if validation.ok else "fail"
            checks.append(
                AcceptanceCheckResult(
                    name="report_validation",
                    ok=validation.ok,
                    detail=f"issues={len(validation.issues)}",
                )
            )

        # --- 3. HTML exists ---
        html_ok = html_report is not None and html_report.is_file()
        checks.append(
            AcceptanceCheckResult(
                name="html_report",
                ok=html_ok,
                detail=str(html_report) if html_report else "missing",
            )
        )

        # --- 4. Artifact counts ---
        artifacts_ok = chunks > 0
        checks.append(
            AcceptanceCheckResult(
                name="artifacts",
                ok=artifacts_ok,
                detail=(
                    f"findings={findings} recommendations={recommendations} "
                    f"roadmap={roadmap} chunks={chunks}"
                ),
                metadata={
                    "findings": findings,
                    "recommendations": recommendations,
                    "roadmap_initiatives": roadmap,
                    "chunks": chunks,
                },
            )
        )
        # Evidence presence in report when findings exist.
        if json_report and json_report.is_file() and findings > 0:
            document = json.loads(json_report.read_text(encoding="utf-8"))
            report_findings = document.get("assessment", {}).get("findings") or []
            evidence_ok = any(
                isinstance(item, dict) and (item.get("evidence") or []) for item in report_findings
            )
            checks.append(
                AcceptanceCheckResult(
                    name="evidence",
                    ok=evidence_ok,
                    detail="finding evidence present" if evidence_ok else "no evidence",
                )
            )

        # --- 5. Grounded questions (Platform RAG when installed) ---
        qa_label = "not_run"
        vector_store = None
        answer_engine = None
        answer_provider = None
        rag = load_acceptance_rag_helpers()
        run_dir = Path(first.manifest.run_directory) if first.manifest.run_directory else None
        if rag is None:
            checks.append(
                AcceptanceCheckResult(
                    name="question_answer",
                    ok=True,
                    detail="skipped (Platform RAG not installed)",
                    metadata={"skipped": True},
                )
            )
            qa_label = "skipped"
        else:
            corpus = rag.load_corpus_from_run(run_dir) if run_dir else None
            repo_id = first.manifest.repository_id
            scan_id = first.manifest.scan_id
            if corpus is None:
                checks.append(
                    AcceptanceCheckResult(
                        name="question_answer",
                        ok=False,
                        detail="knowledge corpus artifact missing",
                    )
                )
                qa_label = "missing_corpus"
            else:
                try:
                    answer_engine, scope, vector_store, answer_provider = rag.build_answer_stack(
                        corpus,
                        repository_id=repo_id,
                        scan_id=scan_id,
                        settings=acceptance_settings,
                    )
                    rows = rag.ask_predefined_questions(answer_engine, scope)
                    qa_ok, qa_detail = questions_passed(rows)
                    qa_label = "pass" if qa_ok else "fail"
                    checks.append(
                        AcceptanceCheckResult(
                            name="question_answer",
                            ok=qa_ok,
                            detail=qa_detail,
                            metadata={"answers": rows},
                        )
                    )
                    (work_root / "questions.json").write_text(
                        json.dumps(rows, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                except Exception as error:  # noqa: BLE001
                    qa_label = "error"
                    checks.append(
                        AcceptanceCheckResult(
                            name="question_answer",
                            ok=False,
                            detail=str(error),
                        )
                    )

        # --- 6. MCP health ---
        mcp_label = "not_run"
        if rag is None:
            checks.append(
                AcceptanceCheckResult(
                    name="mcp_health",
                    ok=True,
                    detail="skipped (Platform RAG not installed)",
                    metadata={"skipped": True},
                )
            )
            mcp_label = "skipped"
        else:
            try:
                health_payload = rag.mcp_health_check(
                    acceptance_settings,
                    vector_store=vector_store,
                    answer_engine=answer_engine,
                    answer_provider=answer_provider,
                )
                mcp_ok, mcp_detail = mcp_health_passed(health_payload)
                mcp_label = "pass" if mcp_ok else "fail"
                checks.append(
                    AcceptanceCheckResult(
                        name="mcp_health",
                        ok=mcp_ok,
                        detail=mcp_detail,
                        metadata={"health": health_payload},
                    )
                )
                (work_root / "mcp-health.json").write_text(
                    json.dumps(health_payload, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8",
                )
            except Exception as error:  # noqa: BLE001
                mcp_label = "error"
                checks.append(
                    AcceptanceCheckResult(
                        name="mcp_health",
                        ok=False,
                        detail=str(error),
                    )
                )

        # --- 7. Repeated onboard + determinism ---
        determinism_label = "not_run"
        try:
            second = self._onboard.onboard(
                str(repository_path),
                config_path=config_path,
                output_directory=reports_root / "repeat",
                settings=acceptance_settings,
                provider="deterministic",
                force_reindex=True,
                mode=AssessmentMode.DETERMINISTIC,
            )
            second_json = (
                Path(second.manifest.json_report_path) if second.manifest.json_report_path else None
            )
            if second_json is None:
                for candidate in second.summary.reports_generated:
                    if candidate.endswith("report.json"):
                        second_json = Path(candidate)
            if json_report is None or second_json is None:
                determinism_label = "missing_report"
                det_ok = False
                detail = "missing report.json for comparison"
            else:
                left = json.loads(json_report.read_text(encoding="utf-8"))
                right = json.loads(second_json.read_text(encoding="utf-8"))
                det_ok = _reports_live_equal(left, right)
                determinism_label = "pass" if det_ok else "fail"
                detail = "structurally equal" if det_ok else "structural drift"
            checks.append(
                AcceptanceCheckResult(
                    name="determinism",
                    ok=det_ok,
                    detail=detail,
                )
            )
        except Exception as error:  # noqa: BLE001
            determinism_label = "error"
            checks.append(
                AcceptanceCheckResult(
                    name="determinism",
                    ok=False,
                    detail=str(error),
                )
            )

        failed = [item for item in checks if not item.ok]
        ok = not failed and first.status.value == "succeeded"
        failure_reason = None
        if failed:
            failure_reason = "; ".join(f"{item.name}: {item.detail}" for item in failed)

        return RepositoryAcceptanceResult(
            repository=label,
            repository_path=str(repository_path),
            languages=languages,
            frameworks=frameworks,
            onboarding_status=first.status.value,
            findings=findings,
            recommendations=recommendations,
            roadmap_initiatives=roadmap,
            chunks=chunks,
            report_validation=validation_label,
            question_answer=qa_label,
            mcp_health=mcp_label,
            determinism=determinism_label,
            elapsed_ms=(perf_counter() - started) * 1000.0,
            ok=ok,
            failure_reason=failure_reason,
            checks=tuple(checks),
            json_report_path=str(json_report) if json_report else None,
            html_report_path=str(html_report) if html_report else None,
            run_directory=first.manifest.run_directory,
        )


def _reports_live_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return strip_volatile_fields(
        left, extra_paths=LIVE_DETERMINISM_EXTRA_PATHS
    ) == strip_volatile_fields(right, extra_paths=LIVE_DETERMINISM_EXTRA_PATHS)


def run_mvp_acceptance(
    *,
    output_directory: Path,
    config_path: Path = Path("codestrata.toml"),
    repositories: tuple[str, ...] | None = None,
    settings: CodestrataSettings | None = None,
) -> AcceptanceHarnessResult:
    """Module-level entry for scripts and CLI."""

    return MvpAcceptanceService().run(
        output_directory=output_directory,
        config_path=config_path,
        repositories=repositories,
        settings=settings,
    )
