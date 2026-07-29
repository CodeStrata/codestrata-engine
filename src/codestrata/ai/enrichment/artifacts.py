"""Persist AI enrichment artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from codestrata.domain.ai_enrichment import AiEnrichmentResult

AI_ENRICHMENT_FILENAME = "advisor.json"


class AiEnrichmentArtifactWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    written: bool = True


def write_ai_enrichment_artifact(
    result: AiEnrichmentResult,
    run_directory: Path,
) -> AiEnrichmentArtifactWriteResult:
    """Write validated advisor.json (no fabricated fallback content)."""

    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / AI_ENRICHMENT_FILENAME
    payload = result.model_dump(mode="json")
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    path.write_text(text + "\n", encoding="utf-8")
    return AiEnrichmentArtifactWriteResult(path=path)


def try_write_ai_enrichment_artifact(
    result: AiEnrichmentResult,
    run_directory: Path,
) -> AiEnrichmentArtifactWriteResult | None:
    """Best-effort enrichment artifact write; never raises."""

    try:
        return write_ai_enrichment_artifact(result, run_directory)
    except OSError:
        return None
