"""Leadership presentation helpers for HTML Report v3 (Phase 7.3).

Presentation only — no assessment-engine or scoring-logic changes.
"""

from __future__ import annotations

from typing import Any

from codestrata.reporting.html_v2.models import (
    DashboardMetrics,
    ExecutiveSummaryNarrative,
    FindingView,
    RecommendationView,
    ReportSummary,
    severity_rank,
)
from codestrata.reporting.roadmap.models import (
    RoadmapReportInitiativeView,
    RoadmapReportPhaseView,
    RoadmapReportSection,
)

_INFORMATIONAL = frozenset({"informational", "info"})

# Findings that are detection noise for leadership surfaces.
_LOW_SIGNAL_TITLE_MARKERS = (
    "language detected",
    "technology detected",
    "detected language",
    "programming language",
)

_THEME_LABELS: dict[str, str] = {
    "security": "Security",
    "dependency": "Dependencies",
    "architecture": "Architecture",
    "maintainability": "Technical debt",
    "technical_debt": "Technical debt",
    "testing": "Testing",
    "cloud_readiness": "Cloud readiness",
    "cloud": "Cloud readiness",
    "ai_readiness": "AI readiness",
    "performance": "Performance",
    "operational_readiness": "Operational readiness",
    "configuration": "Configuration",
    "reliability": "Reliability",
    "governance": "Governance",
    "technology": "Technology",
    "other": "Other",
}

_PACK_LABELS: dict[str, str] = {
    "security": "Security",
    "dependency": "Dependencies",
    "architecture": "Architecture",
    "technical_debt": "Technical debt",
    "testing": "Testing",
    "cloud": "Cloud readiness",
    "ai_readiness": "AI readiness",
    "performance": "Performance",
    "roadmap": "Roadmap",
}

# Engineer titles → leadership wording (keep meaning; improve readability).
_CUSTOMER_TITLES: dict[str, str] = {
    "framework symbol in domain boundary": (
        "Framework concerns are leaking into the domain model"
    ),
    "excessive branching": "Complex branching is increasing change risk",
    "large callable": "Oversized methods are hard to change safely",
    "disabled or skipped tests detected": (
        "Skipped or disabled tests are weakening delivery confidence"
    ),
    "dependency locking is not configured": (
        "Dependencies are not locked for reproducible builds"
    ),
    "dependency uses a dynamic version": (
        "Dynamic dependency versions risk inconsistent builds"
    ),
    "npm lockfile missing": "An npm lockfile is missing",
    "missing license": "No LICENSE file is present",
    "missing tests": "No automated tests were detected",
    "missing ci workflow": "No CI workflow was detected",
    "no conventional test structure detected": (
        "No conventional test layout was detected"
    ),
    "no cloud deployment assets detected": (
        "No cloud deployment assets were detected"
    ),
    "cloud deployment assets without runtime platform evidence": (
        "Deployment assets exist without clear runtime platform evidence"
    ),
}

_PHASE_OBJECTIVES = {
    "stabilize": (
        "Restore foundational engineering hygiene so later change is safe "
        "and observable."
    ),
    "secure": "Reduce security exposure before broader modernization work.",
    "modernize": (
        "Address structural, dependency, and platform modernization work."
    ),
    "optimize": "Improve performance and operational efficiency after foundations are solid.",
}


def is_leadership_signal_finding(finding: FindingView) -> bool:
    """Return True when a finding is meaningful for leadership risk narrative."""

    severity = finding.severity.strip().lower()
    if severity in _INFORMATIONAL:
        return False
    title = finding.title.strip().lower()
    category = finding.category.strip().lower()
    if category == "technology" and any(marker in title for marker in _LOW_SIGNAL_TITLE_MARKERS):
        return False
    if any(marker in title for marker in _LOW_SIGNAL_TITLE_MARKERS) and severity in {
        "low",
        "medium",
    }:
        return False
    return True


def customer_title(title: str) -> str:
    """Rewrite a finding/risk title into leadership language when a mapping exists."""

    key = title.strip().lower()
    return _CUSTOMER_TITLES.get(key, title.strip())


