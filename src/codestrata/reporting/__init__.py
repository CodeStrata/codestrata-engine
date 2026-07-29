"""Customer-facing modernization assessment reporting."""

from codestrata.reporting.assessment_json import (
    ASSESSMENT_JSON_SCHEMA_VERSION,
    build_assessment_json_document,
)
from codestrata.reporting.modernization_html import (
    CONTENT_SECURITY_POLICY,
    ModernizationHTMLReportRenderer,
)
from codestrata.reporting.modernization_models import (
    AIAttemptInfo,
    AIExecutionStage,
    AIExecutionStatus,
    AssessmentMode,
    AssessmentTiming,
    ModernizationReportError,
    ModernizationReportInput,
    ModernizationReportValidationError,
)
from codestrata.reporting.modernization_serialization import (
    modernization_report_input_from_json,
    modernization_report_input_to_json,
    write_modernization_assessment_reports,
    write_modernization_html_report,
    write_modernization_json_report,
)
from codestrata.reporting.modernization_view import (
    sanitize_display_path,
    validate_modernization_report_input,
)

__all__ = [
    "ASSESSMENT_JSON_SCHEMA_VERSION",
    "CONTENT_SECURITY_POLICY",
    "AIAttemptInfo",
    "AIExecutionStage",
    "AIExecutionStatus",
    "AssessmentMode",
    "AssessmentTiming",
    "ModernizationHTMLReportRenderer",
    "ModernizationReportError",
    "ModernizationReportInput",
    "ModernizationReportValidationError",
    "build_assessment_json_document",
    "modernization_report_input_from_json",
    "modernization_report_input_to_json",
    "sanitize_display_path",
    "validate_modernization_report_input",
    "write_modernization_assessment_reports",
    "write_modernization_html_report",
    "write_modernization_json_report",
]
