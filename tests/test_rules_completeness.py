"""Class 3 fixtures. Three per rule: violates, passes, witness missing."""

from __future__ import annotations

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import completeness


# ---- C3.parcel_identifier_unique ------------------------------------------


def test_parcel_identifier_unique_fires_on_a_repeated_number():
    found = f.run(
        completeness.parcel_identifier_unique,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "217"))),
    )
    assert len(found) == 1
    assert {s.entity_id for s in found[0].subjects} == {"K1", "K2"}


def test_parcel_identifier_unique_passes_distinct_numbers():
    found = f.run(
        completeness.parcel_identifier_unique,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "218"))),
    )
    assert found == []


def test_parcel_identifier_unique_abstains_over_undated_records():
    found = f.run(
        completeness.parcel_identifier_unique,
        f.records(undated=True, khesras=(f.khesra("K1", "217", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.subdivision_sequence_complete -------------------------------------


def _subdivided(child_numbers):
    return f.records(
        khesras=(f.khesra("P", "217"),)
        + tuple(f.khesra(f"C{n}", n, parent_khesra_id="P") for n in child_numbers)
    )


def test_subdivision_sequence_complete_fires_on_a_gap():
    found = f.run(completeness.subdivision_sequence_complete, _subdivided(["1", "3"]))
    assert len(found) == 1
    assert found[0].evidence["missing"] == "2"
    assert found[0].primary_subject.entity_id == "P"


def test_subdivision_sequence_complete_passes_a_full_run():
    assert f.run(completeness.subdivision_sequence_complete, _subdivided(["1", "2", "3"])) == []


def test_subdivision_sequence_complete_abstains_over_undated_records():
    records = f.records(
        undated=True,
        khesras=(f.khesra("P", "217", valid_from=None),
                 f.khesra("C1", "1", parent_khesra_id="P", valid_from=None)),
    )
    found = f.run(completeness.subdivision_sequence_complete, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_orphan_holding --------------------------------------------------


def _held(khesra_id="K1", khata_id="T1"):
    return f.records(
        khesras=(f.khesra("K1", "217"),),
        khatas=(f.khata("T1", "2001"),),
        holdings=(f.holding("H1", khata_id, khesra_id),),
    )


def test_no_orphan_holding_fires_on_a_dangling_parcel_reference():
    found = f.run(completeness.no_orphan_holding, _held(khesra_id="GONE"))
    assert len(found) == 1 and found[0].evidence["khesra_id"] == "GONE"


def test_no_orphan_holding_passes_when_both_ends_exist():
    assert f.run(completeness.no_orphan_holding, _held()) == []


def test_no_orphan_holding_abstains_over_undated_holdings():
    records = f.records(
        undated=True,
        khesras=(f.khesra("K1", "217", valid_from=None),),
        khatas=(f.khata("T1", "2001", valid_from=None),),
        holdings=(f.holding("H1", "T1", "GONE", valid_from=None),),
    )
    found = f.run(completeness.no_orphan_holding, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_empty_khata -----------------------------------------------------


def test_no_empty_khata_fires_on_a_khata_holding_nothing():
    """T2 holds nothing while T1 does, so the holdings table is demonstrably present."""
    records = f.records(
        khesras=(f.khesra("K1", "217"),),
        khatas=(f.khata("T1", "2001"), f.khata("T2", "2002")),
        holdings=(f.holding("H1", "T1", "K1"),),
    )
    found = f.run(completeness.no_empty_khata, records)
    assert len(found) == 1 and found[0].primary_subject.entity_id == "T2"


def test_no_empty_khata_passes_when_every_khata_holds_something():
    assert f.run(completeness.no_empty_khata, _held()) == []


def test_no_empty_khata_abstains_over_undated_holdings():
    records = f.records(
        undated=True,
        khatas=(f.khata("T1", "2001", valid_from=None),),
        holdings=(f.holding("H1", "T1", "K1", valid_from=None),),
    )
    found = f.run(completeness.no_empty_khata, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_unheld_parcel ---------------------------------------------------


def test_no_unheld_parcel_fires_on_a_parcel_no_khata_holds():
    """K2 is unheld while K1 is held, so the holdings table is demonstrably present."""
    records = f.records(
        khesras=(f.khesra("K1", "217"), f.khesra("K2", "218")),
        khatas=(f.khata("T1", "2001"),),
        holdings=(f.holding("H1", "T1", "K1"),),
    )
    found = f.run(completeness.no_unheld_parcel, records)
    assert len(found) == 1 and found[0].primary_subject.entity_id == "K2"


def test_no_unheld_parcel_does_not_fire_on_a_sub_divided_parent():
    """The parent is not a parcel anyone holds. Its children are."""
    records = f.records(
        khesras=(f.khesra("P", "217"), f.khesra("C1", "1", parent_khesra_id="P")),
        khatas=(f.khata("T1", "2001"),),
        holdings=(f.holding("H1", "T1", "C1"),),
    )
    assert f.run(completeness.no_unheld_parcel, records) == []


def test_no_unheld_parcel_abstains_over_undated_holdings():
    records = f.records(
        undated=True,
        khesras=(f.khesra("K1", "217", valid_from=None),),
        holdings=(f.holding("H1", "T1", "K1", valid_from=None),),
    )
    found = f.run(completeness.no_unheld_parcel, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_duplicate_holding ----------------------------------------------


def test_no_duplicate_holding_fires_when_a_holding_is_written_twice():
    records = f.records(
        khesras=(f.khesra("K1", "217"),),
        khatas=(f.khata("T1", "2001"),),
        holdings=(f.holding("H1", "T1", "K1"), f.holding("H2", "T1", "K1")),
    )
    found = f.run(completeness.no_duplicate_holding, records)
    assert len(found) == 1 and found[0].evidence["times"] == "2"


def test_no_duplicate_holding_passes_two_khatas_sharing_one_parcel():
    """EVIDENCE.md E1: several jamabandis under one survey number is normal."""
    records = f.records(
        khesras=(f.khesra("K1", "217"),),
        khatas=(f.khata("T1", "2001"), f.khata("T2", "2002")),
        holdings=(f.holding("H1", "T1", "K1"), f.holding("H2", "T2", "K1")),
    )
    assert f.run(completeness.no_duplicate_holding, records) == []


def test_no_duplicate_holding_abstains_over_undated_holdings():
    records = f.records(
        undated=True,
        holdings=(f.holding("H1", "T1", "K1", valid_from=None),),
    )
    found = f.run(completeness.no_duplicate_holding, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_ownerless_khata -------------------------------------------------


def test_no_ownerless_khata_fires_when_nobody_is_named():
    """T2 names nobody while T1 does, so the membership table is demonstrably present."""
    records = f.records(
        khatas=(f.khata("T1", "2001"), f.khata("T2", "2002")),
        owners=(f.owner("O1"),),
        memberships=(f.membership("M1", "T1", "O1"),),
    )
    found = f.run(completeness.no_ownerless_khata, records)
    assert len(found) == 1 and found[0].primary_subject.entity_id == "T2"


def test_no_ownerless_khata_passes_when_an_owner_is_named():
    records = f.records(
        khatas=(f.khata("T1", "2001"),), owners=(f.owner("O1"),),
        memberships=(f.membership("M1", "T1", "O1"),),
    )
    assert f.run(completeness.no_ownerless_khata, records) == []


def test_no_ownerless_khata_abstains_over_undated_memberships():
    records = f.records(
        undated=True, khatas=(f.khata("T1", "2001", valid_from=None),),
        memberships=(f.membership("M1", "T1", "O1", valid_from=None),),
    )
    found = f.run(completeness.no_ownerless_khata, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.khata_number_unique ------------------------------------------------


def test_khata_number_unique_fires_on_a_repeated_number():
    found = f.run(
        completeness.khata_number_unique,
        f.records(khatas=(f.khata("T1", "2001"), f.khata("T2", "2001"))),
    )
    assert len(found) == 1 and {s.entity_id for s in found[0].subjects} == {"T1", "T2"}


def test_khata_number_unique_passes_distinct_numbers():
    found = f.run(
        completeness.khata_number_unique,
        f.records(khatas=(f.khata("T1", "2001"), f.khata("T2", "2002"))),
    )
    assert found == []


def test_khata_number_unique_abstains_over_undated_khatas():
    found = f.run(
        completeness.khata_number_unique,
        f.records(undated=True, khatas=(f.khata("T1", "2001", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.no_cyclic_parentage ------------------------------------------------


def test_no_cyclic_parentage_fires_on_a_loop():
    records = f.records(
        khesras=(f.khesra("A", "1", parent_khesra_id="B"),
                 f.khesra("B", "2", parent_khesra_id="A")),
    )
    found = f.run(completeness.no_cyclic_parentage, records)
    assert len(found) == 1 and found[0].evidence["khesras"] == "A, B"


def test_no_cyclic_parentage_passes_a_tree():
    records = f.records(
        khesras=(f.khesra("P", "217"), f.khesra("C1", "1", parent_khesra_id="P")),
    )
    assert f.run(completeness.no_cyclic_parentage, records) == []


def test_no_cyclic_parentage_abstains_over_undated_records():
    found = f.run(
        completeness.no_cyclic_parentage,
        f.records(undated=True, khesras=(f.khesra("K1", "217", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.records_belong_to_this_mouza ---------------------------------------


def test_records_belong_to_this_mouza_fires_on_a_foreign_parcel():
    found = f.run(
        completeness.records_belong_to_this_mouza,
        f.records(khesras=(f.khesra("K1", "217", mouza_id="OTHER"),)),
    )
    assert len(found) == 1 and found[0].evidence["parcel_mouza"] == "OTHER"


def test_records_belong_to_this_mouza_passes_a_consistent_set():
    found = f.run(
        completeness.records_belong_to_this_mouza,
        f.records(khesras=(f.khesra("K1", "217"),), khatas=(f.khata("T1", "2001"),)),
    )
    assert found == []


def test_records_belong_to_this_mouza_abstains_over_undated_records():
    found = f.run(
        completeness.records_belong_to_this_mouza,
        f.records(undated=True, khesras=(f.khesra("K1", "217", valid_from=None),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C3.classification_is_known --------------------------------------------


def test_classification_is_known_fires_on_a_code_no_scheme_defines():
    records = f.records(
        khesras=(f.khesra("K1", "217", tenure="not_a_real_class",
                          classification_scheme="bihar.khatiyan"),)
    )
    found = f.run(completeness.classification_is_known, records, schemes=f.SCHEMES)
    assert len(found) == 1 and found[0].evidence["tenure"] == "not_a_real_class"


def test_classification_is_known_passes_a_defined_code():
    records = f.records(
        khesras=(f.khesra("K1", "217", tenure="raiyati",
                          classification_scheme="bihar.khatiyan"),)
    )
    assert f.run(completeness.classification_is_known, records, schemes=f.SCHEMES) == []


def test_classification_is_known_abstains_on_unclassified_jamabandi_input():
    found = f.run(
        completeness.classification_is_known,
        f.records(khesras=(f.khesra("K1", "217"),)),
        schemes=f.SCHEMES,
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "khesra.tenure"


def test_classification_is_known_abstains_when_no_schemes_were_supplied():
    records = f.records(
        khesras=(f.khesra("K1", "217", tenure="raiyati",
                          classification_scheme="bihar.khatiyan"),)
    )
    found = f.run(completeness.classification_is_known, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- absence of a whole record type is a missing witness, not an error ------
#
# Found by tests/test_engine_end_to_end.py. A record set holding parcels but no
# khata table at all is not a set of orphaned parcels; it is a set with no
# tenurial witness. Firing CERTAIN_ERROR there would have flagged every parcel of
# any extract that omitted the holdings table.


def test_no_unheld_parcel_abstains_when_no_holding_exists_at_all():
    found = f.run(
        completeness.no_unheld_parcel,
        f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "218"))),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "holding records"


def test_no_empty_khata_abstains_when_no_holding_exists_at_all():
    found = f.run(completeness.no_empty_khata, f.records(khatas=(f.khata("T1", "2001"),)))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


def test_no_ownerless_khata_abstains_when_no_membership_exists_at_all():
    found = f.run(completeness.no_ownerless_khata, f.records(khatas=(f.khata("T1", "2001"),)))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


def test_but_a_genuine_orphan_still_fires_when_the_table_is_present():
    """The distinction that matters: absent table abstains, absent row reports."""
    records = f.records(
        khesras=(f.khesra("K1", "217"), f.khesra("K2", "218")),
        khatas=(f.khata("T1", "2001"),),
        holdings=(f.holding("H1", "T1", "K1"),),
    )
    found = f.run(completeness.no_unheld_parcel, records)
    assert len(found) == 1
    assert found[0].finding_class is FindingClass.CERTAIN_ERROR
    assert found[0].primary_subject.entity_id == "K2"
