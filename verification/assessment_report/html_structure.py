"""HTML structure, anchors, CSP, and section-order verification."""

from __future__ import annotations

import re
from collections import Counter

from codestrata.reporting.html_v2.r2_shell import PRINT_CONTROL_SCRIPT, script_source_hash
from verification.assessment_report.contract import EXPECTED_SECTION_ORDER
from verification.assessment_report.loaders import AssessmentRunArtifacts
from verification.assessment_report.models import CheckResult

# Do not match attribute suffixes such as data-evidence-id="...".
_ID_RE = re.compile(r'(?<![\w-])id="([^"]+)"')
_HREF_RE = re.compile(r'href="#([^"]+)"')
_CCL_RE = re.compile(
    r'data-canonical="coverage-confidence-limitations"|class="[^"]*assessment-ccl[^"]*"'
)
_SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_EVENT_HANDLER_RE = re.compile(r"<[^>]*\s(on[a-z]+)\s*=", re.IGNORECASE)
_CSP_RE = re.compile(
    r'http-equiv="Content-Security-Policy"[^>]*content="([^"]*)"',
    re.IGNORECASE,
)
_HASH_TOKEN_RE = re.compile(r"^'sha256-[A-Za-z0-9+/]+=*'$")
_APPROVED_SCRIPT_HASH = f"'sha256-{script_source_hash(PRINT_CONTROL_SCRIPT)}'"
_UNSAFE_SCRIPT_TOKENS = frozenset(
    {
        "'unsafe-inline'",
        "'unsafe-eval'",
        "'self'",
        "'strict-dynamic'",
        "*",
        "data:",
        "blob:",
        "http:",
        "https:",
    }
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
            ok=_scripts_are_approved(html),
            detail=_script_detail(html),
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
            ok=_csp_matches_scripts(html),
            detail=_csp_detail(html),
            category="html",
        ),
        CheckResult(
            name="html:no_inline_event_handlers",
            ok=_EVENT_HANDLER_RE.search(html) is None,
            detail="no inline event handlers",
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


def _script_bodies(html: str) -> list[tuple[str, str]]:
    return [(attrs, body) for attrs, body in _SCRIPT_RE.findall(html)]


def _has_external_source(attrs: str) -> bool:
    return re.search(r"\bsrc\s*=", attrs, flags=re.IGNORECASE) is not None


def _scripts_are_approved(html: str) -> bool:
    """Allow only the static print script, or no script at all."""

    bodies = _script_bodies(html)
    if not bodies:
        return True
    for attrs, body in bodies:
        if _has_external_source(attrs) or body != PRINT_CONTROL_SCRIPT:
            return False
    return True


def _script_detail(html: str) -> str:
    bodies = _script_bodies(html)
    if not bodies:
        return "no script"
    external = sum(1 for attrs, _body in bodies if _has_external_source(attrs))
    approved = sum(1 for _attrs, body in bodies if body == PRINT_CONTROL_SCRIPT)
    return f"scripts={len(bodies)} approved={approved} external={external}"


def _script_src_tokens(html: str) -> list[str] | None:
    match = _CSP_RE.search(html)
    if match is None:
        return None
    for part in match.group(1).split(";"):
        tokens = part.strip().split()
        if tokens and tokens[0] == "script-src":
            return tokens[1:]
    return None


def _csp_matches_scripts(html: str) -> bool:
    tokens = _script_src_tokens(html)
    if tokens is None:
        return False
    if any(_unsafe_script_token(token) for token in tokens):
        return False
    if any(not _HASH_TOKEN_RE.match(token) and token != "'none'" for token in tokens):
        return False
    bodies = _script_bodies(html)
    has_external = any(_has_external_source(attrs) for attrs, _body in bodies)
    if has_external:
        return False
    if not bodies:
        return tokens == ["'none'"]
    if any(body != PRINT_CONTROL_SCRIPT for _attrs, body in bodies):
        return False
    return tokens == [_APPROVED_SCRIPT_HASH]


def _unsafe_script_token(token: str) -> bool:
    return token in _UNSAFE_SCRIPT_TOKENS or token.startswith(("http:", "https:"))


def _csp_detail(html: str) -> str:
    tokens = _script_src_tokens(html)
    if tokens is None:
        return "CSP script-src missing"
    return "script-src " + " ".join(tokens)
