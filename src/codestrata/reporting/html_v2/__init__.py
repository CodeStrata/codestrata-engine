"""HTML Report v2: view-model and self-contained renderer."""

from codestrata.reporting.html_v2.builder import (
    build_customer_report_document,
    build_html_report_view_model,
    default_report_artifacts,
)
from codestrata.reporting.html_v2.models import (
    AiEnrichmentView,
    CustomerReportDocument,
    FindingView,
    HtmlReportViewModel,
    RecommendationView,
    ReportOutlineEntry,
    ReportSummary,
)
from codestrata.reporting.html_v2.renderer import CONTENT_SECURITY_POLICY, HtmlReportRenderer
from codestrata.reporting.html_v2.versions import build_highlighted_versions
from codestrata.reporting.modernization_models import HighlightedVersionInput, ReportArtifactInput

__all__ = [
    "CONTENT_SECURITY_POLICY",
    "AiEnrichmentView",
    "CustomerReportDocument",
    "FindingView",
    "HighlightedVersionInput",
    "HtmlReportRenderer",
    "HtmlReportViewModel",
    "RecommendationView",
    "ReportArtifactInput",
    "ReportOutlineEntry",
    "ReportSummary",
    "build_customer_report_document",
    "build_highlighted_versions",
    "build_html_report_view_model",
    "default_report_artifacts",
]
