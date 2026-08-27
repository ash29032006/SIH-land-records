"""Class 8 — the witness census."""

from __future__ import annotations

from fractions import Fraction

import fixtures as f
import pytest

from kavach.findings import FindingClass
from kavach.rules import census
from kavach.rules.census import WITNESS_NAMES, verifiability_rate, witness_census
from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza


def test_the_denominator_is_fixed_not_data_dependent():
    """A rate whose denominator moves with the data is not a measurement."""
    thin = witness_census(f.records(khesras=(f.khesra("K1", "217"),)), f.REG, f.TODAY)
    rich = witness_census(synthetic_mouza(MouzaSpec(seed=3)), f.REG)
    assert thin.parcels[0].total == len(WITNESS_NAMES)
    assert all(p.total == len(WITNESS_NAMES) for p in rich.parcels)


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


def test_census_rule_fires_on_a_parcel_with_no_witnesses():
    found = f.run(census.witness_census_rule, f.records(khesras=(f.khesra("K1", "217"),)))
    assert all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)
    assert any(x.primary_subject.entity_id == "K1" for x in found)


def test_census_rule_never_asserts_anything_is_wrong():
    """Class 8 reports coverage. It has no CERTAIN_ERROR path at all."""
    records = synthetic_mouza(MouzaSpec(seed=3))
    found = f.run(census.witness_census_rule, records, as_of=records.as_of)
    assert found and all(x.finding_class is FindingClass.UNVERIFIABLE for x in found)


def test_census_rule_always_reports_the_rate_even_on_a_rich_record_set():
    records = synthetic_mouza(MouzaSpec(seed=3))
    found = f.run(census.witness_census_rule, records, as_of=records.as_of)
    summary = [x for x in found if "verifiability_rate" in x.evidence]
    assert len(summary) == 1
    assert summary[0].evidence["verifiability_rate"] != "None"
