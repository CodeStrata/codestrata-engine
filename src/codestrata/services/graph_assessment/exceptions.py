"""Focused errors for the Phase 2 graph assessment pipeline."""

from __future__ import annotations


class GraphAssessmentPipelineError(RuntimeError):
    """Raised when a Phase 2 graph pipeline stage fails closed."""

    def __init__(self, stage: str, message: str) -> None:
        compact_stage = stage.strip() or "graph_pipeline"
        compact_message = message.strip() or "unknown failure"
        super().__init__(f"[{compact_stage}] {compact_message}")
        self.stage = compact_stage
        self.message = compact_message
