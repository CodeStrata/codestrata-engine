"""Parse PMD XML reports into CodeStrata findings."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from codestrata.models.enums import FindingSource
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.static_analysis.providers.pmd_mapping import (
    build_pmd_rule_id,
    humanize_rule_name,
    map_pmd_category,
    map_pmd_priority,
)


class PmdParser:
    """Convert PMD XML output into normalized CodeStrata findings."""

    def parse(
        self,
        report_xml: str,
        *,
        repository_path: Path,
        provider_version: str | None = None,
    ) -> list[Finding]:
        """Parse a PMD XML report string."""

        try:
            root = ET.fromstring(report_xml)
        except ET.ParseError as exc:
            raise ValueError(f"Malformed PMD XML: {exc}") from exc

        findings: list[Finding] = []
        for file_element in root.findall(".//{*}file"):
            absolute_name = file_element.attrib.get("name", "")
            relative_path = self._relativize(absolute_name, repository_path)

            for violation in file_element.findall("{*}violation"):
                findings.append(
                    self._violation_to_finding(
                        violation=violation,
                        relative_path=relative_path,
                        provider_version=provider_version,
                    )
                )

        return findings

    def _violation_to_finding(
        self,
        *,
        violation: ET.Element,
        relative_path: str,
        provider_version: str | None,
    ) -> Finding:
        rule = violation.attrib.get("rule")
        ruleset = violation.attrib.get("ruleset")
        priority = self._parse_int(violation.attrib.get("priority"))
        begin_line = self._parse_int(violation.attrib.get("beginline"))
        end_line = self._parse_int(violation.attrib.get("endline"))
        begin_column = self._parse_int(violation.attrib.get("begincolumn"))
        end_column = self._parse_int(violation.attrib.get("endcolumn"))
        message = (violation.text or "").strip() or humanize_rule_name(rule)
        external_info_url = violation.attrib.get("externalInfoUrl")
        package = violation.attrib.get("package")
        class_name = violation.attrib.get("class")
        method = violation.attrib.get("method")
        variable = violation.attrib.get("variable")

        rule_id = build_pmd_rule_id(ruleset, rule)
        metadata: dict[str, object] = {
            "provider_id": "pmd",
            "provider_name": "PMD",
            "provider_version": provider_version,
            "external_rule_id": rule,
            "ruleset": ruleset,
            "original_priority": priority,
        }
        if external_info_url:
            metadata["documentation_url"] = external_info_url
        if package:
            metadata["package"] = package
        if class_name:
            metadata["class"] = class_name
        if method:
            metadata["method"] = method
        if variable:
            metadata["variable"] = variable

        evidence_metadata: dict[str, object] = {}
        if class_name:
            evidence_metadata["class"] = class_name
        if method:
            evidence_metadata["method"] = method

        return Finding(
            rule_id=rule_id,
            title=humanize_rule_name(rule),
            description=message,
            category=map_pmd_category(ruleset),
            severity=map_pmd_priority(priority),
            source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
            evidence=[
                Evidence(
                    file_path=relative_path,
                    line_number=begin_line,
                    end_line_number=end_line,
                    column_number=begin_column,
                    end_column_number=end_column,
                    description=message,
                    metadata=evidence_metadata,
                )
            ],
            affected_technologies=["Java"],
            metadata=metadata,
        )

    def _relativize(self, file_name: str, repository_path: Path) -> str:
        if not file_name:
            return "."

        candidate = Path(file_name)
        try:
            relative = candidate.resolve().relative_to(repository_path.resolve())
            return PurePosixPath(relative.as_posix()).as_posix()
        except Exception:
            normalized = file_name.replace("\\", "/")
            repo = str(repository_path.resolve()).replace("\\", "/")
            if normalized.startswith(repo.rstrip("/") + "/"):
                return normalized[len(repo.rstrip("/")) + 1 :]
            return PurePosixPath(normalized).name

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None or value == "":
            return None
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 1 else None
