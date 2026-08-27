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


# ---- C2.leaves_sum_to_mouza (the trial balance) ---------------------------


def _village(total, parcels):
    return f.records(
        mouza=f.mouza(area_stated=f.stated(total)),
        khesras=tuple(
            f.khesra(f"K{n}", str(200 + n), area_stated=f.stated(u))
            for n, u in enumerate(parcels, start=1)
        ),
    )


def test_leaves_sum_to_mouza_fires_on_a_broken_trial_balance():
    found = f.run(conservation.leaves_sum_to_mouza, _village(100, [40, 61]))
    assert len(found) == 1
    assert found[0].evidence["difference"] == "1 decimal"
    assert found[0].primary_subject.entity_id == "MZ"


def test_leaves_sum_to_mouza_passes_and_counts_only_leaves():
    """A sub-divided parent must not be counted alongside its children."""
    records = f.records(
        mouza=f.mouza(area_stated=f.stated(100)),
        khesras=(
            f.khesra("P", "217", area_stated=f.stated(100)),
            f.khesra("C1", "1", parent_khesra_id="P", area_stated=f.stated(40)),
            f.khesra("C2", "2", parent_khesra_id="P", area_stated=f.stated(60)),
        ),
    )
    assert f.run(conservation.leaves_sum_to_mouza, records) == []


def test_leaves_sum_to_mouza_abstains_without_a_stated_total():
    found = f.run(conservation.leaves_sum_to_mouza, _village(100, [40, 60])._replace_mouza()
                  if False else f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(40)),)))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "mouza.area_stated"
