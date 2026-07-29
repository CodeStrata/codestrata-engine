"""Tests for PMD XML parsing."""

from pathlib import Path

from codestrata.models.enums import FindingSource, Severity
from codestrata.static_analysis.providers.pmd_parser import PmdParser


def test_parse_single_violation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "src/main/java/example/Foo.java"
    source.parent.mkdir(parents=True)
    source.write_text("class Foo {}", encoding="utf-8")

    xml = f"""<?xml version="1.0"?>
    <pmd>
      <file name="{source}">
        <violation beginline="3" endline="3" begincolumn="5" endcolumn="10"
          rule="UnusedPrivateField" ruleset="Best Practices" priority="3"
          externalInfoUrl="https://docs.example/unused"
          class="Foo" method="bar">
          Avoid unused private fields
        </violation>
      </file>
    </pmd>
    """

    findings = PmdParser().parse(xml, repository_path=repo, provider_version="7.0.0")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == FindingSource.EXTERNAL_STATIC_ANALYSIS
    assert finding.severity == Severity.MEDIUM
    assert finding.rule_id == "PMD.JAVA.BESTPRACTICES.UNUSEDPRIVATEFIELD"
    assert finding.evidence[0].file_path == "src/main/java/example/Foo.java"
    assert finding.evidence[0].line_number == 3
    assert finding.evidence[0].column_number == 5
    assert finding.metadata["provider_id"] == "pmd"
    assert finding.metadata["external_rule_id"] == "UnusedPrivateField"
    assert "Avoid unused private fields" in finding.description


def test_parse_zero_violations(tmp_path: Path) -> None:
    findings = PmdParser().parse(
        '<?xml version="1.0"?><pmd></pmd>',
        repository_path=tmp_path,
    )
    assert findings == []


def test_parse_malformed_xml(tmp_path: Path) -> None:
    try:
        PmdParser().parse("<pmd><file>", repository_path=tmp_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Malformed PMD XML" in str(exc)


def test_unicode_message(tmp_path: Path) -> None:
    repo = tmp_path
    xml = """<?xml version="1.0"?>
    <pmd>
      <file name="A.java">
        <violation beginline="1" rule="X" ruleset="design" priority="5">
          Mensagem com acento: café
        </violation>
      </file>
    </pmd>
    """
    findings = PmdParser().parse(xml, repository_path=repo)
    assert "café" in findings[0].description


def test_parse_pmd7_namespaced_xml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "src/main/java/example/Foo.java"
    source.parent.mkdir(parents=True)
    source.write_text("class Foo {}", encoding="utf-8")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         version="7.26.0">
      <file name="{source}">
        <violation beginline="2" endline="2" begincolumn="1" endcolumn="5"
          rule="UnusedPrivateField" ruleset="Best Practices" priority="3">
          Avoid unused private fields
        </violation>
      </file>
    </pmd>
    """
    findings = PmdParser().parse(xml, repository_path=repo, provider_version="7.26.0")
    assert len(findings) == 1
    assert findings[0].evidence[0].file_path == "src/main/java/example/Foo.java"
    assert findings[0].evidence[0].line_number == 2
