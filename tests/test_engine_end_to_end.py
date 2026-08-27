"""The whole engine over the whole harness. These are the project's headline numbers.

Nothing here asserts a *target*. Each test asserts a property that must hold — zero
false positives, every corruption localised — and the report prints whatever the
figures actually are. If a rule regresses, these fail rather than the number quietly
drifting.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from kavach.classifications import default_schemes
from kavach.findings import Engine, FindingClass
from kavach.mutations import all_mutation_cases, score_case, summarise
from kavach.rules import ALL_RULES, BLOCKED_RULES, CENSUS_RULES
from kavach.rules.census import verifiability_rate
from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza
from kavach.units import default_registry

REG = default_registry()
SCHEMES = default_schemes()
ENGINE = Engine(ALL_RULES)


def _run(records):
    return ENGINE.run(records, REG, as_of=records.as_of, schemes=SCHEMES)


# ==========================================================================
# the false-positive guard — HANDOFF_BUILD.md 5.1
# ==========================================================================


@pytest.mark.parametrize("profile", list(DocumentProfile))
@pytest.mark.parametrize("seed", [1, 11, 42, 101, 777])
def test_the_whole_engine_finds_nothing_wrong_with_clean_records(seed, profile):
    """Any CERTAIN_ERROR here is a false positive, and false positives cost money."""
    result = _run(synthetic_mouza(MouzaSpec(seed=seed, profile=profile)))
    assert result.certain_errors == (), [str(x) for x in result.certain_errors]


@pytest.mark.parametrize("profile", list(DocumentProfile))
def test_no_rule_ever_reports_a_conflict_or_anomaly_it_cannot_support(profile):
    """Classes 1-3 and 8 deal in certainty and abstention only."""
    result = _run(synthetic_mouza(MouzaSpec(seed=5, profile=profile)))
    assert result.of_class(FindingClass.CONFLICT) == ()
    assert result.of_class(FindingClass.ANOMALY) == ()


def test_missing_witnesses_produce_abstentions_rather_than_silence():
    """The jamabandi profile lacks shares, classification and a mouza total."""
    jamabandi = _run(synthetic_mouza(MouzaSpec(seed=11, profile=DocumentProfile.JAMABANDI)))
    combined = _run(synthetic_mouza(MouzaSpec(seed=11, profile=DocumentProfile.COMBINED)))
    assert len(jamabandi.abstentions) > len(combined.abstentions)
    assert all(x.missing_witness for x in jamabandi.abstentions)


# ==========================================================================
# detection, localisation, precision
# ==========================================================================


CLEAN = synthetic_mouza(MouzaSpec(seed=11, profile=DocumentProfile.COMBINED))
CASES = all_mutation_cases(CLEAN, REG, seed=3)
RESULTS = [_run(case.mutated) for case in CASES]
CLEAN_RESULT = _run(CLEAN)


@pytest.mark.parametrize("index", range(len(CASES)), ids=[c.name for c in CASES])
def test_every_corruption_is_detected_and_localised(index):
    case, result = CASES[index], RESULTS[index]
    score = score_case(case, result)
    assert score.detected, f"{case.name} was not detected at all"
    assert score.localised, f"{case.name} was detected but not localised to the right record"


def test_measured_recall_localisation_and_precision():
    score = summarise(CASES, RESULTS, CLEAN_RESULT)
    assert score.rules_run > 0
    assert score.clean_certain_errors == 0
    assert score.recall == 1
    assert score.localisation_rate == 1
    assert score.precision == 1
    assert score.propagation > 1  # one corruption reaches more than one record


def test_removing_a_witness_raises_no_certain_error():
    """The mutation that must not be an error. Absence is not wrongness."""
    case = next(c for c in CASES if c.name == "witness_removed")
    result = RESULTS[CASES.index(case)]
    assert result.certain_errors == ()
    assert result.abstentions


def test_the_report_prints_unrounded_measured_figures():
    text = summarise(CASES, RESULTS, CLEAN_RESULT).report()
    assert "measured, not asserted" in text
    assert "FALSE POSITIVES, clean 0" in text
    assert "reviewer load, not error" in text


# ==========================================================================
# Class 8 stands alone
# ==========================================================================


def test_the_verifiability_rate_reflects_which_witnesses_exist():
    rates = {
        profile: verifiability_rate(
            synthetic_mouza(MouzaSpec(seed=11, profile=profile)), REG
        )
        for profile in DocumentProfile
    }
    assert rates[DocumentProfile.COMBINED] > rates[DocumentProfile.KHATIAN]
    assert rates[DocumentProfile.KHATIAN] > rates[DocumentProfile.JAMABANDI]
    assert all(isinstance(r, Fraction) for r in rates.values())


def test_the_census_still_returns_a_number_when_everything_else_abstains():
    """AGENTS.md 3.5 — the property that makes it the distinctive output.

    A record set of bare parcels: no areas, no khatas, no owners, no totals.
    Every other class has nothing to work with. The census still reports.
    """
    import datetime as dt

    from kavach.records import Khesra, Mouza, RecordSet, SetKind

    today = dt.date(2026, 1, 1)
    bare = RecordSet(
        mouza=Mouza(id="MZ", name="BARE", district="D", ladder_id="bihar.jamabandi"),
        kind=SetKind.SNAPSHOT,
        as_of=today,
        source="synthetic:bare",
        khesras=tuple(
            Khesra(id=f"K{n}", mouza_id="MZ", local_number=str(200 + n))
            for n in range(1, 4)
        ),
    )
    result = ENGINE.run(bare, REG, as_of=today, schemes=SCHEMES)
    assert result.certain_errors == ()
    assert result.findings and all(x.is_abstention for x in result.findings)

    rate = verifiability_rate(bare, REG, today)
    assert rate is not None and rate == 0


def test_blocked_classes_are_present_and_abstain_in_a_full_run():
    result = _run(CLEAN)
    blocked_ids = {r.id for r in BLOCKED_RULES}
    seen = {x.rule_id for x in result.abstentions}
    assert blocked_ids <= seen
    assert {r.id for r in CENSUS_RULES} <= seen


# ==========================================================================
# the false-positive guard, over the whole parameter space
# ==========================================================================


from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@settings(max_examples=60, deadline=None)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    profile=st.sampled_from(list(DocumentProfile)),
    root_khesras=st.integers(min_value=2, max_value=18),
    subdivide_percent=st.integers(min_value=0, max_value=100),
    max_depth=st.integers(min_value=1, max_value=4),
    max_holders=st.integers(min_value=1, max_value=4),
    max_owners=st.integers(min_value=1, max_value=4),
    ladder_id=st.sampled_from(
        ["bihar.jamabandi", "bihar.patna", "punjab.standard", "west_bengal.standard"]
    ),
)
def test_no_rule_ever_fires_on_a_record_set_that_is_correct_by_construction(
    seed, profile, root_khesras, subdivide_percent, max_depth, max_holders,
    max_owners, ladder_id,
):
    """The strongest form of the false-positive guard.

    Sixty random shapes of mouza — different sizes, depths, holder counts, document
    profiles and unit ladders, including a base-16 one. Every one holds its
    invariants by construction, so every CERTAIN_ERROR is a false positive.
    """
    records = synthetic_mouza(
        MouzaSpec(
            seed=seed,
            profile=profile,
            ladder_id=ladder_id,
            root_khesras=root_khesras,
            subdivide_percent=subdivide_percent,
            max_depth=max_depth,
            max_children=4,
            max_holders_per_parcel=max_holders,
            max_owners_per_khata=max_owners,
            total_area=8_000,
        )
    )
    result = _run(records)
    assert result.certain_errors == (), [str(x) for x in result.certain_errors]


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    ladder_id=st.sampled_from(
        ["bihar.jamabandi", "bihar.mithila", "punjab.standard", "deccan.standard"]
    ),
)
def test_the_verifiability_rate_is_always_an_exact_fraction_between_zero_and_one(
    seed, ladder_id
):
    records = synthetic_mouza(MouzaSpec(seed=seed, ladder_id=ladder_id, total_area=6_000))
    rate = verifiability_rate(records, REG)
    assert isinstance(rate, Fraction)
    assert 0 <= rate <= 1
