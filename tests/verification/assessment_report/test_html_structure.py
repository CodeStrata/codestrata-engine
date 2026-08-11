"""SV.5 HTML structure tests."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.reporting.html_v2.renderer import CONTENT_SECURITY_POLICY
from verification.assessment_report.credibility import find_unsupported_claims
from verification.assessment_report.html_structure import check_html_structure
from verification.assessment_report.loaders import load_run_directory


def test_html_structure_checks(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">
<style>@media print {{ .x {{ display:none }} }}</style>
</head><body>
<a href="#contents">Skip</a>
<div id="cover"></div>
<div id="contents"></div>
<section id="leadership-verdict"><h2>Leadership Verdict</h2></section>
<section id="executive-summary"><h2>Executive Summary</h2></section>
<section id="engineering-intelligence-summary"><h2>EIS</h2></section>
<section id="key-takeaways"><h2>Key Takeaways</h2></section>
<section id="priority-actions"><h2>Priority Actions</h2></section>
<section id="engineering-risks"><h2>Engineering Risks</h2></section>
<section id="assessment-results"><h1>Assessment Results</h1>
<div data-canonical="coverage-confidence-limitations" class="assessment-ccl"></div>
</section>
<section id="phased-modernization-plan"><h2>Roadmap</h2></section>
<section id="technical-appendix"><h2>Appendix</h2></section>
</body></html>"""
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
    checks = {c.name: c for c in check_html_structure(run)}
    assert checks["html:doctype"].ok
    assert checks["html:csp_present"].ok
    assert checks["html:print_css"].ok
    assert checks["html:section_order"].ok
    assert checks["html:unique_ids"].ok
    assert checks["html:internal_hrefs_resolve"].ok


def test_claim_matcher_disclaimer_aware() -> None:
    assert not find_unsupported_claims("does not claim production ready status")
    assert find_unsupported_claims("The system is production ready today.")
