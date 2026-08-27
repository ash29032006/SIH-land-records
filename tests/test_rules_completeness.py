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