def theme_label_for_category(category: str) -> str:
    key = category.strip().lower().replace(" ", "_").replace("-", "_")
    return _THEME_LABELS.get(key, category.replace("_", " ").strip().title() or "Other")


def pack_display_label(pack_id: str) -> str:
    key = pack_id.strip().lower()
    return _PACK_LABELS.get(key, pack_id.replace("_", " ").strip().title())


def build_leadership_verdict(
    *,
    findings: tuple[FindingView, ...],
    priority_actions: tuple[RecommendationView, ...],
    metrics: DashboardMetrics,
    highest_severity: str,
) -> str:
    """Compose a 2–3 sentence VP-facing verdict. No methodology language."""

    signal = tuple(item for item in findings if is_leadership_signal_finding(item))
    medium_plus = tuple(
        item
        for item in signal
        if item.severity.lower() in {"critical", "high", "medium"}
    )
    severity = (highest_severity or "None Detected").strip()
    top_action = priority_actions[0].title if priority_actions else None
    primary_risk = customer_title(medium_plus[0].title) if medium_plus else None

    if not medium_plus:
        health = (
            f"Overall engineering health looks stable for this repository "
            f"(highest finding severity: {severity})."
        )
        risk_line = (
            "No medium-or-higher engineering risks stood out in the leadership view."
        )
        next_line = (
            f"Next: {top_action}."
            if top_action
            else "Next: maintain current engineering hygiene and reassess after material change."
        )
        return f"{health} {risk_line} {next_line}"

    if severity.lower() in {"critical", "high"}:
        health = (
            f"Overall engineering health requires attention "
            f"(highest finding severity: {severity})."
        )
    else:
        health = (
            f"Overall engineering health is workable but not risk-free "
            f"(highest finding severity: {severity})."
        )

    if len(medium_plus) > 1:
        risk_line = (
            f"Primary engineering risk: {primary_risk}, with "
            f"{len(medium_plus) - 1} additional medium-or-higher signal(s)."
        )
    else:
        risk_line = f"Primary engineering risk: {primary_risk}."

    cicd = (metrics.cicd_label or "").strip().lower()
    tests = (metrics.test_files_label or "").strip().lower()
    delivery_gap = cicd in {"not detected", "unknown", "", "—", "-"} or tests in {
        "0",
        "not detected",
        "unknown",
        "",
        "—",
        "-",
    }
    if top_action:
        next_line = f"Immediate recommendation: {top_action}."
    elif delivery_gap:
        next_line = (
            "Immediate recommendation: close delivery-readiness gaps before broader "
            "modernization."
        )
    else:
        next_line = (
            "Immediate recommendation: address the highest-severity risks before "
            "expanding platform work."
        )
    return f"{health} {risk_line} {next_line}"


def build_executive_summary_narrative(
    *,
    findings: tuple[FindingView, ...],
    priority_actions: tuple[RecommendationView, ...],
    metrics: DashboardMetrics,
    highest_severity: str,
    technologies: tuple[str, ...],
) -> ExecutiveSummaryNarrative:
    """Answer Should I care? / Why now? / What next? in leadership language."""

    signal = tuple(item for item in findings if is_leadership_signal_finding(item))
    medium_plus = tuple(
        item
        for item in signal
        if item.severity.lower() in {"critical", "high", "medium"}
    )
    tech_phrase = ", ".join(technologies[:4]) if technologies else "this codebase"
    top = priority_actions[0] if priority_actions else None
    near_term = tuple(
        item
        for item in priority_actions
        if (item.presentation_bucket or "").lower() in {"immediate", "near_term"}
    )

    if not medium_plus and not near_term:
        care = (
            f"You can treat {tech_phrase} as low urgency for leadership attention right now—"
            f"highest finding severity is {highest_severity}."
        )
        why = (
            "There are no medium-or-higher engineering risks in the leadership view, "
            "and delivery signals do not show an immediate blocker."
        )
        nxt = (
            f"Have the team complete: {top.title}."
            if top
            else "Keep current engineering practices and reassess after significant change."
        )
    elif (highest_severity or "").lower() in {"critical", "high"}:
        care = (
            f"Yes—{tech_phrase} needs leadership attention now "
            f"(highest finding severity: {highest_severity})."
        )
        why = (
            f"There are {len(medium_plus)} medium-or-higher engineering risk signal(s) "
            "that can slow delivery or increase change risk if left unaddressed."
        )
        nxt = _next_steps_sentence(near_term or priority_actions)
    else:
        care = (
            f"Yes, with measured urgency—{tech_phrase} has medium-severity engineering "
            "risks that are actionable now."
        )
        why = (
            "Addressing them now protects delivery confidence and avoids carrying "
            "avoidable debt into modernization work."
        )
        nxt = _next_steps_sentence(near_term or priority_actions)

    return ExecutiveSummaryNarrative(
        should_i_care=care,
        why_now=why,
        what_next=nxt,
    )


