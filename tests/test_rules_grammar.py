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


# ---- C1.identifier_charset -------------------------------------------------


def test_identifier_charset_fires_on_a_letter_misread_for_a_digit():
    found = f.run(grammar.identifier_charset, f.records(khesras=(f.khesra("K1", "2l7"),)))
    assert len(found) == 1
    assert found[0].evidence["stray_characters"] == "l"
    assert found[0].finding_class is FindingClass.CERTAIN_ERROR


def test_identifier_charset_passes_digits_and_separators():
    found = f.run(
        grammar.identifier_charset,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "217/1")),
                  khatas=(f.khata("T1", "2001"),)),
    )
    assert found == []


def test_identifier_charset_abstains_over_undated_records():
    found = f.run(
        grammar.identifier_charset,
        f.records(undated=True, khesras=(f.khesra("K1", "2l7", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C1.area_positive ------------------------------------------------------


def test_area_positive_fires_on_zero_area():
    found = f.run(
        grammar.area_positive,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(0)),)),
    )
    assert len(found) == 1 and found[0].evidence["count"] == "0"


def test_area_positive_passes_real_areas_and_ignores_absent_ones():
    found = f.run(
        grammar.area_positive,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(100)),
                           f.khesra("K2", "218"))),
    )
    assert found == []


def test_area_positive_abstains_over_undated_records():
    found = f.run(
        grammar.area_positive,
        f.records(undated=True,
                  khesras=(f.khesra("K1", "217", area_stated=f.stated(0), valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C1.unit_carry ---------------------------------------------------------


def test_unit_carry_fires_on_an_uncarried_written_area():
    found = f.run(
        grammar.unit_carry,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143, "143 decimal")),)),
    )
    assert len(found) == 1
    assert found[0].evidence["should_read"] == "1 acre 43 decimal"
    assert found[0].evidence["over_base"] == "decimal"


def test_unit_carry_passes_a_properly_carried_area():
    found = f.run(
        grammar.unit_carry,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143)),)),
    )
    assert found == []


def test_unit_carry_abstains_when_nothing_records_how_the_area_was_written():
    found = f.run(
        grammar.unit_carry,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143, None)),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "area_stated.as_written"
