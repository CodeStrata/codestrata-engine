"""Doctor diagnostics baseline — re-export of characterization checks.

Doctor readiness behavior is implemented in ``diagnostics.py`` (same package)
so the Slice 11.1 module inventory matches the suggested structure while
keeping a single source of truth for doctor characterization.
"""

from __future__ import annotations

from verification.ai_provider_baseline.diagnostics import (
    build_doctor_report_scenarios,
    check_doctor_report_never_probes_without_mock_boundary,
    check_doctor_report_no_secrets,
    check_doctor_report_structure,
    run_diagnostics_checks,
)

# Alias for callers that prefer doctor-named entry points.
run_doctor_checks = run_diagnostics_checks

__all__ = [
    "build_doctor_report_scenarios",
    "check_doctor_report_never_probes_without_mock_boundary",
    "check_doctor_report_no_secrets",
    "check_doctor_report_structure",
    "run_diagnostics_checks",
    "run_doctor_checks",
]
