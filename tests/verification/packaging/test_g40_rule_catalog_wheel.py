"""G40-D001: the built wheel ships rule-catalog YAML beside the loaders."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[3]
CATALOG_MEMBER = (
    "codestrata/application/rules/technical_debt/catalog/quality.complexity.yaml"
)
LOADER_MEMBER = "codestrata/application/rules/technical_debt/yaml_catalog.py"


def test_wheel_contains_quality_complexity_yaml_beside_loader(tmp_path: Path) -> None:
    out = tmp_path / "dist"
    completed = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    assert CATALOG_MEMBER in names
    assert LOADER_MEMBER in names
    catalog = CATALOG_MEMBER.rsplit("/", 1)[0]
    loader = LOADER_MEMBER.rsplit("/", 1)[0]
    assert catalog.startswith(loader + "/")
