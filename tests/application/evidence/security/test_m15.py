"""M15 classification quality: confusion counts and promotion bar (E06.3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from codestrata.application.evidence.security.classification import (
    CANARY,
    LabelCase,
    expand_cases,
    load_label_manifest,
    m15_ratio,
    manifest_digest,
    publish_classification,
)
from codestrata.domain.contracts.enums import MetricStatus


def test_zero_denominator_is_undefined_not_100() -> None:
    empty = m15_ratio(0, 0)
    assert empty.status is MetricStatus.UNKNOWN
    assert empty.serialized is None
    assert empty.reason == "zero_denominator"
    value = m15_ratio(19, 20)
    assert value.status is MetricStatus.VALUE
    assert value.serialized == "0.950000"


def test_label_manifest_is_frozen_with_independent_review() -> None:
    document = load_label_manifest()
    assert document["metadata"]["frozen_before_tuning"] is True
    assert document["review"]["independent"] == "Abhinav"
    assert "independent_decision" not in document["review"]
    assert document["review"]["no_cherry_picked_exclusions"] is True
    cases = expand_cases(document)
    published = [item for item in cases if item.split == "published"]
    holdout = [item for item in cases if item.split == "holdout"]
    unsupported = [item for item in cases if item.expected == "unsupported"]
    groups = {item.group for item in published if item.expected != "unsupported"}
    assert groups == {
        "security.secrets",
        "security.configuration",
        "security.known_vulnerability",
        "security.license",
        "dependency.hygiene",
    }
    for group in groups:
        positives = [
            item for item in published if item.group == group and item.expected == "positive"
        ]
        negatives = [
            item for item in published if item.group == group and item.expected == "negative"
        ]
        assert len(positives) >= 20
        assert len(negatives) >= 20
    assert holdout
    assert unsupported
    published_fixtures = {item.fixture for item in published}
    holdout_fixtures = {item.fixture for item in holdout}
    assert published_fixtures.isdisjoint(holdout_fixtures)
    _assert_distinct_flagship_inputs(cases)
    assert manifest_digest()


def _published_input_key(item: LabelCase) -> tuple[object, ...]:
    if item.group == "security.known_vulnerability":
        return (
            item.version,
            item.introduced,
            item.fixed,
            item.last_affected,
            item.limit,
            item.listed,
            item.withdrawn,
        )
    if item.group == "security.license":
        return (item.expression,)
    if item.group == "dependency.hygiene":
        return (
            item.rule_id,
            item.fixture,
            item.identity,
            item.raw_version,
            item.resolved,
            item.other_version,
        )
    return (item.rule_id, item.fixture, item.header, item.path, item.text)


def _assert_distinct_flagship_inputs(cases: list[LabelCase]) -> None:
    """Published bars are not one fixture or one input repeated to reach 20."""

    published = [
        item
        for item in cases
        if item.split == "published" and item.expected in {"positive", "negative"}
    ]
    groups = {item.group for item in published}
    for group in groups:
        for expected in ("positive", "negative"):
            items = [
                item for item in published if item.group == group and item.expected == expected
            ]
            if len(items) < 20:
                continue
            keys = [_published_input_key(item) for item in items]
            assert len(keys) == len(set(keys)), f"{group}/{expected} repeats an input"
            assert all(keys)


def test_repeated_fixture_to_twenty_fails_distinctness() -> None:
    copies = [
        LabelCase(
            case_id=f"secrets-copy-{index:03d}",
            group="security.secrets",
            rule_id="security.private-key-material",
            expected="positive",
            split="published",
            fixture="planted_pem",
            supported=True,
            index=index,
        )
        for index in range(1, 21)
    ]
    with pytest.raises(AssertionError, match="repeats an input"):
        _assert_distinct_flagship_inputs(copies)


def test_published_confusion_meets_proposed_bar_without_canary_leak() -> None:
    report = publish_classification()
    assert report.frozen_before_tuning is True
    assert not hasattr(report, "independent_decision")
    assert report.canary_leaked is False
    assert report.legal_compliance_verdict is False
    assert report.cherry_picked_exclusions is False
    assert report.unsupported_disclosed
    dumped = report.model_dump_json()
    assert CANARY not in dumped
    assert "independent_decision" not in dumped
    for group in report.groups:
        assert group.labeled_positives >= 20
        assert group.labeled_negatives >= 20
        assert group.precision_status == "value"
        assert group.recall_status == "value"
        assert Decimal(group.precision or "0") >= Decimal("0.95")
        assert Decimal(group.recall or "0") >= Decimal("0.90")
        assert group.unexplained_unknown == 0
        assert group.fp == 0
        assert group.fn == 0
    for group in report.holdout:
        assert group.precision_status == "value"
        assert Decimal(group.precision or "0") >= Decimal("0.95")
        assert Decimal(group.recall or "0") >= Decimal("0.90")
    assert report.promotion_blocked is False
    assert report.block_reasons == ()
