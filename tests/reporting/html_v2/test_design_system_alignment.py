"""Design-system alignment contracts for Engineering Assessment HTML reports."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from tests.reporting.html_v2.test_html_report_v2 import _report_input

from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.styles import (
    AUTHORITATIVE_SELECTORS,
    REPORT_CSS,
    css_without_print,
)


def _top_level_selector_count(css: str, selector: str) -> int:
    """Count unindented selector openings (authoritative component rules)."""

    return len(re.findall(rf"(?m)^{re.escape(selector)}", css))


def test_report_css_has_single_authoritative_core_selectors() -> None:
    screen = css_without_print(REPORT_CSS)
    for selector in AUTHORITATIVE_SELECTORS:
        count = _top_level_selector_count(screen, selector)
        assert count == 1, f"{selector!r} top-level count={count}"
    assert "Fraunces" not in REPORT_CSS
    assert "var(--cs-font-display)" in REPORT_CSS
    assert "var(--cs-font-mono)" in REPORT_CSS
    assert "--cs-bg:" in REPORT_CSS
    assert "@media print" in REPORT_CSS


def test_report_css_styles_domain_legacy_primitives() -> None:
    assert ".metric-grid, .grid {" in REPORT_CSS
    assert ".metric-card, .grid > .card {" in REPORT_CSS
    assert ".label {" in REPORT_CSS
    assert ".value {" in REPORT_CSS
    assert ".status-badge {" in REPORT_CSS
    assert ".table-wrap, .table-wrapper, .responsive-table {" in REPORT_CSS
    assert "overflow-wrap: anywhere" in REPORT_CSS
    assert ".conclusion-card {" in REPORT_CSS
    assert ".recommendation-card {" in REPORT_CSS


def test_generated_html_embeds_tokens_and_keeps_csp_offline(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(build_html_report_view_model(_report_input(tmp_path)))
    assert "Fraunces" not in html
    assert "--cs-bg:" in html
    assert "var(--cs-font-display)" in html
    assert 'class="brand-name"' not in html
    assert "Community Edition" in html
    assert "table-wrap" in html or "responsive-table" in html
    assert html.count('id="cover"') == 1
    # Finding/recommendation cards may appear in overview + appendix with shared
    # deep-link anchors (pre-existing). Structural section ids must stay unique.
    structural_ids = [
        item
        for item in re.findall(r'(?<![\w-])id="([^"]+)"', html)
        if not item.startswith(("finding-", "recommendation-"))
    ]
    dupes = [item for item, count in Counter(structural_ids).items() if count > 1]
    assert not dupes, f"duplicate structural ids: {dupes}"
    assert "<script" not in html.lower()
    assert "Content-Security-Policy" in html
    assert "font-src 'none'" in html
    assert "script-src 'none'" in html
    assert "@media print" in html
    # Standalone favicon only (data URI); no external stylesheets.
    assert html.lower().count("<link ") == 1
    assert 'rel="icon"' in html
    assert "data:image/png;base64," in html


def test_ai_variant_also_uses_design_system_css(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(
        build_html_report_view_model(_report_input(tmp_path, with_ai=True))
    )
    assert "--cs-accent:" in html
    assert "Fraunces" not in html
    assert "@media print" in html
