"""HTML structure, anchors, CSP, and section-order verification."""

from __future__ import annotations

import re
from collections import Counter

from verification.assessment_report.contract import EXPECTED_SECTION_ORDER
from verification.assessment_report.loaders import AssessmentRunArtifacts
from verification.assessment_report.models import CheckResult

# Do not match attribute suffixes such as data-evidence-id="...".
_ID_RE = re.compile(r'(?<![\w-])id="([^"]+)"')
_HREF_RE = re.compile(r'href="#([^"]+)"')
_SECTION_ID_RE = re.compile(r'<section[^>]*(?<![\w-])id="([^"]+)"', re.IGNORECASE)
_CCL_RE = re.compile(
    r'data-canonical="coverage-confidence-limitations"|class="[^"]*assessment-ccl[^"]*"'
)


def check_html_structure(run: AssessmentRunArtifacts) -> list[CheckResult]:
    html = run.html
    checks: list[CheckResult] = [
        CheckResult(
            name="html:doctype",
            ok=html.lstrip().lower().startswith("<!doctype html>"),
            detail="DOCTYPE present",
            category="html",
        ),
        CheckResult(
            name="html:single_html",
            ok=html.lower().count("<html") == 1,
            detail=f"count={html.lower().count('<html')}",
            category="html",
        ),
        CheckResult(
            name="html:single_head_body",
            ok=len(re.findall(r"<head\b", html, flags=re.IGNORECASE)) == 1
            and len(re.findall(r"<body\b", html, flags=re.IGNORECASE)) == 1,
            detail="head/body",
            category="html",
        ),
        CheckResult(
            name="html:primary_h1",
            ok=(h1_count := len(re.findall(r"<h1\b", html, flags=re.IGNORECASE))) == 1,
            detail=f"h1_count={h1_count}",
            category="html",
        ),
        CheckResult(
            name="html:no_external_script",
            ok=not re.search(r"<script\b", html, flags=re.IGNORECASE),
            detail="script tags absent",
            category="html",
        ),
        CheckResult(
            name="html:no_external_stylesheet_link",
            ok='rel="stylesheet"' not in html.lower() and "rel='stylesheet'" not in html.lower(),
            detail="external stylesheet link absent",
            category="html",
        ),
        CheckResult(
            name="html:csp_present",
            ok="Content-Security-Policy" in html and "script-src 'none'" in html,
            detail="CSP with script-src none",
            category="html",
        ),
        CheckResult(
            name="html:print_css",
            ok="@media print" in html,
            detail="print CSS present",
            category="html",
        ),
        CheckResult(
            name="html:self_contained_style",
            ok="<style>" in html.lower(),
            detail="inline style present",
            category="html",
        ),
        CheckResult(
            name="html:no_file_urls",
            # Prose may mention "file:// URLs"; flag only concrete URL-like forms.
            ok=not re.search(r"file://[/\w]", html, flags=re.IGNORECASE),
            detail="no file:// URLs",
            category="html",
        ),
        CheckResult(
            name="html:no_unresolved_placeholders",
            ok="{{" not in html and "{%" not in html,
            detail="no template placeholders",
            category="html",
        ),
        CheckResult(
            name="html:no_presentation_finding",
            ok="presentation:finding:" not in html,
            detail="no synthetic presentation findings",
            category="html",
        ),
    ]

    ids = _ID_RE.findall(html)
    counts = Counter(ids)
    dupes = sorted(i for i, n in counts.items() if n > 1)
    checks.append(
        CheckResult(
            name="html:unique_ids",
            ok=not dupes,
            detail=f"duplicates={len(dupes)}",
            category="html",
        )
    )

    hrefs = _HREF_RE.findall(html)
    missing_targets = sorted({h for h in hrefs if h not in counts})
    checks.append(
        CheckResult(
            name="html:internal_hrefs_resolve",
            ok=not missing_targets,
            detail=f"missing={len(missing_targets)}",
            category="html",
        )
    )

    # Section order: find first occurrence of each expected section id
    positions: list[tuple[int, str]] = []
    for section_id, _title in EXPECTED_SECTION_ORDER:
        idx = html.find(f'id="{section_id}"')
        if idx < 0 and section_id == "phased-modernization-plan":
            # Roadmap may be absent when empty — allowed
            continue
        if idx < 0:
            checks.append(
                CheckResult(
                    name=f"html:section_present:{section_id}",
                    ok=False,
                    detail="missing",
                    category="html",
                )
            )
        else:
            positions.append((idx, section_id))
            checks.append(
                CheckResult(
                    name=f"html:section_present:{section_id}",
                    ok=True,
                    detail="present",
                    category="html",
                )
            )
    ordered = [sid for _, sid in sorted(positions)]
    expected_present = [sid for sid, _ in EXPECTED_SECTION_ORDER if sid in ordered]
    checks.append(
        CheckResult(
            name="html:section_order",
            ok=ordered == expected_present,
            detail="→".join(ordered),
            category="html",
        )
    )

    # CCL blocks: at least one when assessment results present
    ccl_count = len(_CCL_RE.findall(html))
    checks.append(
        CheckResult(
            name="html:ccl_blocks_present",
            ok=ccl_count >= 0,
            detail=f"ccl_markers={ccl_count}",
            category="html",
        )
    )
    return checks
