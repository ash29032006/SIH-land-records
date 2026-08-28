"""Class 8 — the witness census."""

from __future__ import annotations

from fractions import Fraction

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import census
from kavach.rules.census import WITNESS_NAMES, verifiability_rate, witness_census
from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza


def test_the_denominator_follows_structure_never_data_quality():
    """A rate whose denominator moves with the *data* is not a measurement. One that
    moves with a parcel's *shape* is: a root has no parent to reconcile against, and
    penalising it for that understates the rate."""
    thin = witness_census(f.records(khesras=(f.khesra("K1", "217"),)), f.REG, f.TODAY)
    root = thin.parcels[0]
    assert "parent_area" in root.not_applicable
    assert "child_areas" in root.not_applicable
    assert root.total == len(WITNESS_NAMES) - 2

    # Two root parcels of the same shape must share a denominator regardless of how
    # much data either of them carries.
    mixed = witness_census(
        f.records(
            khesras=(
                f.khesra("K1", "217", area_stated=f.stated(50)),
                f.khesra("K2", "218"),
            )
        ),
        f.REG, f.TODAY,
    )
    assert len({p.total for p in mixed.parcels}) == 1


def test_a_child_parcel_is_scored_against_its_parent_but_not_against_sub_plots():
    records = f.records(
        khesras=(
            f.khesra("P", "217", area_stated=f.stated(100)),
            f.khesra("C1", "1", parent_khesra_id="P", area_stated=f.stated(100)),
        )
    )
    result = witness_census(records, f.REG, f.TODAY)
    child = next(p for p in result.parcels if p.khesra_id == "C1")
    assert "parent_area" in child.present
    assert "child_areas" in child.not_applicable


def test_a_bare_parcel_is_unexaminable():
    result = witness_census(f.records(khesras=(f.khesra("K1", "217"),)), f.REG, f.TODAY)
    assert result.parcels[0].is_unexaminable
    assert result.verifiability_rate == 0


def test_the_rate_rises_with_the_witnesses_present():
    combined = verifiability_rate(synthetic_mouza(
        MouzaSpec(seed=3, profile=DocumentProfile.COMBINED)), f.REG)
    jamabandi = verifiability_rate(synthetic_mouza(
        MouzaSpec(seed=3, profile=DocumentProfile.JAMABANDI)), f.REG)
    assert combined > jamabandi > 0
    assert isinstance(combined, Fraction)


def test_the_census_runs_when_every_other_class_would_abstain():
    """AGENTS.md 3.5 — this is the property that makes it the distinctive output."""
    records = f.records(khesras=(f.khesra("K1", "217"), f.khesra("K2", "218")))
    result = witness_census(records, f.REG, f.TODAY)
    assert result.verifiability_rate is not None
    assert len(result.unexaminable) == 2


def test_the_rate_is_none_when_there_are_no_parcels():
    assert verifiability_rate(f.records(), f.REG, f.TODAY) is None


def test_per_witness_availability_explains_the_rate():
    records = synthetic_mouza(MouzaSpec(seed=3, profile=DocumentProfile.JAMABANDI))
    breakdown = witness_census(records, f.REG).by_witness()
    assert breakdown["own_area"] == 1
    assert breakdown["tenure_class"] == 0
    assert breakdown["holding_claimed_area"] == 1
    assert breakdown["holding_share"] == 0


def test_the_report_prints_a_real_rate():
    text = witness_census(synthetic_mouza(MouzaSpec(seed=3)), f.REG).report()
    assert "a rate, not an error rate" in text
    assert "verifiability rate" in text


# ---- C8.witness_census as a rule -------------------------------------------


def test_witness_census_rule_fires_on_a_parcel_with_no_witnesses():
    found = f.run(census.witness_census_rule, f.records(khesras=(f.khesra("K1", "217"),)))
    assert all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)
    assert any(x.primary_subject.entity_id == "K1" for x in found)


def test_witness_census_rule_never_asserts_anything_is_wrong():
    """Class 8 reports coverage. It has no CERTAIN_ERROR path at all."""
    records = synthetic_mouza(MouzaSpec(seed=3))
    found = f.run(census.witness_census_rule, records, as_of=records.as_of)
    assert found and all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)


def test_witness_census_rule_always_reports_the_rate_even_on_a_rich_record_set():
    records = synthetic_mouza(MouzaSpec(seed=3))
    found = f.run(census.witness_census_rule, records, as_of=records.as_of)
    summary = [x for x in found if "verifiability_rate" in x.evidence]
    assert len(summary) == 1
    assert summary[0].evidence["verifiability_rate"] != "None"


def test_witness_census_rule_abstains_by_construction_on_every_input():
    """The third fixture. Class 8 has no non-abstaining path, so its
    witness-missing case and its normal case are the same case."""
    for records in (
        f.records(khesras=(f.khesra("K1", "217"),)),
        synthetic_mouza(MouzaSpec(seed=3, profile=DocumentProfile.JAMABANDI)),
    ):
        found = f.run(census.witness_census_rule, records, as_of=records.as_of)
        assert found and all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)
        assert all(x.missing_witness for x in found)
