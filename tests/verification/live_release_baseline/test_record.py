"""Independent fixtures for live-version recording (never copy pyproject/tags)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from verification.live_release_baseline.models import InferenceError
from verification.live_release_baseline.record import (
    load_recorded,
    parse_pypi_project,
    refuse_pyproject_inference,
    unused_git_tags,
)


def test_live_version_comes_from_pypi_json_not_pyproject() -> None:
    payload = {
        "info": {"name": "codestrata", "version": "9.9.9", "yanked": False},
        "releases": {
            "9.9.9": [
                {
                    "filename": "codestrata-9.9.9-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "size": 12,
                    "url": "https://example.test/codestrata-9.9.9-py3-none-any.whl",
                    "yanked": False,
                    "digests": {"sha256": "aa" * 32},
                }
            ]
        },
    }
    project = parse_pypi_project(payload)
    assert project.live_version == "9.9.9"
    refuse_pyproject_inference(pypi=project, pyproject_version="0.2.1")
    assert project.live_version != "0.2.1"


def test_missing_pypi_releases_refuses_pyproject_fallback() -> None:
    with pytest.raises(InferenceError, match="refusing"):
        parse_pypi_project({"info": {"name": "codestrata", "version": ""}, "releases": {}})
    with pytest.raises(InferenceError, match="refusing to treat pyproject"):
        refuse_pyproject_inference(pypi=None, pyproject_version="0.2.1")


def test_empty_file_list_is_not_a_live_release() -> None:
    payload = {
        "info": {"name": "codestrata", "version": "0.2.1"},
        "releases": {"0.2.1": []},
    }
    with pytest.raises(InferenceError, match="no distributable files"):
        parse_pypi_project(payload)


def test_info_version_absent_from_releases_is_not_filled_from_tags() -> None:
    payload = {
        "info": {"name": "codestrata", "version": "0.9.0"},
        "releases": {
            "0.2.1": [
                {
                    "filename": "codestrata-0.2.1.tar.gz",
                    "packagetype": "sdist",
                    "size": 1,
                    "url": "https://example.test/sdist",
                    "digests": {"sha256": "bb" * 32},
                }
            ]
        },
    }
    with pytest.raises(InferenceError, match="tag/pyproject"):
        parse_pypi_project(payload)


def test_git_tags_are_recorded_as_unused_when_not_on_pypi() -> None:
    payload = {
        "info": {"name": "codestrata", "version": "0.2.1"},
        "releases": {
            "0.2.1": [
                {
                    "filename": "codestrata-0.2.1-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "size": 1,
                    "url": "https://example.test/whl",
                    "digests": {"sha256": "cc" * 32},
                }
            ]
        },
    }
    project = parse_pypi_project(payload)
    unused = unused_git_tags(project, ("v0.1.0", "v0.2.0", "v0.2.1"))
    assert unused == ("v0.1.0", "v0.2.0")


def test_recorded_r01_cannot_be_relabeled_present(tmp_path: Path) -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "verification"
        / "live_release_baseline"
        / "recorded.yaml"
    )
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    # Forbidden relabel: claim PRESENT while embedded workflow inventory is still BLOCKED.
    payload["r01"]["status"] = "PRESENT"
    payload["r01"]["engine_only_oidc_publisher"] = ".github/workflows/engine-pypi-release.yml"
    payload["r01"]["workflows"] = [
        item
        for item in payload["r01"]["workflows"]
        if "engine-pypi-release" not in str(item.get("path", ""))
    ]
    fake = tmp_path / "recorded.yaml"
    fake.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(InferenceError, match="disagrees"):
        load_recorded(fake)
