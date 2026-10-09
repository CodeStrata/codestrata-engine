"""SV.5 HTML structure tests for the R2 baseline hierarchy."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from tests.application.incremental.git_repo_helpers import commit_all, init_repo
from verification.assessment_report.credibility import find_unsupported_claims
from verification.assessment_report.html_structure import check_html_structure
from verification.assessment_report.loaders import load_run_directory
from verification.assessment_report.models import CheckResult

from codestrata.application.assessment.canonical_records import seal_assess_canonical_records
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.r2_shell import (
    PRINT_CONTROL_SCRIPT,
    content_security_policy,
    script_source_hash,
)
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput
from codestrata.services.graph_assessment import GraphAssessmentPipeline

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "journeys"
_PINNED = datetime(2026, 9, 27, tzinfo=UTC)
_SECTIONS = (
    ("attention-first", "What deserves attention now"),
    ("assessment-results", "Current outcomes"),
    ("architecture-map", "Architecture Map"),
    ("engineering-hotspots", "Engineering Hotspots"),
    ("ownership-concentration", "Ownership concentration"),
    ("temporal-co-change", "Temporal co-change"),
    ("priority-actions", "Priority Actions"),
    ("coverage-and-trust", "Coverage & Trust"),
    ("technical-appendix", "Technical Appendix"),
)
_CAPABILITY_LABELS = (
    "m16.function",
    "m24.file_churn",
    "component.mapping",
    "m25.repository",
)


def test_claim_matcher_disclaimer_aware() -> None:
    assert not find_unsupported_claims("does not claim production ready status")
    assert find_unsupported_claims("The system is production ready today.")


def test_production_renderer_passes_structure_and_closes_evidence_links(tmp_path: Path) -> None:
    html = _production_html(tmp_path)
    checks = _checks(tmp_path / "run", html)
    failed = [f"{name}: {item.detail}" for name, item in checks.items() if not item.ok]
    assert failed == []
    assert checks["html:section_order"].detail.startswith("attention-first→")
    assert "leadership-verdict" not in checks["html:section_order"].detail
    for label in _CAPABILITY_LABELS:
        assert f'href="#evidence-{label}"' not in html
        assert f"{label} (evidence not attached)" in html
        assert f'id="evidence-{label}"' not in html


def test_external_script_is_rejected(tmp_path: Path) -> None:
    html = _document(
        script='<script src="https://cdn.example/app.js"></script>',
        csp="script-src 'none'",
    )
    checks = _checks(tmp_path, html)
    assert checks["html:no_external_script"].ok is False
    assert checks["html:csp_present"].ok is False


def test_tampered_script_body_is_rejected(tmp_path: Path) -> None:
    body = PRINT_CONTROL_SCRIPT + "/* extra */"
    digest = script_source_hash(body)
    html = _document(script=f"<script>{body}</script>", csp=f"script-src 'sha256-{digest}'")
    checks = _checks(tmp_path, html)
    assert checks["html:no_external_script"].ok is False
    assert checks["html:csp_present"].ok is False


def test_missing_and_mismatched_script_hashes_are_rejected(tmp_path: Path) -> None:
    tagged = f"<script>{PRINT_CONTROL_SCRIPT}</script>"
    missing = _checks(tmp_path / "missing", _document(script=tagged, csp="script-src 'none'"))
    wrong_hash = "script-src 'sha256-" + ("A" * 43) + "='"
    mismatched = _checks(
        tmp_path / "mismatched",
        _document(script=tagged, csp=wrong_hash),
    )
    assert missing["html:csp_present"].ok is False
    assert mismatched["html:csp_present"].ok is False
    assert missing["html:no_external_script"].ok is True


def test_unsafe_script_policy_and_inline_handler_are_rejected(tmp_path: Path) -> None:
    tagged = f"<script>{PRINT_CONTROL_SCRIPT}</script>"
    approved = f"script-src 'sha256-{script_source_hash(PRINT_CONTROL_SCRIPT)}'"
    unsafe = _checks(
        tmp_path / "unsafe",
        _document(script=tagged, csp=approved + " 'unsafe-inline'"),
    )
    handler = _checks(
        tmp_path / "handler",
        _document(
            script=tagged,
            csp=approved,
            extra='<button onclick="window.print()">Print</button>',
        ),
    )
    assert unsafe["html:csp_present"].ok is False
    assert handler["html:no_inline_event_handlers"].ok is False


def test_incorrect_section_order_and_broken_evidence_link_are_rejected(tmp_path: Path) -> None:
    sections = list(_SECTIONS)
    sections[0], sections[1] = sections[1], sections[0]
    html = _document(extra='<a href="#evidence-missing">missing</a>', sections=tuple(sections))
    checks = _checks(tmp_path, html)
    assert checks["html:section_order"].ok is False
    assert checks["html:internal_hrefs_resolve"].ok is False
    assert checks["html:unique_ids"].ok is True


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    html = _document(extra='<section id="attention-first"></section>')
    checks = _checks(tmp_path, html)
    assert checks["html:unique_ids"].ok is False


def _production_html(tmp_path: Path) -> str:
    repo = tmp_path / "complete-js"
    shutil.copytree(_EXAMPLES / "complete-js", repo)
    init_repo(repo)
    commit_all(repo, "pin fixture")
    analysis = seal_assess_canonical_records(
        AnalysisResult(
            repository=Repository(name="complete-js", path=repo, files=["src/app.js"]),
        ),
        repository_root=repo,
        evaluation_time=_PINNED,
    )
    graph = GraphAssessmentPipeline().run(
        Repository(name="complete-js", path=repo, files=["src/app.js"], total_files=1)
    )
    analysis.metadata["canonical_graph"] = graph.repository_graph.snapshot.model_dump(mode="json")
    document = build_html_report_view_model(
        ModernizationReportInput(
            analysis_result=analysis,
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=_PINNED,
        )
    )
    return HtmlReportRenderer().render(document)


def _document(
    *,
    script: str | None = None,
    csp: str | None = None,
    extra: str = "",
    sections: tuple[tuple[str, str], ...] = _SECTIONS,
) -> str:
    if script is None:
        script = f"<script>{PRINT_CONTROL_SCRIPT}</script>"
    if csp is None:
        policy = content_security_policy(PRINT_CONTROL_SCRIPT)
    else:
        policy = f"default-src 'none'; {csp}; style-src 'unsafe-inline'"
    body = "".join(f'<section id="{sid}"><h2>{title}</h2></section>' for sid, title in sections)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta http-equiv="Content-Security-Policy" content="{policy}">
<style>@media print {{ .x {{ display:none }} }}</style>
</head><body>
<h1>Current-code baseline</h1>
<a href="#attention-first">Skip</a>
{body}
{extra}
{script}
</body></html>"""


def _checks(root: Path, html: str) -> dict[str, CheckResult]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "report.html").write_text(html, encoding="utf-8")
    for name, payload in (
        ("report.json", {"schema_version": "1.2", "assessment": {}}),
        ("findings.json", {"findings": []}),
        ("recommendations.json", {"recommendations": []}),
    ):
        (root / name).write_text(json.dumps(payload), encoding="utf-8")
    run = load_run_directory(
        root, run_id="t", source="local_fixture", assessment_run_reference="runs/t"
    )
    return {item.name: item for item in check_html_structure(run)}
