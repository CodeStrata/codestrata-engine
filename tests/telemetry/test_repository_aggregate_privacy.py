"""Repository aggregate privacy and boundary tests (Slice 10.5)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.analytics.repository_aggregate import (
    collect_repository_aggregate_analytics,
)
from codestrata.telemetry.analytics.repository_aggregate_extractor import (
    extract_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_projection import (
    APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES,
)
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
)


_FORBIDDEN = (
    "repository_name",
    "repository_url",
    "project_name",
    "organization",
    "customer_id",
    "branch",
    "commit",
    "file_name",
    "file_path",
    "extension",
    "package",
    "dependency",
    "framework",
    "rule_id",
    "rule_name",
    "finding",
    "evidence",
    "source_code",
    "provider",
    "model",
    "token",
    "cost",
)


def test_forbidden_not_approved() -> None:
    for field in _FORBIDDEN:
        assert field not in APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES


def test_no_filesystem_traversal(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    # Create decoy repo files that must not be read.
    decoy = tmp_path / "repo"
    decoy.mkdir()
    (decoy / "secret.py").write_text("print('x')\n", encoding="utf-8")
    identity = AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )
    event = collect_repository_aggregate_analytics(
        home=home,
        identity=identity,
        aggregate_input=extract_repository_aggregate_input(
            language_label_counts={"python": 1},
            attempted=1,
            completed=1,
            skipped=0,
            failed=0,
        ),
    )
    blob = event.to_stable_dict()
    assert "secret.py" not in str(blob)
    assert str(decoy) not in str(blob)
    assert list(home.iterdir()) == []


def test_no_platform_imports() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "codestrata"
        / "telemetry"
        / "analytics"
    )
    for path in root.glob("repository_aggregate*.py"):
        text = path.read_text(encoding="utf-8")
        assert "boto3" not in text
        assert "codestrata_platform" not in text
