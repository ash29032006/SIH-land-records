"""The one ACROSS_VERSION rule in Phase 1. Three fixtures, like every other rule."""

from __future__ import annotations

from fractions import Fraction

import fixtures as f
import pytest

from kavach.findings import (
    Engine,
    FindingClass,
    RuleScope,
    SingleVersionView,
    VersionPairView,
)
from kavach.rules import conservation
from kavach.units import Area
from kavach.synthetic import (
    MouzaSpec,
    synthetic_mouza,
    synthetic_partition_event,
)

REG = f.REG


def _pair(earlier, later):
    return VersionPairView(
        SingleVersionView.of(earlier, REG, earlier.as_of),
        SingleVersionView.of(later, REG, later.as_of),
        REG,
    )


def _run_pair(earlier, later):
    return list(conservation.area_conserved_across_versions(_pair(earlier, later)))


def test_area_conserved_across_versions_fires_when_ground_appears():
    before, after = synthetic_partition_event(
        synthetic_mouza(MouzaSpec(seed=11)), REG, seed=1
    )
    victim = after.index(after.as_of).leaves()[0]
    one_more = Area(
        victim.area_stated.area.ladder_id, victim.area_stated.area.count + 1
    )
    inflated = victim.area_stated.model_copy(update={"area": one_more})
    broken = after.model_copy(
        update={
            "khesras": tuple(
                k.model_copy(update={"area_stated": inflated}) if k.id == victim.id else k
                for k in after.khesras
            )
        }
    )
    found = _run_pair(before, broken)
    errors = [x for x in found if x.finding_class is FindingClass.CERTAIN_ERROR]
    assert errors
    assert errors[0].evidence["difference"] == "1 decimal"


def test_area_conserved_across_versions_passes_a_legitimate_sub_division():
    """Splitting a parcel is normal. The total does not move, so nothing fires."""
    before, after = synthetic_partition_event(
        synthetic_mouza(MouzaSpec(seed=11)), REG, seed=1
    )
    assert _run_pair(before, after) == []


def test_area_conserved_across_versions_abstains_when_a_parcel_states_no_area():
    before, after = synthetic_partition_event(
        synthetic_mouza(MouzaSpec(seed=11)), REG, seed=1
    )
    victim = after.index(after.as_of).leaves()[0]
    blanked = after.model_copy(
        update={
            "khesras": tuple(
                k.model_copy(update={"area_stated": None, "area_restatements": ()})
                if k.id == victim.id else k
                for k in after.khesras
            )
        }
    )
    found = _run_pair(before, blanked)
    assert [x.finding_class for x in found] == [FindingClass.UNVERIFIABLE]
    assert found[0].missing_witness == "khesra.area_stated"


def test_the_rule_declares_across_version_scope():
    assert conservation.area_conserved_across_versions.scope is RuleScope.ACROSS_VERSION


def test_the_engine_routes_it_only_when_a_pair_is_supplied():
    """A single-version run must abstain rather than silently skipping it."""
    engine = Engine((conservation.area_conserved_across_versions,))
    records = synthetic_mouza(MouzaSpec(seed=11))
    single = engine.run(records, REG, as_of=records.as_of)
    assert single.rules_run == ()
    assert len(single.abstentions) == 1

    before, after = synthetic_partition_event(records, REG, seed=1)
    paired = engine.run_pair(
        before, after, REG, earlier_as_of=before.as_of, later_as_of=after.as_of
    )
    assert paired.rules_run == ("C2.area_conserved_across_versions",)
    assert paired.certain_errors == ()
