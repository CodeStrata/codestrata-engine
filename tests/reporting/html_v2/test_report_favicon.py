"""Slice 20.13A — favicon on standalone / published Engineering Assessment HTML."""

from __future__ import annotations

import base64
import inspect
import re
from pathlib import Path

from tests.reporting.html_v2.test_html_report_v2 import _report_input

from codestrata.community_cloud import report_publishing
from codestrata.reporting.assessment_json import build_assessment_json_document
from codestrata.reporting.branding import (
    BRAND_FAVICON_ASSET,
    brand_favicon_data_uri,
    brand_favicon_link_tag,
)
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model


_FORBIDDEN_PATH_MARKERS = (
    "/Users/",
    "file://",
    "codestrata-platform/engine/src",
    "workspace-ai/",
    ".venv/",
)


def _render(tmp_path: Path) -> str:
    return HtmlReportRenderer().render(build_html_report_view_model(_report_input(tmp_path)))


def test_report_favicon_01_generated_html_contains_favicon_declaration(tmp_path: Path) -> None:
    """REPORT-FAVICON-01"""

    html = _render(tmp_path)
    assert "<head>" in html
    assert 'rel="icon"' in html
    assert 'type="image/png"' in html
    assert brand_favicon_link_tag() in html
    assert html.index("<head>") < html.index('rel="icon"') < html.index("</head>")


def test_report_favicon_02_no_developer_local_or_private_path(tmp_path: Path) -> None:
    """REPORT-FAVICON-02"""

    html = _render(tmp_path)
    match = re.search(r'<link\s+rel="icon"[^>]*>', html)
    assert match is not None
    tag = match.group(0)
    tag_lower = tag.lower()
    for marker in _FORBIDDEN_PATH_MARKERS:
        assert marker.lower() not in tag_lower
    assert "href=\"data:image/png;base64," in tag
    assert "http://" not in tag
    assert "https://" not in tag
    # Syntactically valid bounded base64 payload.
    uri = brand_favicon_data_uri()
    assert uri.startswith("data:image/png;base64,")
    raw = base64.standard_b64decode(uri.split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert 0 < len(raw) <= 4096
    assert BRAND_FAVICON_ASSET.endswith(".png")


def test_report_favicon_03_packaged_asset_resolves_via_importlib(tmp_path: Path) -> None:
    """REPORT-FAVICON-03 — installed-wheel path uses importlib.resources, not source tree."""

    from importlib.resources import files

    asset = files("codestrata.reporting.assets").joinpath(BRAND_FAVICON_ASSET)
    assert asset.is_file()
    html = _render(tmp_path)
    assert brand_favicon_data_uri() in html
    # Helper must not construct filesystem paths to the monorepo.
    src = inspect.getsource(brand_favicon_data_uri)
    assert ".venv" not in src
    assert "/Users/" not in src
    assert "Path(__file__)" not in src


def test_report_favicon_04_public_publish_uploads_raw_html_bytes(tmp_path: Path) -> None:
    """REPORT-FAVICON-04 — publish path does not strip favicon from assessment.html."""

    html = _render(tmp_path)
    current = tmp_path / "current"
    current.mkdir()
    html_path = current / "assessment.html"
    json_path = current / "assessment.json"
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text("{}", encoding="utf-8")

    # Contract: publish reads assessment.html bytes verbatim (no HTML rewrite).
    src = inspect.getsource(report_publishing.publish_local_assessment)
    assert 'html_path.read_bytes()' in src
    assert "assessment.html" in src
    raw = html_path.read_bytes()
    assert b'rel="icon"' in raw
    assert b"data:image/png;base64," in raw
    assert raw == html.encode("utf-8")


def test_report_favicon_05_json_report_semantics_unchanged(tmp_path: Path) -> None:
    """REPORT-FAVICON-05"""

    report_input = _report_input(tmp_path)
    before = build_assessment_json_document(report_input)
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    after = build_assessment_json_document(report_input)
    assert before == after
    assert "favicon" not in str(after).lower()
    assert 'rel="icon"' in html