def _next_steps_sentence(actions: tuple[RecommendationView, ...]) -> str:
    if not actions:
        return "Review Engineering Risks and close the highest-severity items first."
    titles = [item.title for item in actions[:3]]
    if len(titles) == 1:
        return f"Have the team prioritize: {titles[0]}."
    if len(titles) == 2:
        return f"Have the team prioritize: {titles[0]}; then {titles[1]}."
    return (
        f"Have the team prioritize: {titles[0]}; then {titles[1]}; "
        f"then {titles[2]}"
        + ("." if len(actions) <= 3 else f" (+{len(actions) - 3} more).")
    )


def build_priority_actions_for_leadership(
    *,
    findings: tuple[FindingView, ...],
    recommendations: tuple[RecommendationView, ...],
    max_actions: int = 8,
) -> tuple[RecommendationView, ...]:
    """Return finding-backed Priority Actions for customer display.

    - Keep existing recommendations only when linked to findings.
    - When medium+ leadership risks lack a linked action, synthesize a
      presentation action from the finding (does not alter engine scoring).
    - Collapse duplicate titles and near-duplicate dependency/test intents.
    """

    grounded = tuple(item for item in recommendations if item.related_finding_ids)
    covered_ids = {fid for item in grounded for fid in item.related_finding_ids}
    covered_titles = {
        customer_title(title).lower()
        for item in grounded
        for title in item.related_finding_titles
    }
    covered_titles.update(customer_title(item.title).lower() for item in grounded)
    covered_intents = {_action_intent(item.title) for item in grounded}

    polished_grounded = tuple(_polish_recommendation(item, findings) for item in grounded)

    synthetic: list[RecommendationView] = []
    seen_titles: set[str] = set(covered_titles)
    for finding in findings:
        if not is_leadership_signal_finding(finding):
            continue
        if finding.severity.lower() not in {"critical", "high", "medium"}:
            continue
        if finding.finding_id in covered_ids:
            continue
        title = customer_title(finding.title)
        key = title.lower()
        if key in seen_titles:
            continue
        action_title = _action_title_from_finding(title, finding.category)
        intent = _action_intent(action_title)
        if intent in covered_intents:
            continue
        seen_titles.add(key)
        covered_intents.add(intent)
        synthetic.append(_action_from_finding(finding, title=title))

    combined = list(polished_grounded) + synthetic
    combined.sort(
        key=lambda item: (
            _bucket_rank(item.presentation_bucket),
            -float(item.priority_score or 0.0),
            priority_label_rank(item.priority),
            item.title.lower(),
        )
    )
    # Final pass: drop near-duplicate intents keeping highest-ranked.
    deduped: list[RecommendationView] = []
    seen_intents: set[str] = set()
    for item in combined:
        intent = _action_intent(item.title)
        if intent in seen_intents:
            continue
        seen_intents.add(intent)
        deduped.append(item)
    return tuple(deduped[:max_actions])


