"""YAML-bound Dependency hygiene SharedRules (E06.3).

Canonical default severity, title and message come from bundled YAML. Native
Python extracts declaration facts and evaluates allowlisted operators.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from codestrata.application.rules.dependency.yaml_catalog import bundled_rule
from codestrata.domain.rules.enums import RuleSeverity
from codestrata.domain.rules.metadata import RuleMetadata

_BINDING = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def render_template(template: str, values: Mapping[str, str]) -> str:
    rendered = _BINDING.sub(lambda match: values.get(match.group(1), ""), template)
    return " ".join(rendered.split())


def yaml_metadata(
    rule_id: str,
    *,
    make_metadata: Callable[..., RuleMetadata],
    remediation: str,
) -> RuleMetadata:
    catalog = bundled_rule(rule_id)
    severity = catalog["default_severity"]
    if not isinstance(severity, RuleSeverity):
        severity = RuleSeverity(str(severity))
    return make_metadata(
        rule_id=str(catalog["rule_id"]),
        title=str(catalog["title"]),
        description=str(catalog["description"]),
        remediation=remediation,
        severity=severity,
    )


def yaml_title_and_template(rule_id: str) -> tuple[str, str, RuleSeverity]:
    catalog = bundled_rule(rule_id)
    severity = catalog["default_severity"]
    if not isinstance(severity, RuleSeverity):
        severity = RuleSeverity(str(severity))
    return str(catalog["title"]), str(catalog["message_template"]), severity
