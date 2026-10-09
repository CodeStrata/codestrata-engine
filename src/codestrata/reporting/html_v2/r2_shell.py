"""Shared R2 report shell taken from the committed reference stylesheets.

The CSS and logo are the reference presentation assets. Repository names,
metrics, findings, and action text from those samples are not copied here.
The print script is static and does not interpolate report text.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from importlib.resources import files

from codestrata.design_system.embedded_fonts import embedded_font_faces_css
from codestrata.reporters.html_rendering import escape_html

PRINT_CONTROL_SCRIPT = (
    "(function(){var b=document.querySelector('[data-print]');"
    "if(b){b.addEventListener('click',function(){window.print();});}})();"
)

# Layout and theme live in r2_shell.css. Do not redeclare grids here.
SHELL_COMPAT_CSS = ""


@lru_cache(maxsize=1)
def reference_shell_css() -> str:
    """Embedded fonts, reference stylesheet, and compatibility layer."""

    css = (
        files("codestrata.reporting.html_v2")
        .joinpath("assets/r2_shell.css")
        .read_text(encoding="utf-8")
    )
    # Tokens come before the embedded faces. A long data URI can cause the
    # following rule to be dropped, which previously left text on an undefined
    # palette.
    tokens = (
        ":root{color-scheme:light;--canvas:#f6f7f4;--ink:#0b3f3f;--text:#0b3f3f;"
        "--text-secondary:#3e574f;--muted:#4d635c;--surface:#ffffff;--surface-2:#eef2ef;"
        "--line:#d7e0db;--border:#d7e0db;--lime:#89f537;--accent:#89f537;--brand:#0b3f3f;"
        "--teal:#0b5f5f;--link:#0b5f5f;--warn:#8a4b12;--bad:#8f2d2d;--good:#1d5c28;"
        "--info:#1d4e89;--focus:#0b3f3f;--chart-label:#0b3f3f;--chart-axis:#4d635c;"
        "--chart-mark:#0b3f3f;--chart-edge:#8aa399;--status-attention-bg:#fff4e8;"
        "--status-attention-text:#8a4b12;--status-good-bg:#e7f6df;--status-good-text:#1d5c28;"
        "--status-neutral-bg:#f4f6f5;--status-neutral-text:#3d524c}"
    )
    return tokens + embedded_font_faces_css() + css + SHELL_COMPAT_CSS


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    return (
        files("codestrata.reporting.html_v2")
        .joinpath("assets/r2_logo_data_uri.txt")
        .read_text(encoding="utf-8")
        .strip()
    )


def script_source_hash(script: str) -> str:
    digest = hashlib.sha256(script.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def content_security_policy(*scripts: str) -> str:
    """Offline policy. Scripts are allowed only by exact source hash."""

    if scripts:
        sources = " ".join(f"'sha256-{script_source_hash(script)}'" for script in scripts)
    else:
        sources = "'none'"
    return (
        "default-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'; "
        "img-src data:; "
        "font-src data:; "
        "connect-src 'none'; "
        "object-src 'none'; "
        f"script-src {sources}; "
        "style-src 'unsafe-inline'"
    )


def print_script_tag() -> str:
    return f"<script>{PRINT_CONTROL_SCRIPT}</script>"


def report_chrome(*, active_label: str, download_href: str, download_label: str) -> str:
    """Brand bar, logo, one current-report label, JSON download, and print."""

    label = escape_html(active_label)
    href = escape_html(download_href)
    download = escape_html(download_label)
    return (
        '<a class="skip" href="#main">Skip to report</a>'
        '<div class="brandbar">'
        "<span>Engineering decisions, grounded in code.</span>"
        "<span>Single repository · Evidence-led reporting</span>"
        "</div>"
        '<header><div class="header-inner">'
        f'<img class="logo" src="{logo_data_uri()}" alt="CodeStrata">'
        '<span class="brand-word" aria-hidden="true">CodeStrata</span>'
        '<nav class="report-nav" aria-label="Report">'
        f'<span class="active" aria-current="page">{label}</span>'
        "</nav>"
        '<div class="header-actions">'
        f'<a class="button" href="{href}" download="{href}">{download}</a>'
        '<button type="button" class="primary" data-print>Print / Save PDF</button>'
        "</div></div></header>"
    )
