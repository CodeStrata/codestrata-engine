"""Write self-contained HTML modernization assessment reports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from codestrata.models import (
    AnalysisResult,
    Finding,
    Priority,
    Recommendation,
    Severity,
)
from codestrata.models.evidence import Evidence
from codestrata.reporters.evidence_location import format_evidence_item_location
from codestrata.reporters.html_rendering import (
    COLLECTION_COLLAPSE_THRESHOLD,
    escape_and_wrap,
    escape_html,
    render_collection,
    wrap_table,
)


class HtmlFileReporter:
    """Render an AnalysisResult as a self-contained HTML report."""

    collection_collapse_threshold = COLLECTION_COLLAPSE_THRESHOLD

    def write(
        self,
        result: AnalysisResult,
        output_path: Path,
    ) -> Path:
        """Write the HTML report and return its path."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self.render(result),
            encoding="utf-8",
        )
        return output_path

    def render(self, result: AnalysisResult) -> str:
        """Return the complete HTML document as a string."""

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{self._e(self._page_title(result))}</title>\n"
            f"<style>{self._css()}</style>\n"
            "</head>\n"
            "<body>\n"
            '<div class="page">\n'
            f"{self._render_header(result)}"
            f"{self._render_executive_summary(result)}"
            f"{self._render_static_analysis_providers(result)}"
            f"{self._render_comparison(result)}"
            f"{self._render_repository_facts(result)}"
            f"{self._render_findings(result)}"
            f"{self._render_recommendations(result)}"
            f"{self._render_roadmap(result)}"
            f"{self._render_assessment_summary(result)}"
            f"{self._render_footer(result)}"
            "</div>\n"
            "</body>\n"
            "</html>\n"
        )

    def _page_title(self, result: AnalysisResult) -> str:
        return f"CodeStrata Assessment — {result.repository.name}"

    def _render_header(self, result: AnalysisResult) -> str:
        repository = result.repository
        technologies = ", ".join(technology.name for technology in result.technologies) or (
            "None detected"
        )
        build_systems = (
            ", ".join(result.facts.build.build_systems)
            if result.facts.build is not None and result.facts.build.build_systems
            else "None detected"
        )
        dependency_count = self._dependency_count(result)

        return (
            '<header class="report-header">\n'
            "<h1>CodeStrata</h1>\n"
            '<p class="subtitle">Deterministic modernization assessment</p>\n'
            '<dl class="meta-grid">\n'
            f"<dt>Repository</dt><dd>{self._wrap(repository.name)}</dd>\n"
            f"<dt>Scan timestamp</dt><dd>{self._wrap(self._scan_timestamp(result))}</dd>\n"
            f"<dt>Files scanned</dt><dd>{len(repository.files)}</dd>\n"
            f"<dt>Detected technologies</dt><dd>{self._wrap(technologies)}</dd>\n"
            f"<dt>Build systems</dt><dd>{self._wrap(build_systems)}</dd>\n"
            f"<dt>Dependency count</dt><dd>{self._wrap(dependency_count)}</dd>\n"
            "</dl>\n"
            "</header>\n"
        )

    def _render_executive_summary(self, result: AnalysisResult) -> str:
        severity_counts = Counter(finding.severity for finding in result.findings)
        priority_counts = Counter(
            recommendation.priority for recommendation in result.recommendations
        )

        severity_rows = "".join(
            (
                "<tr>"
                f"<td>{self._severity_badge(severity)}</td>"
                f"<td>{severity_counts.get(severity, 0)}</td>"
                "</tr>"
            )
            for severity in (
                Severity.CRITICAL,
                Severity.HIGH,
                Severity.MEDIUM,
                Severity.LOW,
                Severity.INFO,
            )
        )
        priority_rows = "".join(
            (
                "<tr>"
                f"<td>{self._priority_badge(priority)}</td>"
                f"<td>{priority_counts.get(priority, 0)}</td>"
                "</tr>"
            )
            for priority in (
                Priority.CRITICAL,
                Priority.HIGH,
                Priority.MEDIUM,
                Priority.LOW,
            )
        )

        findings_table = wrap_table(
            '<table class="counts">\n'
            "<thead><tr><th>Severity</th><th>Count</th></tr></thead>\n"
            f"<tbody>{severity_rows}</tbody>\n"
            "</table>\n"
        )
        recommendations_table = wrap_table(
            '<table class="counts">\n'
            "<thead><tr><th>Priority</th><th>Count</th></tr></thead>\n"
            f"<tbody>{priority_rows}</tbody>\n"
            "</table>\n"
        )

        return (
            '<section class="section">\n'
            "<h2>Executive Summary</h2>\n"
            f'<p class="summary-text">{self._wrap(self._executive_summary_text(result))}</p>\n'
            '<div class="summary-grid">\n'
            '<div class="summary-card">\n'
            "<h3>Findings</h3>\n"
            f'<p class="metric">{len(result.findings)}</p>\n'
            f"{findings_table}"
            "</div>\n"
            '<div class="summary-card">\n'
            "<h3>Recommendations</h3>\n"
            f'<p class="metric">{len(result.recommendations)}</p>\n'
            f"{recommendations_table}"
            "</div>\n"
            "</div>\n"
            "</section>\n"
        )

    def _executive_summary_text(self, result: AnalysisResult) -> str:
        finding_count = len(result.findings)
        recommendation_count = len(result.recommendations)
        critical_findings = sum(
            finding.severity == Severity.CRITICAL for finding in result.findings
        )
        high_recommendations = sum(
            recommendation.priority in {Priority.CRITICAL, Priority.HIGH}
            for recommendation in result.recommendations
        )

        parts = [
            (
                f"Analyzed repository '{result.repository.name}' with "
                f"{len(result.repository.files)} scanned file(s)."
            ),
            (
                f"Detected {finding_count} finding(s) "
                f"({critical_findings} critical) and "
                f"{recommendation_count} recommendation(s) "
                f"({high_recommendations} critical/high priority)."
            ),
        ]

        structure = result.facts.structure
        if structure is not None and structure.has_tests is not None:
            parts.append(
                "Automated tests were detected."
                if structure.has_tests
                else "No automated tests were detected."
            )

        cicd = result.facts.cicd
        if cicd is not None:
            parts.append("CI was detected." if cicd.has_ci else "No CI pipeline was detected.")

        cloud = result.facts.cloud
        if cloud is not None and cloud.cloud_capabilities:
            parts.append(
                "Cloud capabilities detected: " + ", ".join(cloud.cloud_capabilities) + "."
            )

        return " ".join(parts)

    def _render_comparison(self, result: AnalysisResult) -> str:
        comparison = result.comparison

        if comparison is None or not comparison.baseline_available:
            return (
                '<section class="section">\n'
                "<h2>Changes Since Previous Scan</h2>\n"
                '<p class="empty">No previous completed scan is available '
                "for comparison.</p>\n"
                "</section>\n"
            )

        summary = comparison.summary
        summary_rows = [
            ("New findings", str(summary.new_findings)),
            ("Resolved findings", str(summary.resolved_findings)),
            ("Worsened findings", str(summary.worsened_findings)),
            ("Improved findings", str(summary.improved_findings)),
            ("New recommendations", str(summary.new_recommendations)),
            ("Resolved recommendations", str(summary.resolved_recommendations)),
            ("Worsened priorities", str(summary.worsened_priorities)),
            ("Improved priorities", str(summary.improved_priorities)),
            ("Fact changes", str(summary.fact_changes)),
        ]
        summary_html = "".join(
            f"<tr><th>{self._e(label)}</th><td>{self._wrap(value)}</td></tr>\n"
            for label, value in summary_rows
        )

        version_rows = ""
        if (
            comparison.baseline_analyzer_version
            or comparison.current_analyzer_version
            or comparison.baseline_ruleset_version
            or comparison.current_ruleset_version
        ):
            version_rows = (
                "<dt>Baseline analyzer</dt>"
                f"<dd>{self._wrap(comparison.baseline_analyzer_version or 'Unknown')}</dd>\n"
                "<dt>Current analyzer</dt>"
                f"<dd>{self._wrap(comparison.current_analyzer_version or 'Unknown')}</dd>\n"
                "<dt>Baseline ruleset</dt>"
                f"<dd>{self._wrap(comparison.baseline_ruleset_version or 'Unknown')}</dd>\n"
                "<dt>Current ruleset</dt>"
                f"<dd>{self._wrap(comparison.current_ruleset_version or 'Unknown')}</dd>\n"
            )

        notes_html = ""
        if comparison.notes:
            notes_items = "".join(
                f'<li class="technical-value">{self._wrap(note)}</li>' for note in comparison.notes
            )
            notes_html = f'<h3>Notes</h3>\n<ul class="change-list">{notes_items}</ul>\n'

        return (
            '<section class="section comparison-section">\n'
            "<h2>Changes Since Previous Scan</h2>\n"
            '<dl class="meta-grid">\n'
            "<dt>Baseline timestamp</dt>"
            f"<dd>{self._wrap(comparison.baseline_timestamp or 'Unknown')}</dd>\n"
            "<dt>Current timestamp</dt>"
            f"<dd>{self._wrap(comparison.current_timestamp or 'Unknown')}</dd>\n"
            f"{version_rows}"
            "</dl>\n"
            f"{notes_html}"
            "<h3>Summary</h3>\n"
            + self._fact_table(summary_html)
            + self._comparison_finding_list(
                "New Findings",
                comparison.new_findings,
                "new",
            )
            + self._comparison_finding_list(
                "Resolved Findings",
                comparison.resolved_findings,
                "resolved",
            )
            + self._severity_change_list(comparison.severity_changes)
            + self._comparison_recommendation_list(
                "New Recommendations",
                comparison.new_recommendations,
                "new",
            )
            + self._comparison_recommendation_list(
                "Resolved Recommendations",
                comparison.resolved_recommendations,
                "resolved",
            )
            + self._priority_change_list(comparison.priority_changes)
            + self._fact_change_list(comparison.fact_changes)
            + "</section>\n"
        )

    def _comparison_finding_list(
        self,
        title: str,
        findings: list[Any],
        label: str,
    ) -> str:
        if not findings:
            return f'<h3>{self._e(title)}</h3>\n<p class="empty">None</p>\n'

        items: list[str] = []
        for finding in findings:
            items.append(
                "<li>"
                f'<span class="badge change-{label}">{self._e(label.title())}</span> '
                f'<span class="technical-value">'
                f"{self._wrap(finding.rule_id or 'No rule ID')}"
                "</span>"
                " — "
                f"{self._wrap(finding.title)} "
                f"({self._e(finding.severity)})"
                "</li>"
            )
        return f'<h3>{self._e(title)}</h3>\n<ul class="change-list">{"".join(items)}</ul>\n'

    def _comparison_recommendation_list(
        self,
        title: str,
        recommendations: list[Any],
        label: str,
    ) -> str:
        if not recommendations:
            return f'<h3>{self._e(title)}</h3>\n<p class="empty">None</p>\n'

        items: list[str] = []
        for recommendation in recommendations:
            items.append(
                "<li>"
                f'<span class="badge change-{label}">{self._e(label.title())}</span> '
                f'<span class="technical-value">{self._wrap(recommendation.rule_id)}</span>'
                " — "
                f"{self._wrap(recommendation.title)} "
                f"({self._e(recommendation.priority)})"
                "</li>"
            )
        return f'<h3>{self._e(title)}</h3>\n<ul class="change-list">{"".join(items)}</ul>\n'

    def _severity_change_list(self, changes: list[Any]) -> str:
        if not changes:
            return '<h3>Severity Changes</h3>\n<p class="empty">None</p>\n'

        items: list[str] = []
        for change in changes:
            if change.direction == "increased":
                badge_class = "worsened"
                badge_label = "Worsened"
            else:
                badge_class = "improved"
                badge_label = "Improved"
            items.append(
                "<li>"
                f'<span class="badge change-{badge_class}">{self._e(badge_label)}</span> '
                f'<span class="technical-value">{self._wrap(change.rule_id or "No rule ID")}</span>'
                " — "
                f"{self._wrap(change.title)}: "
                f"{self._e(change.previous_severity)} → "
                f"{self._e(change.current_severity)}"
                "</li>"
            )
        return f'<h3>Severity Changes</h3>\n<ul class="change-list">{"".join(items)}</ul>\n'

    def _priority_change_list(self, changes: list[Any]) -> str:
        if not changes:
            return '<h3>Priority Changes</h3>\n<p class="empty">None</p>\n'

        items: list[str] = []
        for change in changes:
            if change.direction == "increased":
                badge_class = "worsened"
                badge_label = "Worsened"
            else:
                badge_class = "improved"
                badge_label = "Improved"
            items.append(
                "<li>"
                f'<span class="badge change-{badge_class}">{self._e(badge_label)}</span> '
                f'<span class="technical-value">{self._wrap(change.rule_id)}</span>'
                " — "
                f"{self._wrap(change.title)}: "
                f"{self._e(change.previous_priority)} → "
                f"{self._e(change.current_priority)}"
                "</li>"
            )
        return f'<h3>Priority Changes</h3>\n<ul class="change-list">{"".join(items)}</ul>\n'

    def _fact_change_list(self, changes: list[Any]) -> str:
        if not changes:
            return '<h3>Repository Fact Changes</h3>\n<p class="empty">None</p>\n'

        items: list[str] = []
        for change in changes:
            items.append(
                "<li>"
                '<span class="badge change-changed">Changed</span> '
                f'<span class="technical-value">{self._wrap(change.display_text())}</span>'
                "</li>"
            )

        return f'<h3>Repository Fact Changes</h3>\n<ul class="change-list">{"".join(items)}</ul>\n'

    def _render_repository_facts(self, result: AnalysisResult) -> str:
        groups = [
            ("Structure", self._structure_fact_rows(result)),
            ("Technology", self._technology_fact_rows(result)),
            ("Build and Dependencies", self._build_dependency_fact_rows(result)),
            ("CI/CD", self._cicd_fact_rows(result)),
            ("Security", self._security_fact_rows(result)),
            ("Architecture", self._architecture_fact_rows(result)),
            ("Cloud Readiness", self._cloud_fact_rows(result)),
        ]

        group_html: list[str] = []
        for title, rows in groups:
            if not rows:
                continue
            row_html = "".join(
                f"<tr><th>{self._e(label)}</th><td>{value}</td></tr>\n" for label, value in rows
            )
            group_html.append(
                f'<div class="fact-group">\n'
                f"<h3>{self._e(title)}</h3>\n"
                f"{self._fact_table(row_html)}"
                f"</div>\n"
            )

        if not group_html:
            body = '<p class="empty">No repository facts were populated.</p>\n'
        else:
            body = '<div class="fact-groups">\n' + "".join(group_html) + "</div>\n"

        return f'<section class="section">\n<h2>Repository Facts</h2>\n{body}</section>\n'

    def _structure_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        structure = result.facts.structure
        if structure is None:
            return []

        rows: list[tuple[str, str]] = []
        self._add_int_row(rows, "File count", structure.file_count)
        self._add_int_row(rows, "Source files", structure.source_file_count)
        self._add_int_row(rows, "Test files", structure.test_file_count)
        self._add_int_row(rows, "Applications", structure.application_count)
        self._add_bool_row(rows, "Has tests", structure.has_tests)
        self._add_list_row(
            rows,
            "Architecture layers",
            structure.architecture_layers,
            presentation="badges",
        )
        return rows

    def _technology_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        technology = result.facts.technology
        if technology is None:
            return []

        rows: list[tuple[str, str]] = []
        self._add_list_row(
            rows,
            "Languages",
            technology.programming_languages,
            presentation="badges",
        )
        self._add_list_row(
            rows,
            "Frameworks",
            technology.frameworks,
            presentation="badges",
        )
        self._add_list_row(
            rows,
            "Build tools",
            technology.build_tools,
            presentation="badges",
        )
        self._add_list_row(
            rows,
            "Test frameworks",
            technology.test_frameworks,
            presentation="badges",
        )
        self._add_list_row(
            rows,
            "Detected technologies",
            technology.detected_technologies,
            presentation="badges",
        )
        return rows

    def _build_dependency_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        build = result.facts.build
        if build is not None:
            self._add_list_row(
                rows,
                "Build systems",
                build.build_systems,
                presentation="badges",
            )
            self._add_list_row(rows, "Build files", build.build_files)
            self._add_list_row(rows, "Wrapper files", build.wrapper_files)
            self._add_list_row(rows, "Lock files", build.lock_files)
            self._add_list_row(
                rows,
                "Packaging types",
                build.packaging_types,
                presentation="badges",
            )
            self._add_bool_row(rows, "Multi-module", build.multi_module)
            self._add_list_row(rows, "Modules", build.modules)
            self._add_list_row(rows, "Build plugins", build.plugins)
            self._add_list_row(rows, "Inferred commands", build.inferred_commands)

        dependencies = result.facts.dependencies
        if dependencies is not None:
            count = dependencies.dependency_count or dependencies.direct_dependency_count
            rows.append(("Dependency count", self._e(str(count))))
            self._add_int_row(
                rows,
                "Direct dependencies",
                dependencies.direct_dependency_count,
            )
            self._add_list_row(
                rows,
                "Framework dependencies",
                dependencies.framework_dependencies,
            )
            self._add_list_row(
                rows,
                "Database libraries",
                dependencies.database_drivers,
            )
            self._add_list_row(
                rows,
                "Cloud SDKs",
                dependencies.cloud_sdks,
            )
            self._add_list_row(
                rows,
                "Testing libraries",
                dependencies.testing_libraries,
            )
            self._add_list_row(
                rows,
                "Outdated dependencies",
                dependencies.outdated_dependencies,
            )
        return rows

    def _cicd_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        cicd = result.facts.cicd
        if cicd is None:
            return []

        rows: list[tuple[str, str]] = []
        platforms = cicd.ci_platforms or cicd.providers
        self._add_list_row(rows, "CI platforms", platforms, presentation="badges")
        self._add_bool_row(rows, "Has CI", cicd.has_ci)
        self._add_bool_row(rows, "Has deployment workflow", cicd.has_deployment_workflow)
        self._add_int_row(rows, "Pipeline count", cicd.pipeline_count)
        self._add_list_row(rows, "Pipeline files", cicd.pipeline_files)

        workflow_actions = self._pipeline_metadata_values(cicd.pipelines, "actions")
        self._add_list_row(rows, "Workflow actions", workflow_actions)

        build_commands = self._pipeline_command_values(cicd.pipelines, "build_commands")
        test_commands = self._pipeline_command_values(cicd.pipelines, "test_commands")
        deployment_commands = self._pipeline_command_values(
            cicd.pipelines,
            "deployment_commands",
        )
        self._add_list_row(rows, "Build commands", build_commands)
        self._add_list_row(rows, "Test commands", test_commands)
        self._add_list_row(rows, "Deployment commands", deployment_commands)
        return rows

    def _security_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        security = result.facts.security
        if security is None:
            return []

        rows: list[tuple[str, str]] = []
        self._add_int_row(rows, "Sensitive files", security.sensitive_file_count)
        self._add_int_row(rows, "Secret findings", security.secret_finding_count)
        self._add_int_row(rows, "Weak crypto findings", security.weak_crypto_count)
        self._add_int_row(
            rows,
            "Dangerous execution findings",
            security.dangerous_execution_count,
        )
        return rows

    def _architecture_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        architecture = result.facts.architecture
        if architecture is None:
            return []

        rows: list[tuple[str, str]] = []
        self._add_bool_row(rows, "API layer", architecture.has_api_layer)
        self._add_bool_row(rows, "Service layer", architecture.has_service_layer)
        self._add_bool_row(
            rows,
            "Persistence layer",
            architecture.has_persistence_layer,
        )
        self._add_bool_row(rows, "Domain layer", architecture.has_domain_layer)
        self._add_bool_row(
            rows,
            "Multi-application",
            architecture.is_multi_application,
        )
        return rows

    def _cloud_fact_rows(
        self,
        result: AnalysisResult,
    ) -> list[tuple[str, str]]:
        cloud = result.facts.cloud
        if cloud is None:
            return []

        rows: list[tuple[str, str]] = []
        self._add_list_row(
            rows,
            "Cloud capabilities",
            cloud.cloud_capabilities,
            presentation="badges",
        )
        self._add_bool_row(rows, "Docker", cloud.has_docker)
        self._add_bool_row(rows, "Dev Container", cloud.has_devcontainer)
        self._add_bool_row(rows, "Docker Compose", cloud.has_docker_compose)
        self._add_bool_row(rows, "Kubernetes", cloud.has_kubernetes)
        self._add_bool_row(rows, "Helm", cloud.has_helm)
        self._add_bool_row(rows, "Terraform", cloud.has_terraform)
        self._add_bool_row(rows, "CloudFormation", cloud.has_cloudformation)
        self._add_bool_row(rows, "Serverless", cloud.has_serverless)
        return rows

    def _render_findings(self, result: AnalysisResult) -> str:
        if not result.findings:
            return (
                '<section class="section">\n'
                "<h2>Findings</h2>\n"
                '<p class="empty">No deterministic findings were detected.</p>\n'
                "</section>\n"
            )

        grouped: dict[str, list[Finding]] = {}
        for finding in self._sorted_findings(result.findings):
            category = self._display(finding.category)
            grouped.setdefault(category, []).append(finding)

        category_blocks: list[str] = []
        for category, findings in grouped.items():
            cards = "".join(self._finding_card(finding) for finding in findings)
            category_blocks.append(
                f'<div class="category-group">\n'
                f"<h3>{self._e(category.title())}</h3>\n"
                f"{cards}"
                f"</div>\n"
            )

        return (
            '<section class="section">\n'
            f"<h2>Findings ({len(result.findings)})</h2>\n"
            + "".join(category_blocks)
            + "</section>\n"
        )

    def _render_static_analysis_providers(self, result: AnalysisResult) -> str:
        if not result.static_analysis_results:
            return ""

        rows = "".join(
            (
                "<tr>"
                f'<td class="technical-value">{self._wrap(item.provider_name)}</td>'
                f"<td>{self._e(item.status.value)}</td>"
                f'<td class="technical-value">'
                f"{self._wrap(item.provider_version or '—')}"
                "</td>"
                f"<td>{item.files_analyzed}</td>"
                f"<td>{len(item.findings)}</td>"
                f"<td>"
                f"{self._e(str(item.duration_ms) if item.duration_ms is not None else '—')}"
                f"</td>"
                f'<td class="technical-value">'
                f"{self._wrap(item.error_message or '; '.join(item.warnings) or '—')}"
                "</td>"
                "</tr>\n"
            )
            for item in result.static_analysis_results
        )

        provider_table = wrap_table(
            '<table class="facts provider-summary">\n'
            "<thead><tr><th>Provider</th><th>Status</th><th>Version</th>"
            "<th>Files</th><th>Findings</th><th>Duration (ms)</th><th>Notes</th></tr></thead>\n"
            f"<tbody>{rows}</tbody>\n"
            "</table>\n",
            css_class="table-wrapper provider-summary-wrapper",
        )

        return (
            '<section class="section provider-summary-section">\n'
            "<h2>Static Analysis Providers</h2>\n"
            f"{provider_table}"
            "</section>\n"
        )

    def _finding_card(self, finding: Finding) -> str:
        technologies = (
            render_collection(
                finding.affected_technologies,
                presentation="badges",
                threshold=self.collection_collapse_threshold,
            )
            if finding.affected_technologies
            else self._e("None")
        )
        evidence = self._evidence_list(finding.evidence)
        provider_badges = self._provider_badges(finding)

        return (
            '<article class="card finding-card">\n'
            '<div class="card-header">\n'
            f"{self._severity_badge(finding.severity)}"
            f"{provider_badges}"
            f'<span class="rule-id technical-value">'
            f"{self._wrap(finding.rule_id or 'No rule ID')}"
            "</span>\n"
            f"<h4>{self._wrap(finding.title)}</h4>\n"
            "</div>\n"
            f"<p>{self._wrap(finding.description)}</p>\n"
            '<div class="affected-technologies">\n'
            "<strong>Affected technologies:</strong>\n"
            f"{technologies}\n"
            "</div>\n"
            f'<div class="evidence">{evidence}</div>\n'
            "</article>\n"
        )

    def _provider_badges(self, finding: Finding) -> str:
        provider_name = finding.metadata.get("provider_name")
        if not isinstance(provider_name, str) or not provider_name:
            return ""

        badges = [f'<span class="badge provider">{self._wrap(provider_name)}</span>']
        priority = finding.metadata.get("original_priority")
        if priority is not None:
            badges.append(
                f'<span class="badge category">{self._wrap(provider_name)} priority '
                f"{self._e(str(priority))}</span>"
            )
        ruleset = finding.metadata.get("ruleset")
        if isinstance(ruleset, str) and ruleset:
            label = ruleset.rsplit("/", maxsplit=1)[-1].removesuffix(".xml")
            badges.append(f'<span class="badge category">{self._wrap(label)}</span>')
        return "".join(badges)

    def _render_recommendations(self, result: AnalysisResult) -> str:
        if not result.recommendations:
            return (
                '<section class="section">\n'
                "<h2>Modernization Recommendations</h2>\n"
                '<p class="empty">No modernization recommendations were generated.</p>\n'
                "</section>\n"
            )

        cards = "".join(
            self._recommendation_card(recommendation) for recommendation in result.recommendations
        )

        return (
            '<section class="section">\n'
            f"<h2>Modernization Recommendations ({len(result.recommendations)})</h2>\n"
            f"{cards}"
            "</section>\n"
        )

    def _recommendation_card(self, recommendation: Recommendation) -> str:
        actions = recommendation.actions or [recommendation.description]
        actions_html = (
            "<ul>"
            + "".join(
                f'<li class="technical-value">{self._wrap(action)}</li>' for action in actions
            )
            + "</ul>"
        )
        related = (
            ", ".join(self._wrap(item) for item in recommendation.related_finding_ids)
            if recommendation.related_finding_ids
            else self._e("None")
        )

        return (
            '<article class="card recommendation-card">\n'
            '<div class="card-header">\n'
            f"{self._priority_badge(recommendation.priority)}"
            f'<span class="badge category">'
            f"{self._e(self._display(recommendation.category))}"
            "</span>\n"
            f'<span class="rule-id technical-value">'
            f"{self._wrap(recommendation.rule_id)}"
            "</span>\n"
            f"<h4>{self._wrap(recommendation.title)}</h4>\n"
            "</div>\n"
            f"<p><strong>Rationale:</strong> {self._wrap(recommendation.rationale)}</p>\n"
            f"<div><strong>Proposed actions:</strong>{actions_html}</div>\n"
            "<p>"
            f"<strong>Effort:</strong> {self._e(self._display(recommendation.effort))} &nbsp; "
            f"<strong>Risk:</strong> {self._e(self._display(recommendation.risk))}"
            "</p>\n"
            f"<p><strong>Related finding IDs:</strong> {related}</p>\n"
            f'<div class="evidence">{self._evidence_list(recommendation.evidence)}</div>\n'
            "</article>\n"
        )

    def _render_roadmap(self, result: AnalysisResult) -> str:
        groups = {
            "Immediate": [
                recommendation
                for recommendation in result.recommendations
                if recommendation.priority in {Priority.CRITICAL, Priority.HIGH}
            ],
            "Near Term": [
                recommendation
                for recommendation in result.recommendations
                if recommendation.priority == Priority.MEDIUM
            ],
            "Later": [
                recommendation
                for recommendation in result.recommendations
                if recommendation.priority == Priority.LOW
            ],
        }

        group_blocks: list[str] = []
        for title, recommendations in groups.items():
            if not recommendations:
                items = '<li class="empty-item">None</li>'
            else:
                items = "".join(
                    (
                        "<li>"
                        f"{self._priority_badge(recommendation.priority)}"
                        f" {self._e(recommendation.title)}"
                        "</li>"
                    )
                    for recommendation in recommendations
                )
            group_blocks.append(
                f'<div class="roadmap-group">\n'
                f"<h3>{self._e(title)}</h3>\n"
                f"<ul>{items}</ul>\n"
                f"</div>\n"
            )

        return (
            '<section class="section">\n'
            "<h2>Prioritized Roadmap</h2>\n"
            '<div class="roadmap-grid">\n' + "".join(group_blocks) + "</div>\n"
            "</section>\n"
        )

    def _render_assessment_summary(self, result: AnalysisResult) -> str:
        critical_risks = sum(finding.severity == Severity.CRITICAL for finding in result.findings)
        high_priority_recommendations = sum(
            recommendation.priority in {Priority.CRITICAL, Priority.HIGH}
            for recommendation in result.recommendations
        )
        security_findings = sum(
            self._display(finding.category) == "security" for finding in result.findings
        )

        cloud = result.facts.cloud
        cloud_capabilities = (
            ", ".join(cloud.cloud_capabilities)
            if cloud is not None and cloud.cloud_capabilities
            else "None detected"
        )

        cicd = result.facts.cicd
        if cicd is None:
            cicd_status = "Unknown"
        elif cicd.has_ci:
            cicd_status = "CI detected"
            if cicd.has_deployment_workflow:
                cicd_status += " with deployment workflow"
            else:
                cicd_status += " without deployment workflow"
        else:
            cicd_status = "No CI detected"

        structure = result.facts.structure
        if structure is None or structure.has_tests is None:
            test_status = "Unknown"
        elif structure.has_tests:
            test_status = "Tests detected"
        else:
            test_status = "No tests detected"

        rows = [
            ("Critical risks", str(critical_risks)),
            ("High-priority recommendations", str(high_priority_recommendations)),
            ("Security findings", str(security_findings)),
            ("Cloud capabilities", cloud_capabilities),
            ("CI/CD status", cicd_status),
            ("Test status", test_status),
        ]
        row_html = "".join(
            f"<tr><th>{self._e(label)}</th>"
            f'<td class="technical-value">{self._wrap(value)}</td></tr>\n'
            for label, value in rows
        )

        return (
            '<section class="section">\n'
            "<h2>Assessment Summary</h2>\n"
            f"{self._fact_table(row_html)}"
            "</section>\n"
        )

    def _render_footer(self, result: AnalysisResult) -> str:
        version = result.analyzer_version or "unknown"
        return (
            '<footer class="report-footer">\n'
            f"<p>Generated by CodeStrata {self._e(version)}. "
            "This report contains only deterministic analysis results.</p>\n"
            f'<p class="print-meta">Repository: {self._e(result.repository.name)} | '
            f"Scan timestamp: {self._e(self._scan_timestamp(result))}</p>\n"
            "</footer>\n"
        )

    def _evidence_list(self, evidence_items: list[Evidence]) -> str:
        if not evidence_items:
            return "<p><strong>Evidence:</strong> None provided.</p>"

        items: list[str] = []
        for item in evidence_items:
            location = format_evidence_item_location(item)
            parts = [
                f'<span class="technical-value evidence-location">{self._wrap(location)}</span>'
            ]
            if item.description:
                parts.append(f" — {self._wrap(item.description)}")
            if item.detected_value:
                parts.append(
                    f' (detected: <span class="technical-value">'
                    f"{self._wrap(item.detected_value)}"
                    "</span>)"
                )
            items.append(f"<li>{''.join(parts)}</li>")

        return f'<p><strong>Evidence:</strong></p><ul class="evidence-list">{"".join(items)}</ul>'

    def _sorted_findings(self, findings: list[Finding]) -> list[Finding]:
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        return sorted(
            findings,
            key=lambda finding: (
                severity_order.get(finding.severity, 99),
                self._display(finding.category),
                finding.rule_id or "",
            ),
        )

    def _dependency_count(self, result: AnalysisResult) -> str:
        dependencies = result.facts.dependencies
        if dependencies is None:
            return "Unknown"
        return str(dependencies.dependency_count or dependencies.direct_dependency_count)

    def _scan_timestamp(self, result: AnalysisResult) -> str:
        timestamp = result.completed_at or result.started_at
        return timestamp.isoformat()

    def _pipeline_metadata_values(
        self,
        pipelines: list[Any],
        key: str,
    ) -> list[str]:
        values: list[str] = []
        for pipeline in pipelines:
            metadata = getattr(pipeline, "metadata", {}) or {}
            raw = metadata.get(key)
            if isinstance(raw, list):
                values.extend(str(item) for item in raw if item)
            elif isinstance(raw, str) and raw:
                values.append(raw)
        return list(dict.fromkeys(values))

    def _pipeline_command_values(
        self,
        pipelines: list[Any],
        attribute: str,
    ) -> list[str]:
        values: list[str] = []
        for pipeline in pipelines:
            commands = getattr(pipeline, attribute, None) or []
            values.extend(str(command) for command in commands if command)
        return list(dict.fromkeys(values))

    def _fact_table(self, row_html: str) -> str:
        return wrap_table(
            f'<table class="facts fact-table">\n{row_html}</table>\n',
        )

    def _add_int_row(
        self,
        rows: list[tuple[str, str]],
        label: str,
        value: int | None,
    ) -> None:
        if value is None:
            return
        rows.append((label, self._e(str(value))))

    def _add_bool_row(
        self,
        rows: list[tuple[str, str]],
        label: str,
        value: bool | None,
    ) -> None:
        if value is None:
            return
        rows.append((label, self._bool_label(value)))

    def _add_list_row(
        self,
        rows: list[tuple[str, str]],
        label: str,
        values: list[str] | None,
        *,
        presentation: str = "list",
    ) -> None:
        if not values:
            return
        rows.append(
            (
                label,
                render_collection(
                    values,
                    presentation=presentation,
                    threshold=self.collection_collapse_threshold,
                ),
            )
        )

    def _bool_label(self, value: bool | None) -> str:
        if value is None:
            return self._e("Unknown")
        return self._e("Yes" if value else "No")

    def _severity_badge(self, severity: Severity) -> str:
        value = self._display(severity)
        return f'<span class="badge severity-{self._e(value)}">{self._e(value.upper())}</span>'

    def _priority_badge(self, priority: Priority) -> str:
        value = self._display(priority)
        return f'<span class="badge priority-{self._e(value)}">{self._e(value.upper())}</span>'

    def _display(self, value: Any) -> str:
        raw_value = getattr(value, "value", value)
        return str(raw_value).lower()

    def _e(self, value: str) -> str:
        return escape_html(value)

    def _wrap(self, value: str) -> str:
        return escape_and_wrap(value)

    def _css(self) -> str:
        return """
:root {
  --bg: #f7f8fa;
  --surface: #ffffff;
  --text: #1f2933;
  --muted: #52606d;
  --border: #d9e2ec;
  --accent: #243b53;
  --critical: #9b1c1c;
  --high: #b44d12;
  --medium: #8a6d3b;
  --low: #0c6b58;
  --info: #334e68;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  max-width: 100%;
  overflow-x: hidden;
}
body {
  color: var(--text);
  background: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
.page {
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
  padding: 1.5rem;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.report-header, .section, .summary-card, .fact-group, .roadmap-group, .card,
.provider-summary-section, .comparison-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.report-header, .section {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}
h1, h2, h3, h4 {
  margin-top: 0;
  color: var(--accent);
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.subtitle, .empty, .report-footer { color: var(--muted); }
.meta-grid, .summary-grid, .fact-groups, .roadmap-grid {
  display: grid;
  gap: 1rem;
  min-width: 0;
  max-width: 100%;
}
.meta-grid {
  grid-template-columns: max-content minmax(0, 1fr);
}
.meta-grid dt { font-weight: 600; min-width: 0; }
.meta-grid dd {
  margin: 0;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.summary-grid, .fact-groups, .roadmap-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
}
.summary-card, .fact-group, .roadmap-group {
  padding: 1rem;
  min-width: 0;
}
.metric {
  font-size: 2rem;
  font-weight: 700;
  margin: 0.25rem 0 0.75rem;
}
.table-wrapper {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
}
table.counts, table.facts, table.provider-summary {
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
table.counts th, table.counts td,
table.facts th, table.facts td,
table.provider-summary th, table.provider-summary td {
  text-align: left;
  padding: 0.4rem 0.25rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
table.facts th, table.fact-table th {
  width: 32%;
  color: var(--muted);
  font-weight: 600;
}
.card {
  padding: 1rem;
  margin: 0.75rem 0;
  min-width: 0;
  max-width: 100%;
}
.card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.5rem;
  min-width: 0;
  max-width: 100%;
}
.card-header h4 { margin: 0; flex: 1 1 100%; min-width: 0; }
.rule-id, .technical-value, .evidence-location {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--muted);
  font-size: 0.9rem;
  max-width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
.badge {
  display: inline-block;
  max-width: 100%;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #f0f4f8;
  color: var(--text);
  font-size: 0.8rem;
  margin: 0.1rem 0.2rem 0.1rem 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
.value-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
  min-width: 0;
  max-width: 100%;
}
.affected-technologies {
  margin: 0.5rem 0;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.affected-technologies .value-badges,
.affected-technologies .expandable-collection,
.affected-technologies .value-list {
  margin-top: 0.25rem;
}
.value-list {
  list-style: none;
  margin: 0;
  padding: 0;
  min-width: 0;
  max-width: 100%;
}
.value-list li {
  margin: 0.2rem 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.expandable-collection {
  min-width: 0;
  max-width: 100%;
}
.expandable-collection details {
  margin-top: 0.35rem;
}
.expandable-collection summary {
  cursor: pointer;
  color: var(--accent);
  font-weight: 600;
}
.severity-critical, .priority-critical {
  background: #fde8e8; color: var(--critical); border-color: #f5c2c2;
}
.severity-high, .priority-high {
  background: #feecdc; color: var(--high); border-color: #f8d2b0;
}
.severity-medium, .priority-medium {
  background: #fbf1de; color: var(--medium); border-color: #ead9b0;
}
.severity-low, .priority-low {
  background: #e1f5f0; color: var(--low); border-color: #b7e2d7;
}
.severity-info { background: #e6eff8; color: var(--info); border-color: #c5d7eb; }
.badge.category { text-transform: uppercase; letter-spacing: 0.02em; }
.badge.provider { background: #e8eef7; color: #1f3b63; }
.change-list {
  margin: 0.25rem 0 1rem 1.1rem;
  padding: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.change-list li { min-width: 0; max-width: 100%; }
.change-new { background: #e6eff8; color: #243b53; }
.change-resolved { background: #e1f5f0; color: #0c6b58; }
.change-improved { background: #e1f5f0; color: #0c6b58; }
.change-worsened { background: #fde8e8; color: #9b1c1c; }
.change-changed { background: #fbf1de; color: #8a6d3b; }
.evidence-list {
  margin: 0.25rem 0 0 1.1rem;
  padding: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.roadmap-group ul { list-style: none; margin: 0; padding: 0; }
.roadmap-group li { margin: 0.4rem 0; max-width: 100%; overflow-wrap: anywhere; }
.empty-item { color: var(--muted); }
.report-footer { margin-top: 1.5rem; max-width: 100%; }
.print-meta { display: none; }
@media (max-width: 768px) {
  .page { padding: 1rem; }
  .meta-grid { grid-template-columns: 1fr; }
  .summary-grid, .fact-groups, .roadmap-grid {
    grid-template-columns: 1fr;
  }
  table.fact-table,
  table.fact-table tbody,
  table.fact-table tr,
  table.fact-table th,
  table.fact-table td {
    display: block;
    width: 100%;
  }
  table.fact-table th {
    width: 100%;
    border-bottom: none;
    padding-bottom: 0.1rem;
  }
  table.fact-table td {
    padding-top: 0.15rem;
    padding-bottom: 0.75rem;
  }
}
@media (max-width: 375px) {
  .page { padding: 0.75rem; }
  .report-header, .section { padding: 1rem; }
}
@media print {
  body { background: #fff; color: #000; overflow: visible; }
  html, body { overflow-x: visible; }
  .page { max-width: none; margin: 0; padding: 0; overflow: visible; }
  .report-header, .section, .summary-card, .fact-group, .roadmap-group {
    border-color: #999;
    box-shadow: none;
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .finding-card, .recommendation-card, .card {
    border-color: #999;
    break-inside: auto;
    page-break-inside: auto;
  }
  .badge, .summary-card {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  thead { display: table-header-group; }
  .table-wrapper { overflow: visible; }
  details > * { display: block !important; }
  details[open] > summary,
  details > summary { display: none !important; }
  .print-meta { display: block; }
  a { text-decoration: none; color: inherit; }
}
"""
