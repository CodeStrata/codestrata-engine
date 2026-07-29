"""Tests for safe HTML long-value and collection rendering helpers."""

from __future__ import annotations

from codestrata.reporters.html_rendering import (
    COLLECTION_COLLAPSE_THRESHOLD,
    escape_and_wrap,
    escape_html,
    render_collection,
)


def test_escape_and_wrap_escapes_before_inserting_wbr() -> None:
    rendered = escape_and_wrap('<script>alert("xss")</script>')
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "alert" in rendered


def test_escape_and_wrap_inserts_controlled_wbr_markers() -> None:
    rendered = escape_and_wrap("org.example:artifact:1.2.3")
    assert "<wbr>" in rendered
    assert rendered.replace("<wbr>", "") == escape_html("org.example:artifact:1.2.3")


def test_escape_and_wrap_preserves_unicode() -> None:
    value = "café/résumé/日本語"
    rendered = escape_and_wrap(value)
    assert "café" in rendered
    assert "日本語" in rendered
    assert rendered.replace("<wbr>", "") == value


def test_short_collection_remains_expanded() -> None:
    values = [f"item-{index}" for index in range(COLLECTION_COLLAPSE_THRESHOLD)]
    html = render_collection(values, presentation="list")
    assert "Show " not in html
    assert "<details>" not in html
    for value in values:
        assert value in html.replace("<wbr>", "")


def test_collection_one_over_threshold_collapses() -> None:
    values = [f"dep-{index}" for index in range(COLLECTION_COLLAPSE_THRESHOLD + 1)]
    html = render_collection(values, presentation="list")
    assert "<details>" in html
    assert f"Show {1} more" in html
    plain = html.replace("<wbr>", "")
    for value in values:
        assert value in plain


def test_empty_collection_renders_none() -> None:
    assert "None" in render_collection([])


def test_single_value_collection_renders_without_details() -> None:
    html = render_collection(["only-one"], presentation="badges")
    assert "only-one" in html.replace("<wbr>", "")
    assert "<details>" not in html


def test_collection_ordering_is_deterministic() -> None:
    values = ["zeta", "alpha", "middle"]
    html = render_collection(values, presentation="list")
    plain = html.replace("<wbr>", "")
    assert plain.index("zeta") < plain.index("alpha") < plain.index("middle")
