"""Portable Google Sans Flex builds and honest glyph coverage."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[3]
PLEX_TTF_SHA256 = "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46"
REPORT_SAMPLES = "André José María Ørsted Łódź – — • “ ” café/naïve"
# Present in the coverage request, absent from the upstream cmap.
ABSENT_FROM_FAMILY = "→✓⚠"
UNSUPPORTED = "字م🙂"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "gsf_build",
        ROOT / "scripts/build_google_sans_flex_report_subset.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _cmap(path: Path) -> set[int]:
    font = TTFont(path)
    points: set[int] = set()
    for table in font["cmap"].tables:
        points.update(table.cmap)
    return points


def test_check_mode_is_portable_without_prior_reports() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_google_sans_flex_report_subset.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    builder = ROOT / "scripts" / "build_google_sans_flex_report_subset.py"
    assert "/tmp/br02-report-chars" not in builder.read_text(encoding="utf-8")


def test_extractor_reports_unsupported_characters_instead_of_dropping_them() -> None:
    module = _builder()
    markup = "<style>body{font-family:x}</style><script>var x=1</script><p>café 字</p>"
    text = module.extract_visible_text(markup)
    assert "café" in text
    assert "字" in text
    assert "font-family" not in text
    repertoire = module.parse_unicode_spec(module.REPORT_UNICODES)
    missing = module.unsupported_characters(text, repertoire)
    assert "é" not in missing
    assert "字" in missing


def test_report_cmap_covers_declared_repertoire() -> None:
    module = _builder()
    repertoire = module.parse_unicode_spec(module.REPORT_UNICODES)
    cmap = _cmap(ROOT / "design-system/fonts/GoogleSansFlex-report.woff2")
    needed = {ord(char) for char in REPORT_SAMPLES if not char.isspace()}
    assert needed <= cmap
    assert needed <= repertoire
    for char in ABSENT_FROM_FAMILY:
        assert ord(char) not in cmap
    font = TTFont(ROOT / "design-system/fonts/GoogleSansFlex-report.woff2")
    axes = {axis.axisTag: (axis.minValue, axis.maxValue) for axis in font["fvar"].axes}
    assert axes["wght"] == (400, 600)
    assert "GPOS" in font
    assert "GSUB" in font
    assert "HVAR" in font


def test_web_face_is_broader_than_the_report_face() -> None:
    report = _cmap(ROOT / "design-system/fonts/GoogleSansFlex-report.woff2")
    web = _cmap(ROOT / "design-system/fonts/GoogleSansFlex-web.woff2")
    assert report < web
    assert ord("ệ") in web
    assert ord("ệ") not in report


def test_unsupported_scripts_are_outside_both_faces() -> None:
    report = _cmap(ROOT / "design-system/fonts/GoogleSansFlex-report.woff2")
    web = _cmap(ROOT / "design-system/fonts/GoogleSansFlex-web.woff2")
    for char in UNSUPPORTED:
        assert ord(char) not in report
        assert ord(char) not in web


def test_ibm_plex_package_is_the_unmodified_upstream_ttf() -> None:
    packaged = ROOT / "engine/src/codestrata/reporting/html_v2/assets/IBMPlexMono-Regular.ttf"
    digest = hashlib.sha256(packaged.read_bytes()).hexdigest()
    assert digest == PLEX_TTF_SHA256
    assert digest == hashlib.sha256(
        (ROOT / "design-system/fonts/IBMPlexMono-Regular.ttf").read_bytes()
    ).hexdigest()
    assert not (ROOT / "design-system/fonts/IBMPlexMono-Regular.woff2").exists()
    css = (
        ROOT / "engine/src/codestrata/design_system/embedded_fonts.py"
    ).read_text(encoding="utf-8")
    assert "IBMPlexMono-Regular.ttf" in css
    assert "IBMPlexMono-Regular.woff2" not in css