def _action_intent(title: str) -> str:
    """Normalize related action titles into a coarse intent key for dedupe."""

    lowered = title.strip().lower()
    if "lockfile" in lowered or "lock depend" in lowered or "not locked" in lowered:
        return "dependency-lock"
    if "pin depend" in lowered or "dynamic version" in lowered:
        return "dependency-pin"
    if "test baseline" in lowered or "automated test" in lowered or "missing tests" in lowered:
        return "testing-baseline"
    if "ci workflow" in lowered or "ci build" in lowered:
        return "ci-workflow"
    if "license" in lowered:
        return "license"
    if "framework" in lowered and ("domain" in lowered or "contain" in lowered):
        return "architecture-framework-boundary"
    if "branch" in lowered:
        return "td-branching"
    if "oversized" in lowered or "large callable" in lowered or "split oversized" in lowered:
        return "td-large-callable"
    return lowered


def _polish_recommendation(
    item: RecommendationView,
    findings: tuple[FindingView, ...],
) -> RecommendationView:
    finding_by_id = {f.finding_id: f for f in findings}
    titles = tuple(
        customer_title(finding_by_id[fid].title)
        if fid in finding_by_id
        else customer_title(title)
        for fid, title in _zip_related(item)
    )
    if not titles and item.related_finding_titles:
        titles = tuple(customer_title(t) for t in item.related_finding_titles)
    summary = item.summary.strip()
    if not summary or _is_generic_outcome(summary):
        summary = initiative_outcome_for_action(item.title, item.category)
    return item.model_copy(
        update={
            "related_finding_titles": titles or item.related_finding_titles,
            "summary": summary,
        }
    )


def _zip_related(item: RecommendationView) -> list[tuple[str, str]]:
    ids = item.related_finding_ids
    titles = item.related_finding_titles
    if not ids:
        return []
    out: list[tuple[str, str]] = []
    for index, fid in enumerate(ids):
        title = titles[index] if index < len(titles) else fid
        out.append((fid, title))
    return out


def _action_from_finding(finding: FindingView, *, title: str) -> RecommendationView:
    severity = finding.severity.lower()
    if severity == "critical":
        bucket, priority, score = "immediate", "immediate", 150.0
    elif severity == "high":
        bucket, priority, score = "immediate", "high", 145.0
    else:
        bucket, priority, score = "near_term", "medium", 90.0
    category = finding.category.strip().lower().replace(" ", "_")
    summary = initiative_outcome_for_action(title, category)
    return RecommendationView(
        recommendation_id=f"presentation:finding:{finding.finding_id}",
        title=_action_title_from_finding(title, category),
        summary=summary,
        rationale=(
            f"Address this {severity} finding before expanding modernization scope."
        ),
        priority=priority,
        category=category or "other",
        related_finding_ids=(finding.finding_id,),
        related_finding_titles=(title,),
        effort="medium",
        risk="medium" if severity == "medium" else "high",
        priority_score=score,
        presentation_bucket=bucket,
    )


def _action_title_from_finding(title: str, category: str) -> str:
    """Turn a risk statement into an action-oriented leadership title."""

    lowered = title.lower()
    if "lockfile" in lowered:
        return "Commit an npm lockfile"
    if "not locked" in lowered or "locking is not configured" in lowered:
        return "Lock dependencies for reproducible builds"
    if "dynamic dependency" in lowered or "dynamic version" in lowered:
        return "Pin dependency versions"
    if "skipped or disabled tests" in lowered:
        return "Re-enable or replace skipped tests"
    if "no automated tests" in lowered or lowered == "missing tests":
        return "Establish a test baseline"
    if "no ci workflow" in lowered or "missing ci" in lowered:
        return "Add a CI workflow"
    if "framework concerns" in lowered or "framework symbol" in lowered:
        return "Contain framework usage outside the domain model"
    if "complex branching" in lowered or "excessive branching" in lowered:
        return "Simplify high-risk branching paths"
    if "oversized methods" in lowered or "large callable" in lowered:
        return "Split oversized methods to reduce change risk"
    if "license" in lowered and ("missing" in lowered or "no " in lowered):
        return "Add an explicit LICENSE"
    if lowered.startswith("missing "):
        rest = title[len("missing ") :].strip()
        return f"Add {rest}" if rest else title
    if lowered.startswith("no "):
        rest = title[3:].strip()
        if rest.lower().startswith("conventional test"):
            return "Introduce a conventional test layout"
        if rest.lower().startswith("cloud deployment"):
            return "Add cloud deployment assets"
        return f"Address {rest}"
    verbs = {
        "security": "Remediate",
        "testing": "Address",
        "dependency": "Resolve",
        "architecture": "Resolve",
        "technical_debt": "Reduce",
        "maintainability": "Reduce",
        "cloud": "Clarify",
        "cloud_readiness": "Clarify",
        "governance": "Address",
    }
    verb = verbs.get(category, "Address")
    if title.lower().startswith(verb.lower()):
        return title
    if title:
        return f"{verb}: {title[0].lower() + title[1:]}"
    return verb


