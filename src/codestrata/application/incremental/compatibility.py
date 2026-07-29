"""Engine and artifact compatibility evaluation."""

from __future__ import annotations

from codestrata.application.incremental.fingerprints import EngineCompatibilityFingerprint
from codestrata.application.incremental.models import CompatibilityIssue, CompatibilityResult
from codestrata.application.incremental.policies import IncrementalPlanningPolicy


class CompatibilityEvaluator:
    """Compare previous and current engine fingerprints."""

    def evaluate(
        self,
        previous: EngineCompatibilityFingerprint | None,
        current: EngineCompatibilityFingerprint,
        *,
        policy: IncrementalPlanningPolicy | None = None,
        changed_languages: frozenset[str] | None = None,
    ) -> CompatibilityResult:
        policy = policy or IncrementalPlanningPolicy()
        if previous is None:
            return CompatibilityResult(
                compatible=False,
                scanner_compatible=False,
                parser_compatible=False,
                graph_compatible=False,
                rule_compatible=False,
                recommendation_compatible=False,
                artifact_schema_compatible=False,
                tool_compatible=False,
                issues=(
                    CompatibilityIssue(
                        code="missing_previous_engine_fingerprint",
                        message="Previous engine fingerprint is unavailable",
                        blocking=True,
                    ),
                ),
                blocking_reasons=("missing_previous_engine_fingerprint",),
            )

        issues: list[CompatibilityIssue] = []
        scanner_ok = previous.scanner == current.scanner
        if not scanner_ok:
            issues.append(
                CompatibilityIssue(
                    code="scanner_mismatch",
                    message="Scanner fingerprint changed",
                    blocking=True,
                    subject="scanner",
                )
            )

        parser_ok = True
        if previous.parsers != current.parsers:
            # Language-specific: if changed languages are empty and parsers differ,
            # still treat conservatively as incompatible when policy requires.
            changed = changed_languages or frozenset()
            if changed or policy.fallback_on_engine_change:
                parser_ok = False
                issues.append(
                    CompatibilityIssue(
                        code="parser_mismatch",
                        message="Parser fingerprint changed",
                        blocking=True,
                        subject="parsers",
                    )
                )

        graph_ok = (
            previous.repository_graph_schema == current.repository_graph_schema
            and previous.knowledge_graph_schema == current.knowledge_graph_schema
            and previous.assessment_graph_schema == current.assessment_graph_schema
            and previous.graph_builder == current.graph_builder
        )
        if not graph_ok:
            issues.append(
                CompatibilityIssue(
                    code="graph_mismatch",
                    message="Graph schema or builder fingerprint changed",
                    blocking=True,
                    subject="graph",
                )
            )

        rule_ok = previous.rules == current.rules
        if not rule_ok:
            issues.append(
                CompatibilityIssue(
                    code="rule_mismatch",
                    message="Rule-engine fingerprint changed",
                    blocking=True,
                    subject="rules",
                )
            )

        rec_ok = previous.recommendations == current.recommendations
        if not rec_ok:
            issues.append(
                CompatibilityIssue(
                    code="recommendation_mismatch",
                    message="Recommendation-engine fingerprint changed",
                    blocking=True,
                    subject="recommendations",
                )
            )

        schema_ok = previous.artifact_schemas == current.artifact_schemas
        if not schema_ok:
            issues.append(
                CompatibilityIssue(
                    code="artifact_schema_mismatch",
                    message="Artifact schema versions changed",
                    blocking=True,
                    subject="artifact_schemas",
                )
            )

        # Tool patch version alone is non-blocking when functional fingerprints match.
        tool_ok = True
        if previous.tool_version != current.tool_version:
            functional_match = (
                scanner_ok and parser_ok and graph_ok and rule_ok and rec_ok and schema_ok
            )
            if not functional_match:
                tool_ok = False
                issues.append(
                    CompatibilityIssue(
                        code="tool_version_with_functional_change",
                        message="Tool version changed alongside functional fingerprints",
                        blocking=True,
                        subject="tool_version",
                    )
                )
            else:
                issues.append(
                    CompatibilityIssue(
                        code="tool_version_changed",
                        message="Tool version changed; functional fingerprints match",
                        blocking=False,
                        subject="tool_version",
                    )
                )

        blocking = tuple(item.code for item in issues if item.blocking)
        compatible = not blocking
        if not compatible and policy.fallback_on_engine_change:
            pass

        return CompatibilityResult(
            compatible=compatible,
            scanner_compatible=scanner_ok,
            parser_compatible=parser_ok,
            graph_compatible=graph_ok,
            rule_compatible=rule_ok,
            recommendation_compatible=rec_ok,
            artifact_schema_compatible=schema_ok,
            tool_compatible=tool_ok,
            issues=tuple(issues),
            blocking_reasons=blocking,
        )
