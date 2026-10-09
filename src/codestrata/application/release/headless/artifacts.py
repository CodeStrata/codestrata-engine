"""Write standard headless artifact files and compute digests (E14.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from codestrata.application.release.headless.models import HeadlessArtifactRef
from codestrata.domain.contracts.serialization import digest_canonical, dumps_canonical


def write_json_artifact(path: Path, payload: object, *, schema_name: str) -> HeadlessArtifactRef:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps_canonical(payload if isinstance(payload, dict) else _dump_model(payload))
    path.write_text(text + "\n", encoding="utf-8")
    return HeadlessArtifactRef(
        filename=path.name,
        schema_name=schema_name,
        content_digest=digest_canonical(json.loads(text)),
    )


def _dump_model(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = cast(dict[str, Any], value.model_dump(mode="json"))
        return dumped
    raise TypeError("artifact payload must be a mapping or pydantic model")
