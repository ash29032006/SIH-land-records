"""Class 2 fixtures. Three per rule: violates, passes, witness missing.

The "passes" fixture matters most here. Conservation is the flagship claim, and a
conservation rule that fires on records that do add up would discredit it.
"""

from __future__ import annotations

from fractions import Fraction

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.records import TenureTotal
from kavach.rules import conservation


# ---- C2.children_sum_to_parent --------------------------------------------


def _family(parent_units, child_units):
    return f.records(
        khesras=(f.khesra("P", "217", area_stated=f.stated(parent_units)),)
        + tuple(
            f.khesra(f"C{n}", str(n), parent_khesra_id="P", area_stated=f.stated(u))
            for n, u in enumerate(child_units, start=1)
        )
    )


def test_children_sum_to_parent_fires_when_they_do_not():
    found = f.run(conservation.children_sum_to_parent, _family(100, [40, 61]))
    assert len(found) == 1
    assert found[0].finding_class is FindingClass.CERTAIN_ERROR
    assert found[0].primary_subject.entity_id == "P"
    assert found[0].evidence["difference"] == "1 decimal"


def test_children_sum_to_parent_passes_an_exact_partition():
    assert f.run(conservation.children_sum_to_parent, _family(100, [40, 60])) == []


def test_children_sum_to_parent_abstains_when_a_sub_plot_states_no_area():
    records = f.records(
        khesras=(
            f.khesra("P", "217", area_stated=f.stated(100)),
            f.khesra("C1", "1", parent_khesra_id="P", area_stated=f.stated(40)),
            f.khesra("C2", "2", parent_khesra_id="P"),
        )
    )
    found = f.run(conservation.children_sum_to_parent, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "khesra.area_stated"
