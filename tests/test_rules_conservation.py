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


# ---- C2.holding_shares_sum_to_one -----------------------------------------


def _undivided(shares):
    return f.records(
        khesras=(f.khesra("K1", "217", area_stated=f.stated(100)),),
        khatas=tuple(f.khata(f"T{n}", str(2000 + n)) for n in range(1, len(shares) + 1)),
        holdings=tuple(
            f.holding(f"H{n}", f"T{n}", "K1", share=s)
            for n, s in enumerate(shares, start=1)
        ),
    )


def test_holding_shares_fires_when_the_parcel_is_over_allocated():
    found = f.run(
        conservation.holding_shares_sum_to_one, _undivided([Fraction(3, 4), Fraction(1, 2)])
    )
    assert len(found) == 1 and found[0].evidence["shares_sum_to"] == "5/4"


def test_holding_shares_passes_an_exact_undivided_split():
    found = f.run(
        conservation.holding_shares_sum_to_one, _undivided([Fraction(3, 4), Fraction(1, 4)])
    )
    assert found == []


def test_holding_shares_abstains_when_no_share_is_recorded():
    found = f.run(conservation.holding_shares_sum_to_one, _undivided([None, None]))
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]


# ---- C2.tenure_totals_reconcile -------------------------------------------


def _classified(tenures, subtotals):
    return f.records(
        mouza=f.mouza(
            classification_scheme="bihar.khatiyan",
            tenure_totals=tuple(
                TenureTotal(code=c, area_stated=f.stated(u)) for c, u in subtotals
            ),
        ),
        khesras=tuple(
            f.khesra(f"K{n}", str(200 + n), area_stated=f.stated(50), tenure=t,
                     classification_scheme="bihar.khatiyan")
            for n, t in enumerate(tenures, start=1)
        ),
    )


def test_tenure_totals_fires_when_a_parcel_is_reclassified():
    found = f.run(
        conservation.tenure_totals_reconcile,
        _classified(["raiyati", "gairmazrua_aam"], [("raiyati", 100)]),
    )
    assert found
    assert any(x.evidence.get("tenure") == "raiyati" for x in found)
    assert all(x.finding_class is FindingClass.CERTAIN_ERROR for x in found)


def test_tenure_totals_passes_when_the_classification_reconciles():
    found = f.run(
        conservation.tenure_totals_reconcile,
        _classified(["raiyati", "gairmazrua_aam"],
                    [("raiyati", 50), ("gairmazrua_aam", 50)]),
    )
    assert found == []


def test_tenure_totals_abstains_on_jamabandi_input_with_no_classification():
    """EVIDENCE.md E6: the digitised jamabandi has no classification column."""
    found = f.run(
        conservation.tenure_totals_reconcile,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(50)),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "mouza.tenure_totals"


# ---- C2.cross_unit_restatement (EVIDENCE.md E10) --------------------------


def _restated(primary_units, hectare_centiare):
    from kavach.records import AreaStatement, Provenance
    from kavach.units import Area

    return f.records(
        khesras=(
            f.khesra(
                "K1", "217",
                area_stated=f.stated(primary_units),
                area_restatements=(
                    AreaStatement(
                        area=Area("metric.hectare", Fraction(hectare_centiare)),
                        provenance=Provenance(document_id="FIX-DOC", cell="rakba/hectare"),
                    ),
                ),
            ),
        )
    )


def test_cross_unit_restatement_fires_when_the_hectare_column_disagrees():
    found = f.run(conservation.cross_unit_restatement, _restated(100, 4047))
    assert len(found) == 1
    assert found[0].finding_class is FindingClass.CERTAIN_ERROR
    assert found[0].evidence["ladder"] == "metric.hectare"


def test_cross_unit_restatement_passes_an_exact_conversion():
    """1 acre = 4046.8564224 m2 exactly, held as a rational rather than rounded."""
    from kavach.units import convert

    exact = convert(f.area(100), "metric.hectare", f.REG)
    found = f.run(conservation.cross_unit_restatement, _restated(100, 0))
    # replace the deliberately-wrong restatement with the exact one
    records = _restated(100, 0)
    khesra = records.khesras[0]
    fixed = khesra.model_copy(
        update={
            "area_restatements": (
                khesra.area_restatements[0].model_copy(update={"area": exact}),
            )
        }
    )
    assert f.run(
        conservation.cross_unit_restatement, records.model_copy(update={"khesras": (fixed,)})
    ) == []


def test_cross_unit_restatement_abstains_when_no_second_unit_is_recorded():
    found = f.run(
        conservation.cross_unit_restatement,
        f.records(khesras=(f.khesra("K1", "217", area_stated=f.stated(100)),)),
    )
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "khesra.area_restatements"


def test_cross_unit_restatement_abstains_when_a_ladder_has_no_anchor():
    """bigha has no measured physical size, so the module refuses to guess a factor."""
    from kavach.records import AreaStatement, Provenance
    from kavach.units import Area

    records = f.records(
        khesras=(
            f.khesra(
                "K1", "217",
                area_stated=f.stated(100),
                area_restatements=(
                    AreaStatement(
                        area=Area("bihar.patna", Fraction(400)),
                        provenance=Provenance(document_id="FIX-DOC"),
                    ),
                ),
            ),
        )
    )
    found = f.run(conservation.cross_unit_restatement, records)
    assert all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)
    assert any("exact rational" in x.missing_witness for x in found)
