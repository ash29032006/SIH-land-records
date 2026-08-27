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
    records = f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(40)),))
    found = f.run(conservation.leaves_sum_to_mouza, records)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "mouza.area_stated"


# ---- C2.holdings_sum_to_parcel --------------------------------------------


def _shared_parcel(parcel_units, claims):
    return f.records(
        khesras=(f.khesra("K1", "217", area_stated=f.stated(parcel_units)),),
        khatas=tuple(f.khata(f"T{n}", str(2000 + n)) for n in range(1, len(claims) + 1)),
        holdings=tuple(
            f.holding(f"H{n}", f"T{n}", "K1", area_claimed=None if u is None else f.stated(u))
            for n, u in enumerate(claims, start=1)
        ),
    )


def test_holdings_sum_to_parcel_fires_when_claims_overrun_the_parcel():
    found = f.run(conservation.holdings_sum_to_parcel, _shared_parcel(100, [60, 41]))
    assert len(found) == 1
    assert found[0].evidence["difference"] == "1 decimal"
    assert found[0].primary_subject.entity_id == "K1"


def test_holdings_sum_to_parcel_passes_a_textual_partition_that_adds_up():
    assert f.run(conservation.holdings_sum_to_parcel, _shared_parcel(100, [60, 40])) == []


def test_holdings_sum_to_parcel_abstains_when_a_holding_claims_no_area():
    found = f.run(conservation.holdings_sum_to_parcel, _shared_parcel(100, [60, None]))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "holding.area_claimed"


# ---- C2.holdings_sum_to_khata ---------------------------------------------


def _khata_with(total, claims):
    return f.records(
        khesras=tuple(f.khesra(f"K{n}", str(200 + n), area_stated=f.stated(999))
                      for n in range(1, len(claims) + 1)),
        khatas=(f.khata("T1", "2001", area_stated=None if total is None else f.stated(total)),),
        holdings=tuple(
            f.holding(f"H{n}", "T1", f"K{n}", area_claimed=f.stated(u))
            for n, u in enumerate(claims, start=1)
        ),
    )


def test_holdings_sum_to_khata_fires_on_a_mismatch():
    found = f.run(conservation.holdings_sum_to_khata, _khata_with(100, [60, 41]))
    assert len(found) == 1 and found[0].evidence["difference"] == "1 decimal"


def test_holdings_sum_to_khata_passes_when_they_add_up():
    assert f.run(conservation.holdings_sum_to_khata, _khata_with(100, [60, 40])) == []


def test_holdings_sum_to_khata_abstains_without_a_stated_khata_total():
    found = f.run(conservation.holdings_sum_to_khata, _khata_with(None, [60, 40]))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "khata.area_stated"


# ---- C2.khata_totals_sum_to_mouza -----------------------------------------


def _ledger(mouza_total, khata_totals):
    return f.records(
        mouza=f.mouza(area_stated=None if mouza_total is None else f.stated(mouza_total)),
        khatas=tuple(
            f.khata(f"T{n}", str(2000 + n), area_stated=f.stated(u))
            for n, u in enumerate(khata_totals, start=1)
        ),
    )


def test_khata_totals_sum_to_mouza_fires_on_a_duplicated_khata():
    found = f.run(conservation.khata_totals_sum_to_mouza, _ledger(100, [60, 40, 40]))
    assert len(found) == 1
    assert found[0].evidence["difference"] == "40 decimal"


def test_khata_totals_sum_to_mouza_passes_a_balanced_ledger():
    assert f.run(conservation.khata_totals_sum_to_mouza, _ledger(100, [60, 40])) == []


def test_khata_totals_sum_to_mouza_abstains_without_a_mouza_total():
    found = f.run(conservation.khata_totals_sum_to_mouza, _ledger(None, [60, 40]))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C2.co_owner_shares_sum_to_one ----------------------------------------


def _co_owned(shares):
    return f.records(
        khatas=(f.khata("T1", "2001"),),
        owners=tuple(f.owner(f"O{n}") for n in range(1, len(shares) + 1)),
        memberships=tuple(
            f.membership(f"M{n}", "T1", f"O{n}", share=s)
            for n, s in enumerate(shares, start=1)
        ),
    )


def test_co_owner_shares_fires_when_they_do_not_sum_to_one():
    found = f.run(
        conservation.co_owner_shares_sum_to_one,
        _co_owned([Fraction(1, 3), Fraction(1, 3)]),
    )
    assert len(found) == 1 and found[0].evidence["shares_sum_to"] == "2/3"


def test_co_owner_shares_passes_thirds_that_are_exact():
    found = f.run(
        conservation.co_owner_shares_sum_to_one,
        _co_owned([Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]),
    )
    assert found == []


def test_co_owner_shares_abstains_because_bihar_records_no_shares():
    """EVIDENCE.md E2 — this is the real-input case, not an edge case."""
    found = f.run(conservation.co_owner_shares_sum_to_one, _co_owned([None, None]))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "membership.share"
