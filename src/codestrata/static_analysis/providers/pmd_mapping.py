"""PMD priority, category, and rule-id mapping helpers."""

from __future__ import annotations

import re

from codestrata.models.enums import FindingCategory, Severity

_PRIORITY_TO_SEVERITY = {
    1: Severity.CRITICAL,
    2: Severity.HIGH,
    3: Severity.MEDIUM,
    4: Severity.LOW,
    5: Severity.INFO,
}

_RULESET_TO_CATEGORY = {
    "security": FindingCategory.SECURITY,
    "errorprone": FindingCategory.RELIABILITY,
    "performance": FindingCategory.PERFORMANCE,
    "design": FindingCategory.MAINTAINABILITY,
    "bestpractices": FindingCategory.MAINTAINABILITY,
    "codestyle": FindingCategory.MAINTAINABILITY,
    "documentation": FindingCategory.MAINTAINABILITY,
    "multithreading": FindingCategory.RELIABILITY,
}


def map_pmd_priority(priority: int | None) -> Severity:
    """Map a PMD priority value to CodeStrata severity."""

    if priority is None:
        return Severity.INFO
    return _PRIORITY_TO_SEVERITY.get(priority, Severity.INFO)


def normalize_ruleset_token(ruleset: str | None) -> str:
    """Normalize a PMD ruleset name into a compact token."""

    if not ruleset:
        return "UNKNOWN"

    token = ruleset.strip().lower().replace(" ", "")
    token = token.removesuffix(".xml")
    if "/" in token:
        token = token.rsplit("/", maxsplit=1)[-1]
    token = re.sub(r"[^a-z0-9]+", "", token)
    return token.upper() or "UNKNOWN"


def map_pmd_category(ruleset: str | None) -> FindingCategory:
    """Map a PMD ruleset to an CodeStrata finding category."""

    token = normalize_ruleset_token(ruleset).lower()
    return _RULESET_TO_CATEGORY.get(token, FindingCategory.MAINTAINABILITY)


def build_pmd_rule_id(ruleset: str | None, rule: str | None) -> str:
    """Build a stable CodeStrata rule identifier for a PMD violation."""

    ruleset_token = normalize_ruleset_token(ruleset)
    rule_token = re.sub(r"[^A-Za-z0-9]+", "", rule or "UNKNOWN").upper() or "UNKNOWN"
    return f"PMD.JAVA.{ruleset_token}.{rule_token}"


def humanize_rule_name(rule: str | None) -> str:
    """Convert a CamelCase PMD rule name into a readable title."""

    if not rule:
        return "PMD finding"

    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", rule).strip()
    if not spaced:
        return rule
    return spaced[0].upper() + spaced[1:].lower() if len(spaced) > 1 else spaced.upper()
