"""Shared offline font embedding for HTML consumers."""

from __future__ import annotations

import base64
from functools import lru_cache
from importlib.resources import files

FONT_LICENSE_NOTICE = (
    "Google Sans Flex: Copyright 2015 The Google Sans Flex Authors "
    "(https://github.com/googlefonts/googlesans-flex). "
    "IBM Plex Mono: Copyright 2017 IBM Corp. with Reserved Font Name Plex. "
    "Both fonts are licensed under the SIL Open Font License 1.1."
)


def _asset_bytes(name: str) -> bytes:
    return files("codestrata.reporting.html_v2").joinpath("assets").joinpath(name).read_bytes()


def _asset_text(name: str) -> str:
    return files("codestrata.reporting.html_v2").joinpath("assets").joinpath(name).read_text(
        encoding="utf-8"
    )


def _data_uri(mime: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


@lru_cache(maxsize=1)
def embedded_font_faces_css() -> str:
    """One variable Google Sans Flex payload plus supplementary IBM Plex Mono."""

    sans = _data_uri("font/woff2", _asset_bytes("GoogleSansFlex-report.woff2"))
    mono = _data_uri("font/ttf", _asset_bytes("IBMPlexMono-Regular.ttf"))
    return (
        f'@font-face{{font-family:"Google Sans Flex";src:url("{sans}") '
        'format("woff2");font-weight:400 600;font-style:normal;font-display:swap}'
        f'@font-face{{font-family:"IBM Plex Mono";src:url("{mono}") '
        'format("truetype");font-weight:400;font-style:normal;font-display:swap}'
        f"/* {FONT_LICENSE_NOTICE} */"
    )


@lru_cache(maxsize=1)
def font_license_html_comment() -> str:
    """Full unchanged OFL texts plus the short attribution line."""

    google = _asset_text("OFL-GoogleSansFlex.txt").strip()
    mono = _asset_text("OFL-IBMPlexMono.txt").strip()
    return (
        f"<!-- {FONT_LICENSE_NOTICE} -->\n"
        f"<!-- OFL-GoogleSansFlex.txt\n{google}\n-->\n"
        f"<!-- OFL-IBMPlexMono.txt\n{mono}\n-->"
    )


__all__ = [
    "FONT_LICENSE_NOTICE",
    "embedded_font_faces_css",
    "font_license_html_comment",
]
