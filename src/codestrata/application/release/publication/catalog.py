"""Publication catalog for candidate release blobs (E14.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from codestrata.application.release.publication.models import CatalogEntry, PublicationCatalog
from codestrata.application.release.standalone.digest import sha256_bytes, sha256_file

CatalogKind = Literal["wheel", "sdist", "sbom", "provenance", "container_recipe", "sigstore_bundle"]


def _entry(path: Path, *, kind: CatalogKind, root: Path) -> CatalogEntry:
    data = path.read_bytes()
    relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
    return CatalogEntry(
        kind=kind,
        path=relative,
        sha256=sha256_bytes(data) if len(data) <= 256 else sha256_file(path),
        bytes=len(data),
    )


def build_publication_catalog(
    *,
    output_directory: Path,
    engine_root: Path,
    wheel_path: Path,
    sdist_path: Path,
    sbom_path: Path,
    provenance_path: Path,
    bundle_path: Path | None,
) -> PublicationCatalog:
    entries: list[CatalogEntry] = [
        _entry(wheel_path, kind="wheel", root=output_directory),
        _entry(sdist_path, kind="sdist", root=output_directory),
        _entry(sbom_path, kind="sbom", root=output_directory),
        _entry(provenance_path, kind="provenance", root=output_directory),
    ]
    recipe = engine_root / "examples" / "non-root-container" / "Dockerfile"
    if recipe.is_file():
        entries.append(_entry(recipe, kind="container_recipe", root=engine_root))
    compose = engine_root / "examples" / "non-root-container" / "docker-compose.yml"
    if compose.is_file():
        entries.append(_entry(compose, kind="container_recipe", root=engine_root))
    if bundle_path is not None and bundle_path.is_file():
        entries.append(_entry(bundle_path, kind="sigstore_bundle", root=output_directory))
    return PublicationCatalog(entries=tuple(entries))
