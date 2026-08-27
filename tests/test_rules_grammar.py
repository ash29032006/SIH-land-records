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


# ---- C1.area_written_matches_value ----------------------------------------


def test_area_written_matches_value_fires_when_the_string_disagrees():
    found = f.run(
        grammar.area_written_matches_value,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143, "1 acre 44 decimal")),)),
    )
    assert len(found) == 1
    assert found[0].evidence["stored_value"] == "1 acre 43 decimal"


def test_area_written_matches_value_fires_on_an_unreadable_string():
    found = f.run(
        grammar.area_written_matches_value,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143, "about an acre")),)),
    )
    assert len(found) == 1 and "cannot be read" in found[0].message


def test_area_written_matches_value_passes_a_faithful_string():
    found = f.run(
        grammar.area_written_matches_value,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143)),)),
    )
    assert found == []


def test_area_written_matches_value_abstains_without_a_written_form():
    found = f.run(
        grammar.area_written_matches_value,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(143, None)),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C1.date_ordering ------------------------------------------------------


def _mutation(mutation_id, date):
    from kavach.records import EntityType, Mutation

    return Mutation(
        id=mutation_id, mouza_id="MZ", subject_type=EntityType.KHESRA,
        subject_id="K1", date=date, valid_from=f.SURVEY,
    )


def test_date_ordering_fires_on_an_impossible_chronology():
    import datetime as dt

    found = f.run(
        grammar.date_ordering,
        f.records(mutations=(_mutation("M1", dt.date(1899, 6, 1)),)),
    )
    assert len(found) == 1
    assert found[0].primary_subject.entity_id == "M1"


def test_date_ordering_passes_a_mutation_after_the_survey():
    import datetime as dt

    found = f.run(
        grammar.date_ordering,
        f.records(mutations=(_mutation("M1", dt.date(1950, 6, 1)),)),
    )
    assert found == []


def test_date_ordering_abstains_without_a_survey_date():
    found = f.run(
        grammar.date_ordering,
        f.records(mouza=f.mouza(survey_date=None), mutations=(_mutation("M1", None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "mouza.survey_date"