def initiative_outcome_for_action(title: str, category: str) -> str:
    """Initiative-specific business outcome (not a generic phase blurb)."""

    key = category.strip().lower().replace(" ", "_").replace("-", "_")
    t = title.strip()
    templates = {
        "testing": f"Improve delivery confidence by completing “{t}”.",
        "ci_cd": f"Make every change safer and more visible by completing “{t}”.",
        "build": f"Make every change safer and more visible by completing “{t}”.",
        "dependency": f"Stabilize builds and upgrades by completing “{t}”.",
        "governance": f"Clarify ownership and usage terms by completing “{t}”.",
        "security": f"Reduce security exposure by completing “{t}”.",
        "architecture": f"Reduce structural change risk by completing “{t}”.",
        "technical_debt": f"Lower maintenance cost by completing “{t}”.",
        "maintainability": f"Lower maintenance cost by completing “{t}”.",
        "cloud": f"Clarify deployment readiness by completing “{t}”.",
        "cloud_readiness": f"Clarify deployment readiness by completing “{t}”.",
        "performance": f"Improve runtime efficiency by completing “{t}”.",
    }
    return templates.get(key, f"Reduce engineering risk by completing “{t}”.")


def _is_generic_outcome(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "recommendations progress under control",
            "foundational build, test, documentation, and governance gaps are addressed",
            "architecture, dependency, and modernization recommendations progress",
        )
    )


def build_leadership_roadmap(
    priority_actions: tuple[RecommendationView, ...],
) -> RoadmapReportSection | None:
    """Build a phased plan from the same ordered Priority Actions.

    Phase assignment follows Priority Action horizon so ordering never
    contradicts Immediate → Near Term → Future sequencing.
    """

    if not priority_actions:
        return None

    phase_order = ("stabilize", "secure", "modernize", "optimize")
    buckets: dict[str, list[RecommendationView]] = {key: [] for key in phase_order}
    for action in priority_actions:
        phase = _phase_for_priority_action(action)
        buckets[phase].append(action)

    initiatives: list[RoadmapReportInitiativeView] = []
    phases: list[RoadmapReportPhaseView] = []
    sequence = 0
    for phase_id in phase_order:
        actions = buckets[phase_id]
        if not actions:
            continue
        phase_initiatives: list[RoadmapReportInitiativeView] = []
        for action in actions:
            sequence += 1
            initiative = RoadmapReportInitiativeView(
                initiative_id=f"leadership:{action.recommendation_id}",
                title=action.title,
                summary=action.title,
                phase=phase_id,
                phase_label=phase_id.title(),
                priority=action.priority,
                effort=action.effort or "medium",
                risk=action.risk or "medium",
                expected_outcome=initiative_outcome_for_action(
                    action.title, action.category
                ),
                supporting_finding_ids=tuple(action.related_finding_ids),
                supporting_recommendation_ids=(action.recommendation_id,),
                confidence="medium",
                category=action.category,
                sequence=sequence,
            )
            phase_initiatives.append(initiative)
            initiatives.append(initiative)
        phases.append(
            RoadmapReportPhaseView(
                phase_id=f"phase:{phase_id}",
                phase=phase_id,
                title=phase_id.title(),
                objective=_PHASE_OBJECTIVES[phase_id],
                sequence=len(phases),
                initiative_ids=tuple(item.initiative_id for item in phase_initiatives),
                initiatives=tuple(phase_initiatives),
            )
        )

    near = sum(
        1
        for item in priority_actions
        if (item.presentation_bucket or "").lower() in {"immediate", "near_term"}
    )
    summary = (
        f"{len(initiatives)} initiative(s) across {len(phases)} phase(s), "
        f"sequenced to match Priority Actions"
        + (f" ({near} near-term)." if near else ".")
    )
    return RoadmapReportSection(
        engine_version="leadership-presentation",
        status="succeeded",
        status_label="Ready",
        summary=summary,
        phases=tuple(phases),
        initiatives=tuple(initiatives),
        initiatives_total=len(initiatives),
        initiatives_displayed=len(initiatives),
        assumptions=(),
        limitations=(),
        confidence="medium",
        metadata={"source": "priority_actions"},
    )


