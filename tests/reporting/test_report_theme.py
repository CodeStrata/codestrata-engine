"""Theme checks for the shared report shell.

Baseline, trend, and canonical reports use a light screen regardless of the
operating-system preference. The last declaration for each property has to
keep dark-green text on a pale surface.
"""

from __future__ import annotations

import re

from codestrata.reporting.engineering_health.trend_report import _TREND_CSS
from codestrata.reporting.html_v2.r2_shell import reference_shell_css

_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _declarations(css: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for selector, body in _RULE.findall(css.split("@media", 1)[0]):
        props = found.setdefault(selector.strip(), {})
        for chunk in body.split(";"):
            if ":" not in chunk:
                continue
            name, value = chunk.split(":", 1)
            props[name.strip()] = value.strip()
    return found


def test_report_screen_is_light_by_default() -> None:
    props = _declarations(reference_shell_css())[":root"]
    assert props["color-scheme"] == "light"
    assert props["--canvas"] == "#f6f7f4"
    assert props["--ink"] == "#0b3f3f"
    assert props["--surface"] == "#ffffff"
    screen = reference_shell_css().split("@media", 1)[0]
    assert "#00120d" not in screen
    assert "prefers-color-scheme" not in reference_shell_css()


def test_attention_verdict_uses_dark_text_on_a_pale_card() -> None:
    props = _declarations(reference_shell_css())[".attention-main"]
    assert props["background"] == "var(--surface)"
    assert props["color"] == "var(--ink)"
    assert "white" not in props["color"]


def test_chart_labels_use_dark_ink() -> None:
    props = _declarations(reference_shell_css())
    chart_text = "svg text, .plot-label, .plot-axis, .architecture-map text, .hotspot-scatter text"
    label = props[chart_text]
    assert label["fill"] == "var(--chart-label)"
    assert props[":root"]["--chart-label"] == "#0b3f3f"
    assert props[":root"]["--chart-mark"] == "#0b3f3f"


def test_code_and_evidence_surfaces_keep_dark_text() -> None:
    props = _declarations(reference_shell_css())
    assert props[".meta code, code, .trace-id"]["color"] == "var(--ink)"
    assert "anywhere" in props[".meta code, code, .trace-id"]["overflow-wrap"]
    evidence = (
        ".count-statement, .impact-hero, .impact-stat, .impact-step, "
        ".priority-action details, details"
    )
    assert props[evidence]["background"] == "var(--surface)"
    assert props[evidence]["color"] == "var(--ink)"


def test_each_grid_is_declared_once_on_the_screen() -> None:
    screen = reference_shell_css().split("@media", 1)[0]
    assert screen.count(".attention-board {") == 1
    assert screen.count(".hotspot-layout {") == 1
    assert "grid-template-columns:1.4fr .8fr" not in screen
    assert "grid-template-columns:1.65fr 1fr" not in screen


def test_trend_overlay_does_not_restore_a_warning_panel() -> None:
    assert "#fff7ed" not in _TREND_CSS
    assert "#ffedd5" not in _TREND_CSS
    assert "var(--surface)" in _TREND_CSS
