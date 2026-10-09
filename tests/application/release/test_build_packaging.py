"""E14.2 wheel/sdist packaging inventory checks."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from codestrata.application.release.standalone.packaging import (
    verify_public_source_export,
    verify_sdist_inventory,
    verify_wheel_inventory,
)

ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_public_source_export_paths_exist() -> None:
    result = verify_public_source_export(ENGINE_ROOT)
    assert result.ok, result.missing


@pytest.mark.parametrize("build_kind", ["wheel", "sdist"])
def test_built_artifacts_include_packaged_resources(tmp_path: Path, build_kind: str) -> None:
    dist = tmp_path / "dist"
    flag = "--wheel" if build_kind == "wheel" else "--sdist"
    completed = subprocess.run(
        [sys.executable, "-m", "build", flag, "--outdir", str(dist)],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    if build_kind == "wheel":
        wheels = list(dist.glob("*.whl"))
        assert len(wheels) == 1
        result = verify_wheel_inventory(wheels[0])
        assert result.ok, result.missing
        with zipfile.ZipFile(wheels[0]) as archive:
            assert "codestrata/resources/release/headless-runtime-limits-v1.yaml" in set(
                archive.namelist()
            )
    else:
        sdists = list(dist.glob("*.tar.gz"))
        assert len(sdists) == 1
        result = verify_sdist_inventory(sdists[0])
        assert result.ok, result.missing
