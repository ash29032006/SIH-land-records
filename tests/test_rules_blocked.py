"""Classes 4-7 — interfaces only. They must abstain, never pass."""

from __future__ import annotations

import fixtures as f
import pytest

from kavach.findings import Engine, FindingClass, RuleScope
from kavach.rules import BLOCKED_RULES, blocked
from kavach.units import default_registry


@pytest.mark.parametrize(
    "declared",
    [blocked.text_versus_geometry, blocked.cross_system, blocked.statistical],
    ids=lambda r: r.id,
)
def test_blocked_rules_abstain_and_name_what_they_lack(declared):
    found = f.run(declared, f.records(khesras=(f.khesra("K1", "217"),)))
    assert len(found) == 1
    assert found[0].finding_class is FindingClass.UNVERIFIABLE
    assert found[0].missing_witness
    assert found[0].evidence["status"] == "specced, no body"


def test_no_blocked_rule_can_ever_report_a_pass():
    """Stubbing these as passing is the exact failure the project argues against."""
    records = f.records(khesras=(f.khesra("K1", "217"),))
    for declared in BLOCKED_RULES:
        if declared.scope is RuleScope.WITHIN_VERSION:
            found = f.run(declared, records)
            assert found, f"{declared.id} returned nothing, which reads as a pass"
            assert all(x.is_abstention for x in found)


def test_chain_continuity_is_across_version_and_abstains_when_unpaired():
    assert blocked.chain_continuity.scope is RuleScope.ACROSS_VERSION
    result = Engine((blocked.chain_continuity,)).run(
        f.records(), default_registry(), as_of=f.TODAY
    )
    assert result.rules_run == ()
    assert len(result.abstentions) == 1


def test_the_blocked_classes_cover_four_through_seven():
    assert sorted(r.validation_class for r in BLOCKED_RULES) == [4, 5, 6, 7]
