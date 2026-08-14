"""Documentation validation tests (Phase 5.21).

Checks:
* relative markdown links resolve
* referenced example/sample paths exist
* TOML fences parse
* documented top-level CLI commands exist on the Typer app
* no stale AIMF user-facing doc names outside the rename guide
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from typer.main import get_command

from codestrata.cli import app

ENGINE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ENGINE_ROOT.parent
ROOT = ENGINE_ROOT
DOCS = ENGINE_ROOT / "docs"
# Monorepo keeps fixtures at <repo>/test-fixtures; engine export may vendor them.
if (REPO_ROOT / "test-fixtures" / "sample-js-app").is_dir():
    FIXTURES = REPO_ROOT / "test-fixtures"
    EXAMPLES = REPO_ROOT / "examples"
elif (ENGINE_ROOT / "test-fixtures" / "sample-js-app").is_dir():
    FIXTURES = ENGINE_ROOT / "test-fixtures"
    EXAMPLES = (
        ENGINE_ROOT / "examples"
        if (ENGINE_ROOT / "examples").is_dir()
        else FIXTURES
    )
else:
    FIXTURES = ENGINE_ROOT / "test-fixtures"
    EXAMPLES = ENGINE_ROOT / "examples"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TOML_FENCE_RE = re.compile(r"```toml\n(.*?)```", re.DOTALL | re.IGNORECASE)
CODESTRATA_CMD_RE = re.compile(
    r"codestrata\s+([a-z][a-z0-9-]*)",
    re.IGNORECASE,
)

# Historical phase notes may mention AIMF intentionally.
AIMF_ALLOWLIST = {
    (REPO_ROOT / "ROADMAP.md").resolve(),
    (REPO_ROOT / "CHANGELOG.md").resolve(),
    (REPO_ROOT / "ARCHITECTURE.md").resolve(),
}


def _markdown_files() -> list[Path]:
    files = list(DOCS.rglob("*.md"))
    if EXAMPLES.is_dir():
        files.extend(EXAMPLES.rglob("*.md"))
    if FIXTURES.is_dir():
        files.extend(FIXTURES.rglob("*.md"))
    files.append(ROOT / "README.md")
    files.append(ROOT / "CONTRIBUTING.md")
    monorepo_architecture = REPO_ROOT / "ARCHITECTURE.md"
    if monorepo_architecture.is_file():
        files.append(monorepo_architecture)
    return sorted({path.resolve() for path in files if path.is_file()})


def _strip_url(target: str) -> str:
    value = target.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    # Drop anchors and titles: path#anchor "title"
    value = value.split()[0]
    value = value.split("#", 1)[0]
    return value.strip()


def test_relative_markdown_links_resolve() -> None:
    missing: list[str] = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for _label, raw_target in LINK_RE.findall(text):
            target = _strip_url(raw_target)
            if not target or target.startswith(
                ("http://", "https://", "mailto:", "tel:")
            ):
                continue
            if target.startswith(("`", "#")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                try:
                    shown = path.relative_to(ROOT)
                except ValueError:
                    shown = path.relative_to(REPO_ROOT)
                missing.append(f"{shown} -> {target}")
    assert not missing, "Broken relative links:\n" + "\n".join(missing[:40])


def test_example_sample_directories_exist() -> None:
    required = [
        FIXTURES / "sample-js-app",
        FIXTURES / "sample-python-app",
        FIXTURES / "sample-java-app",
        FIXTURES / "sample-php-app",
        FIXTURES / "sample-csharp-app",
    ]
    missing = []
    for path in required:
        if path.is_dir():
            continue
        try:
            missing.append(str(path.relative_to(ROOT)))
        except ValueError:
            missing.append(str(path.relative_to(REPO_ROOT)))
    assert not missing, f"Missing fixture apps: {missing}"


def test_required_developer_docs_exist() -> None:
    required = [
        DOCS / "README.md",
        DOCS / "getting-started.md",
        DOCS / "quick-start.md",
        DOCS / "installation.md",
        DOCS / "architecture-guide.md",
        DOCS / "configuration-profiles.md",
        DOCS / "cli-reference.md",
        DOCS / "examples.md",
        DOCS / "public-contracts.md",
        DOCS / "apis.md",
        DOCS / "community-vs-platform.md",
        DOCS / "mcp" / "setup.md",
        DOCS / "mcp" / "README.md",
        DOCS / "report-interpretation.md",
        DOCS / "troubleshooting.md",
        DOCS / "contributor-guide.md",
        DOCS / "tutorial.md",
        DOCS / "community-edition.md",
        DOCS / "COMMUNITY_EDITION_CHECKLIST.md",
        ROOT / "NOTICE",
        ROOT / "SUPPORT.md",
        ROOT / "LICENSE",
        ROOT / "SECURITY.md",
        ROOT / "CODE_OF_CONDUCT.md",
        ROOT / "CONTRIBUTING.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"Missing docs: {missing}"


def test_sample_reports_exist_for_all_languages() -> None:
    base = FIXTURES / "sample-reports"
    for lang in ("javascript", "python", "java", "php", "csharp"):
        directory = base / lang
        assert (directory / "report.html").is_file(), f"missing {lang}/report.html"
        assert (directory / "report.json").is_file(), f"missing {lang}/report.json"
        assert (directory / "findings.json").is_file(), f"missing {lang}/findings.json"
        html = (directory / "report.html").read_text(encoding="utf-8")
        assert "Community Edition" in html or "CodeStrata" in html


def test_toml_fences_in_key_docs_parse() -> None:
    targets = [
        DOCS / "configuration-profiles.md",
        DOCS / "installation.md",
        DOCS / "tutorial.md",
        DOCS / "mcp" / "setup.md",
        ROOT / "README.md",
    ]
    errors: list[str] = []
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for index, block in enumerate(TOML_FENCE_RE.findall(text), start=1):
            snippet = block.strip()
            if not snippet or snippet.startswith("#"):
                # Allow comment-only illustrative fragments.
                if "=[" not in snippet and "[" not in snippet:
                    continue
            try:
                tomllib.loads(snippet)
            except Exception as error:  # noqa: BLE001
                # Accept incomplete illustrative tables that omit [repository].
                if "repository" not in snippet and "Invalid" not in str(error):
                    try:
                        tomllib.loads(f'[repository]\npath = "."\n{snippet}')
                        continue
                    except Exception as nested:  # noqa: BLE001
                        errors.append(
                            f"{path.relative_to(ROOT)} fence#{index}: {nested}"
                        )
                        continue
                errors.append(f"{path.relative_to(ROOT)} fence#{index}: {error}")
    assert not errors, "Invalid TOML fences:\n" + "\n".join(errors[:20])


def test_documented_top_level_commands_exist() -> None:
    click_cmd = get_command(app)
    registered = set(click_cmd.list_commands(None))  # type: ignore[arg-type]
    text = (DOCS / "cli-reference.md").read_text(encoding="utf-8")
    mentioned = {match.group(1).lower() for match in CODESTRATA_CMD_RE.finditer(text)}
    # Filter to likely top-level commands (single token after codestrata).
    expected = mentioned & {
        "assess",
        "scan",
        "onboard",
        "config",
        "mcp",
        "agent",
        "incremental",
        "rules",
        "evidence",
        "architecture",
        "roadmap",
        "report",
        "version",
        "about",
        "init",
        "doctor",
        "open",
        "welcome",
        "examples",
    }
    missing = sorted(expected - registered)
    assert not missing, f"CLI reference mentions missing commands: {missing}"


def test_no_stale_aimf_in_user_docs() -> None:
    offenders: list[str] = []
    for path in _markdown_files():
        if path.resolve() in AIMF_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\baimf\b", text, flags=re.IGNORECASE):
            try:
                offenders.append(str(path.relative_to(ROOT)))
            except ValueError:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, "Stale AIMF mentions:\n" + "\n".join(offenders[:20])


def test_readme_points_at_new_guides() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in (
        "docs/quick-start.md",
        "docs/installation.md",
        "docs/cli-reference.md",
        "docs/troubleshooting.md",
        "docs/tutorial.md",
        "docs/community-edition.md",
        "badge/edition-Community",
    ):
        assert needle in readme, f"README missing link to {needle}"


@pytest.mark.parametrize(
    "command",
    [
        ["--help"],
        ["version"],
        ["config", "--help"],
        ["assess", "--help"],
        ["mcp", "--help"],
    ],
)
def test_documented_commands_run_help(command: list[str]) -> None:
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
    assert "aimf" not in result.output.lower()