def _phase_for_priority_action(action: RecommendationView) -> str:
    """Horizon-first phase so roadmap order matches Priority Actions."""

    bucket = (action.presentation_bucket or "").strip().lower()
    category = action.category.strip().lower().replace(" ", "_").replace("-", "_")
    if category == "security":
        return "secure"
    if category == "performance":
        return "optimize"
    if bucket in {"immediate", "near_term"}:
        return "stabilize"
    if category in {
        "testing",
        "ci_cd",
        "build",
        "docs",
        "documentation",
        "governance",
        "configuration",
    }:
        # Future hygiene still lands after Near Term stabilize work.
        return "modernize"
    return "modernize"


def build_leadership_key_takeaways(
    *,
    findings: tuple[FindingView, ...],
    recommendations: tuple[RecommendationView, ...],
    metrics: DashboardMetrics,
    summary: ReportSummary,
    activation: dict[str, Any] | None = None,
    architecture_present: bool = False,
    cloud_present: bool = False,
    testing_present: bool = False,
) -> tuple[str, ...]:
    """Compose 3–5 leadership takeaways aligned to Priority Actions."""

    del summary, activation, architecture_present, testing_present  # unused by design
    bullets: list[str] = []
    signal_findings = tuple(item for item in findings if is_leadership_signal_finding(item))
    medium_plus = tuple(
        item
        for item in signal_findings
        if item.severity.lower() in {"critical", "high", "medium"}
    )

    if medium_plus:
        lead = medium_plus[0]
        bullets.append(
            f"Highest engineering risk: {customer_title(lead.title)} ({lead.severity})."
        )
    elif signal_findings:
        bullets.append(
            f"Assessment recorded {len(signal_findings)} lower-severity signal(s); "
            "none rise to medium-or-higher leadership risk."
        )
    else:
        bullets.append(
            "No engineering risks were identified under the activated assessment checks."
        )

    if recommendations:
        top = recommendations[0]
        bullets.append(f"Top Priority Action: {top.title}.")
    else:
        bullets.append(
            "No Priority Actions were produced; address findings directly where present."
        )

    readiness_parts: list[str] = []
    if metrics.has_tests is True or (
        metrics.test_files_label and metrics.test_files_label not in {"Unknown", "—", "-"}
    ):
        readiness_parts.append(f"tests: {metrics.test_files_label}")
    elif metrics.has_tests is False:
        readiness_parts.append("tests: not detected")
    if metrics.cicd_label and metrics.cicd_label not in {"Unknown", "—", "-"}:
        readiness_parts.append(f"CI/CD: {metrics.cicd_label}")
    if readiness_parts:
        bullets.append("Delivery readiness — " + "; ".join(readiness_parts) + ".")

    if (
        cloud_present
        and metrics.cloud_signals_primary
        and metrics.cloud_signals_primary not in {"Unknown", "—", "-"}
        and len(bullets) < 5
    ):
        bullets.append(f"Cloud readiness signal: {metrics.cloud_signals_primary}.")

    if len(bullets) < 4 and len(recommendations) > 1:
        follow = recommendations[1].title
        bullets.append(f"Follow-on action: {follow}.")

    return tuple(bullets[:5])


