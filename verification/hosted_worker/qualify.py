"""Checks that run inside a candidate Engine image before it can be pushed.

The image contains the published wheel only. These checks do not accept a
source checkout as the installed package.
"""

from __future__ import annotations

CHECK = r"""
import importlib.metadata as metadata
import os
import pathlib
import shutil
import subprocess
import sys

expected = os.environ["CODESTRATA_EXPECTED_VERSION"]
import codestrata

location = pathlib.Path(codestrata.__file__).as_posix()
if "site-packages" not in location or "/platform/" in location:
    sys.exit("import location is not the installed package")
if codestrata.__version__ != expected:
    sys.exit("installed version differs")
requirements = metadata.requires("codestrata") or []
for requirement in requirements:
    name = requirement.split(";", 1)[0].split("[", 1)[0].strip().lower()
    if name in {"codestrata-platform", "platform"} or name.startswith("codestrata-platform"):
        sys.exit("platform dependency")
    if " @ " in requirement or requirement.startswith("."):
        sys.exit("path dependency")
if shutil.which("codestrata") is None:
    sys.exit("wrapper command missing")
probe = pathlib.Path("/tmp/probe")
probe.write_text("ok", encoding="utf-8")
try:
    pathlib.Path("/usr/local/probe").write_text("no", encoding="utf-8")
except OSError:
    pass
else:
    sys.exit("container root is writable")
fixture = pathlib.Path("/tmp/fixture")
output_a = pathlib.Path("/tmp/out-a")
output_b = pathlib.Path("/tmp/out-b")
fixture.mkdir()
(fixture / "app.js").write_text("function ready() { return 1 }\n", encoding="utf-8")
env = os.environ.copy()
env["CODESTRATA_TELEMETRY_DISABLE"] = "1"
hashes = []
for output in (output_a, output_b):
    output.mkdir()
    completed = subprocess.run(
        ["codestrata", "assess", "--repo", str(fixture), "--no-ai", "--output", str(output)],
        check=False,
        env=env,
        timeout=180,
    )
    if completed.returncode != 0:
        sys.exit("assessment failed")
    canonical = list(output.rglob("canonical-report.json"))
    if len(canonical) != 1:
        sys.exit("canonical artifact missing")
    hashes.append(canonical[0].read_bytes())
if hashes[0] != hashes[1]:
    sys.exit("assessment output is not deterministic")
print("qualified")
"""


def qualification_script() -> str:
    return CHECK
