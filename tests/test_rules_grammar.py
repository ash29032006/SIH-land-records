"""Class 1 fixtures. Three per rule: violates, passes, witness missing.

AGENTS.md 4.2. The "passes" fixture is the false-positive guard and matters most:
a rule that fires on a correct record costs a family money.
"""

from __future__ import annotations

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import grammar


# ---- C1.subdivision_number_positive ---------------------------------------


def test_subdivision_number_positive_fires_on_zero():
    found = f.run(
        grammar.subdivision_number_positive,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "0", parent_khesra_id="K1"))),
    )
    assert len(found) == 1
    assert found[0].finding_class is FindingClass.CERTAIN_ERROR
    assert found[0].primary_subject.entity_id == "K2"
    assert found[0].evidence["local_number"] == "0"


def test_subdivision_number_positive_passes_valid_numbering():
    found = f.run(
        grammar.subdivision_number_positive,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "1", parent_khesra_id="K1"))),
    )
    assert found == []


def test_subdivision_number_positive_abstains_over_undated_records():
    found = f.run(
        grammar.subdivision_number_positive,
        f.records(undated=True, khesras=(f.khesra("K1", "0", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "validity dates"


# ---- C1.identifier_present -------------------------------------------------


def test_identifier_present_fires_on_blank_numbers():
    found = f.run(
        grammar.identifier_present,
        f.records(khesras=(f.khesra("K1", ""),), khatas=(f.khata("T1", ""),)),
    )
    assert {x.primary_subject.entity_id for x in found} == {"K1", "T1"}
    assert all(x.finding_class is FindingClass.CERTAIN_ERROR for x in found)


def test_identifier_present_passes_when_numbers_are_there():
    found = f.run(
        grammar.identifier_present,
        f.records(khesras=(f.khesra("K1", "217"),), khatas=(f.khata("T1", "2001"),)),
    )
    assert found == []


def test_identifier_present_abstains_over_undated_records():
    found = f.run(
        grammar.identifier_present,
        f.records(undated=True, khesras=(f.khesra("K1", "", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