def build_engineering_risks(
    findings: tuple[FindingView, ...],
    *,
    max_per_theme: int = 3,
    max_themes: int = 6,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Group meaningful findings into leadership risk themes (deduped titles)."""

    themes: dict[str, list[tuple[int, str]]] = {}
    seen_titles: set[str] = set()
    for finding in findings:
        if not is_leadership_signal_finding(finding):
            continue
        if finding.severity.lower() not in {"critical", "high", "medium"}:
            continue
        title = customer_title(finding.title)
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        theme = theme_label_for_category(finding.category)
        bucket = themes.setdefault(theme, [])
        if len(bucket) >= max_per_theme:
            continue
        bucket.append((severity_rank(finding.severity), f"{title} ({finding.severity})"))

    ordered_themes = sorted(
        themes.items(),
        key=lambda pair: (
            min((rank for rank, _text in pair[1]), default=99),
            pair[0].lower(),
        ),
    )
    return tuple(
        (theme, tuple(text for _rank, text in items))
        for theme, items in ordered_themes[:max_themes]
    )


def build_modernization_opportunities(
    *,
    findings: tuple[FindingView, ...],
    recommendations: tuple[RecommendationView, ...],
    risk_titles: frozenset[str] | None = None,
    max_items: int = 5,
) -> tuple[str, ...]:
    """Surface improvement opportunities without restating Priority Actions or risks."""

    excluded = {item.lower() for item in (risk_titles or frozenset())}
    excluded.update(customer_title(item.title).lower() for item in recommendations)
    for item in recommendations:
        excluded.update(customer_title(t).lower() for t in item.related_finding_titles)

    opportunities: list[str] = []
    seen: set[str] = set()

    for finding in findings:
        if not is_leadership_signal_finding(finding):
            continue
        if finding.severity.lower() != "low":
            continue
        title = customer_title(finding.title)
        if title.lower() in excluded or title.lower() in seen:
            continue
        seen.add(title.lower())
        opportunities.append(f"{title} ({finding.severity})")
        if len(opportunities) >= max_items:
            return tuple(opportunities)

    if not opportunities:
        opportunities.append(
            "Review capability assessments below for additional modernization options."
        )
    return tuple(opportunities[:max_items])


def build_assessment_scope(
    activation: dict[str, Any] | None,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Return (assessed_labels, ((not_assessed_label, reason), ...))."""

    if not activation:
        return (), ()
    packs = activation.get("packs") or []
    assessed: list[str] = []
    skipped: list[tuple[str, str]] = []
    for item in packs:
        if not isinstance(item, dict):
            continue
        pack_id = str(item.get("pack_id") or "")
        label = pack_display_label(pack_id)
        reason = str(item.get("reason") or "").strip() or "Not assessed for this repository."
        reason = _sanitize_scope_reason(reason)
        if item.get("enabled"):
            assessed.append(label)
        else:
            skipped.append((label, reason))
    return tuple(assessed), tuple(skipped)


def _sanitize_scope_reason(reason: str) -> str:
    """Remove config path / implementation crumbs from scope explanations."""

    cleaned = reason
    if " (" in cleaned and cleaned.endswith(")"):
        head, _, _tail = cleaned.partition(" (")
        if any(token in _tail for token in (".", "rules.", "assessment.", "report.")):
            cleaned = head.strip() or "Explicit configuration override"
    return cleaned


def _bucket_rank(bucket: str | None) -> int:
    key = (bucket or "").strip().lower()
    order = {"immediate": 0, "near_term": 1, "future": 2}
    return order.get(key, 9)


def priority_label_rank(priority: str) -> int:
    order = {
        "immediate": 0,
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return order.get(priority.lower(), 99)
