"""Separate license notices and embedded font bytes from report claims."""

from __future__ import annotations

import re

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_DATA_URI = re.compile(r"data:[^\"'\s)]+")


def claim_text(html: str) -> str:
    """Report prose with license comments and embedded font payloads removed."""

    text = _HTML_COMMENT.sub(" ", html)
    text = _CSS_COMMENT.sub(" ", text)
    return _DATA_URI.sub(" ", text)


def assert_no_network_asset(html: str) -> None:
    """License URLs in comments are allowed. Network assets and requests are not."""

    claims = claim_text(html)
    assert "https://" not in claims
    assert "http://" not in claims
    assert "<script src" not in html.lower()
    assert "url(http" not in claims.lower()
