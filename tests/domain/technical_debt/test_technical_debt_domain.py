"""Technical debt domain foundation tests (Phase 4.3.1)."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import _CATEGORY_MAP
from codestrata.domain.findings.enums import FindingCategory
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.technical_debt.assessment.identifiers import (
    SECTION_ID,
    SECTION_SCHEMA_VERSION,
)
from codestrata.domain.technical_debt.assessment.models import TechnicalDebtAssessmentSection
from codestrata.domain.technical_debt.ids import PACK_ID, PACK_VERSION, RULE_ID_PREFIX
from codestrata.domain.technical_debt.taxonomy import (
    TECHNICAL_DEBT_CATEGORIES,
    TechnicalDebtCategory,
)
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json


def test_pack_and_section_constants_stable() -> None:
    assert PACK_ID == "technical_debt.core"
    assert PACK_VERSION == "1.0.0"
    assert RULE_ID_PREFIX == "technical_debt."
    assert SECTION_ID == "assessment.technical_debt"
    assert SECTION_SCHEMA_VERSION == "1.2.0"


def test_taxonomy_is_deterministic_and_bounded() -> None:
    assert TechnicalDebtCategory.DEPRECATED_TECHNOLOGY.value.startswith(
        "technical-debt."
    )
    assert TECHNICAL_DEBT_CATEGORIES == tuple(TechnicalDebtCategory)
    assert TECHNICAL_DEBT_CATEGORIES == tuple(TechnicalDebtCategory)


def test_finding_category_technical_debt_exists() -> None:
    assert FindingCategory.TECHNICAL_DEBT.value == "technical_debt"
    assert _CATEGORY_MAP[RuleCategory.TECHNICAL_DEBT] is FindingCategory.TECHNICAL_DEBT


def test_section_forbids_financial_fields() -> None:
    fields = TechnicalDebtAssessmentSection.model_fields
    forbidden = {
        "financial_cost",
        "cost",
        "engineering_hours",
        "effort_hours",
        "productivity_loss",
        "modernization_percentage",
        "interest_rate",
    }
    assert forbidden.isdisjoint(fields.keys())


def test_empty_section_round_trip_deterministic() -> None:
    from codestrata.application.technical_debt.assessment.assembler import (
        TechnicalDebtAssessmentAssembler,
    )

    left = TechnicalDebtAssessmentAssembler().assemble_empty(
        repository_id="repo:codestrata"
    )
    right = TechnicalDebtAssessmentAssembler().assemble_empty(
        repository_id="repo:codestrata"
    )
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    payload = dumps_stable_json(left.model_dump(mode="json"))
    restored = TechnicalDebtAssessmentSection.model_validate(loads_stable_json(payload))
    assert restored.section_id == SECTION_ID
    assert restored.finding_ids == ()
    assert restored.business_impact == "unknown"
    assert "financial-cost-not-assessed" in payload
    assert '"engineering_hours"' not in payload
    assert '"financial_cost"' not in payload
    assert '"interest_rate"' not in payload
