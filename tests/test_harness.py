"""Tests for the schema, the finding contract, the generator and the mutation engine.

This is build-order step 2 (AGENTS.md 5). The headline assertion of the whole project
lives here: `test_engine_finds_nothing_wrong_with_a_clean_mouza`. A finding on clean
input is a false positive, and the pitch commits publicly to the cost of those.

`_LeafSumRule` below is a **test double**, not a shipped rule. It is a real Class 2
conservation check written here so the contract — pure rule, typed finding, localised
subject, abstain when the witness is missing — is exercised end to end before any rule
module exists.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

import pytest
from helpers import assert_exact, walk_for_floats
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from kavach.classifications import ClassificationError, default_schemes, load_schemes
from kavach.findings import (
    Engine,
    EngineResult,
    Finding,
    FindingClass,
    OnRuleError,
    RuleScope,
    SingleVersionView,
    Subject,
)
from kavach.mutations import (
    MUTATIONS,
    ExpectedFinding,
    MutationCase,
    all_mutation_cases,
    apply_mutation,
    score_case,
    summarise,
)
from kavach.records import (
    AreaStatement,
    EntityType,
    Holding,
    Khata,
    Khesra,
    LeafStatus,
    Membership,
    Mouza,
    Owner,
    Provenance,
    RecordSet,
    SetKind,
    TenureTotal,
    ValidityStatus,
    validity_status,
)
from kavach.synthetic import (
    DocumentProfile,
    MouzaSpec,
    is_synthetic,
    synthetic_mouza,
    verify_synthetic_invariants,
)
from kavach.units import Area, default_registry

REG = default_registry()
SCHEMES = default_schemes()
LADDER = "bihar.jamabandi"
TODAY = dt.date(2026, 1, 1)
YESTERYEAR = dt.date(1900, 1, 1)


def _statement(units: int, ladder_id: str = LADDER) -> AreaStatement:
    return AreaStatement(
        area=Area(ladder_id, Fraction(units)),
        provenance=Provenance(document_id="TEST-DOC", page=1),
    )


# ==========================================================================
# schema: exact scalars
# ==========================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (Fraction(1, 3), Fraction(1, 3)),
        (1, Fraction(1)),
        ("1/3", Fraction(1, 3)),
        ([1, 3], Fraction(1, 3)),
        ((2, 6), Fraction(1, 3)),
        ("0.25", Fraction(1, 4)),
    ],
)
def test_shares_accept_every_exact_representation(value, expected):
    membership = Membership(id="M", khata_id="K", owner_id="O", share=value)
    assert membership.share == expected


@pytest.mark.parametrize("value", [0.5, 1.0, [1, 0], "not a number", {"n": 1}, True])
def test_shares_reject_inexact_or_nonsense(value):
    with pytest.raises(ValidationError):
        Membership(id="M", khata_id="K", owner_id="O", share=value)


def test_areas_must_name_their_ladder():
    statement = AreaStatement.model_validate(
        {"area": {"ladder_id": LADDER, "count": "543"}}
    )
    assert statement.area == Area(LADDER, Fraction(543))
    with pytest.raises(ValidationError):
        AreaStatement.model_validate({"area": {"count": "543"}})
    with pytest.raises(ValidationError):
        AreaStatement.model_validate({"area": 543})


def test_a_mouza_total_without_provenance_is_refused():
    """SCHEMA.md 4: an unsourced total cannot anchor a trial balance."""
    with pytest.raises(ValidationError, match="provenance"):
        Mouza(
            id="MZ",
            name="X",
            district="D",
            ladder_id=LADDER,
            area_stated=AreaStatement(area=Area(LADDER, Fraction(100))),
        )


def test_records_are_frozen_and_reject_unknown_fields():
    khesra = Khesra(id="K", mouza_id="MZ", local_number="217")
    with pytest.raises(ValidationError):
        khesra.local_number = "218"
    with pytest.raises(ValidationError):
        Khesra(id="K", mouza_id="MZ", local_number="217", surprise=1)


def test_validity_interval_must_be_ordered():
    with pytest.raises(ValidationError):
        Khesra(
            id="K",
            mouza_id="MZ",
            local_number="1",
            valid_from=TODAY,
            valid_to=YESTERYEAR,
        )


# ==========================================================================
# schema: the time axis (Ruling 2)
# ==========================================================================


@pytest.mark.parametrize(
    "valid_from, valid_to, kind, snapshot, as_of, expected",
    [
        (None, None, SetKind.SNAPSHOT, TODAY, TODAY, ValidityStatus.VALID),
        (None, None, SetKind.SNAPSHOT, TODAY, YESTERYEAR, ValidityStatus.UNKNOWN),
        (None, None, SetKind.MULTI_VERSION, None, TODAY, ValidityStatus.UNKNOWN),
        (YESTERYEAR, None, SetKind.MULTI_VERSION, None, TODAY, ValidityStatus.VALID),
        (TODAY, None, SetKind.MULTI_VERSION, None, YESTERYEAR, ValidityStatus.NOT_YET_VALID),
        (YESTERYEAR, TODAY, SetKind.MULTI_VERSION, None, TODAY, ValidityStatus.SUPERSEDED),
        (None, TODAY, SetKind.MULTI_VERSION, None, TODAY, ValidityStatus.SUPERSEDED),
        (None, TODAY, SetKind.MULTI_VERSION, None, YESTERYEAR, ValidityStatus.UNKNOWN),
        (None, None, SetKind.MULTI_VERSION, None, None, ValidityStatus.VALID),
    ],
)
def test_validity_truth_table(valid_from, valid_to, kind, snapshot, as_of, expected):
    record = Khesra(
        id="K", mouza_id="MZ", local_number="1", valid_from=valid_from, valid_to=valid_to
    )
    assert (
        validity_status(record, as_of, set_kind=kind, snapshot_as_of=snapshot)
        is expected
    )


def test_a_snapshot_must_declare_its_date():
    mouza = Mouza(id="MZ", name="X", district="D", ladder_id=LADDER)
    with pytest.raises(ValidationError, match="as_of"):
        RecordSet(mouza=mouza, kind=SetKind.SNAPSHOT, source="test")


def test_undated_rows_in_a_multi_version_set_are_unknown_not_current():
    """The failure Ruling 2 exists to prevent: superseded rows read as duplicates."""
    mouza = Mouza(id="MZ", name="X", district="D", ladder_id=LADDER)
    records = RecordSet(
        mouza=mouza,
        kind=SetKind.MULTI_VERSION,
        source="test",
        khatas=(
            Khata(id="KT1", mouza_id="MZ", number="1", valid_from=YESTERYEAR),
            Khata(id="KT2", mouza_id="MZ", number="1"),
        ),
    )
    index = records.index(TODAY)
    assert [k.id for k in index.khatas] == ["KT1"]
    assert [k.id for k in index.unknown_khatas] == ["KT2"]
    assert index.has_undated_records()


# ==========================================================================
# schema: derived structure
# ==========================================================================


def _tree(*khesras) -> RecordSet:
    return RecordSet(
        mouza=Mouza(id="MZ", name="X", district="D", ladder_id=LADDER),
        kind=SetKind.SNAPSHOT,
        as_of=TODAY,
        source="test",
        khesras=khesras,
    )


def test_leaf_status_is_derived_not_stored():
    records = _tree(
        Khesra(id="A", mouza_id="MZ", local_number="217"),
        Khesra(id="B", mouza_id="MZ", parent_khesra_id="A", local_number="1"),
        Khesra(id="C", mouza_id="MZ", parent_khesra_id="B", local_number="2"),
    )
    index = records.index(TODAY)
    assert index.leaf_status("A") is LeafStatus.INTERNAL
    assert index.leaf_status("B") is LeafStatus.INTERNAL
    assert index.leaf_status("C") is LeafStatus.LEAF
    assert index.display_path("C") == "217/1/2"
    assert index.depth_of("C") == 3
    assert [k.id for k in index.leaves()] == ["C"]


def test_a_parent_with_only_undated_children_has_unknown_leaf_status():
    """Not knowing whether a parcel was sub-divided is different from knowing it wasn't."""
    records = RecordSet(
        mouza=Mouza(id="MZ", name="X", district="D", ladder_id=LADDER),
        kind=SetKind.MULTI_VERSION,
        source="test",
        khesras=(
            Khesra(id="A", mouza_id="MZ", local_number="217", valid_from=YESTERYEAR),
            Khesra(id="B", mouza_id="MZ", parent_khesra_id="A", local_number="1"),
        ),
    )
    index = records.index(TODAY)
    assert index.leaf_status("A") is LeafStatus.UNKNOWN
    assert index.undetermined_leaves()
    assert index.leaves() == ()


def test_cyclic_parentage_is_reported_not_raised():
    records = _tree(
        Khesra(id="A", mouza_id="MZ", parent_khesra_id="B", local_number="1"),
        Khesra(id="B", mouza_id="MZ", parent_khesra_id="A", local_number="2"),
    )
    index = records.index(TODAY)
    assert index.cyclic_khesra_ids == frozenset({"A", "B"})
    assert index.path_of("A") is None


def test_a_khesra_cannot_be_its_own_parent():
    with pytest.raises(ValidationError):
        Khesra(id="A", mouza_id="MZ", parent_khesra_id="A", local_number="1")


def test_deep_subdivision_needs_no_new_level():
    """217/1/2/3/4 — recursion, not a fixed fourth level."""
    chain = [Khesra(id="K0", mouza_id="MZ", local_number="217")]
    for depth in range(1, 6):
        chain.append(
            Khesra(
                id=f"K{depth}",
                mouza_id="MZ",
                parent_khesra_id=f"K{depth - 1}",
                local_number=str(depth),
            )
        )
    index = _tree(*chain).index(TODAY)
    assert index.display_path("K5") == "217/1/2/3/4/5"


# ==========================================================================
# findings: the contract
# ==========================================================================


def _finding(**overrides) -> Finding:
    base = dict(
        rule_id="test.rule",
        validation_class=2,
        finding_class=FindingClass.CERTAIN_ERROR,
        subjects=(Subject(EntityType.KHESRA, "K1", display="217/1"),),
        message="areas do not reconcile",
    )
    base.update(overrides)
    return Finding(**base)


def test_an_abstention_must_name_the_witness_it_lacked():
    """Abstaining without saying why is indistinguishable from passing."""
    with pytest.raises(ValueError, match="witness"):
        _finding(finding_class=FindingClass.UNVERIFIABLE)
    ok = _finding(
        finding_class=FindingClass.UNVERIFIABLE, missing_witness="stated mouza total"
    )
    assert ok.is_abstention


def test_a_finding_must_localise():
    with pytest.raises(ValueError, match="localise"):
        _finding(subjects=())


@pytest.mark.parametrize("bad", [0, 9, -1])
def test_validation_class_is_one_to_eight(bad):
    with pytest.raises(ValueError):
        _finding(validation_class=bad)


def test_evidence_values_are_strings_rendered_by_the_rule_that_knows_the_units():
    with pytest.raises(TypeError):
        _finding(evidence={"stated": 543})
    assert _finding(evidence={"stated": "5 acre 43 decimal"}).evidence["stated"]


def test_findings_are_immutable():
    finding = _finding()
    with pytest.raises(Exception):
        finding.rule_id = "other"
    with pytest.raises(TypeError):
        finding.evidence["x"] = "y"


# ==========================================================================
# findings: the engine
# ==========================================================================


@dataclass(frozen=True)
class _FakeRule:
    id: str
    validation_class: int
    scope: RuleScope
    emit: Callable

    def __call__(self, view):
        return self.emit(view)


def _silent(rule_id="quiet", scope=RuleScope.WITHIN_VERSION):
    return _FakeRule(rule_id, 1, scope, lambda view: [])


def test_engine_refuses_duplicate_rule_ids():
    with pytest.raises(ValueError, match="duplicate"):
        Engine((_silent("same"), _silent("same")))


def test_engine_refuses_a_rule_with_no_declared_scope():
    bogus = _FakeRule("bogus", 1, "within_version", lambda view: [])
    with pytest.raises(ValueError, match="RuleScope"):
        Engine((bogus,))


def test_a_rule_whose_view_was_not_supplied_abstains_rather_than_passing():
    engine = Engine((_silent("needs_pair", scope=RuleScope.ACROSS_VERSION),))
    result = engine.run(synthetic_mouza(MouzaSpec(seed=1)), REG, as_of=TODAY)
    assert result.rules_run == ()
    assert len(result.abstentions) == 1
    assert result.abstentions[0].missing_witness == RuleScope.ACROSS_VERSION


def test_a_rule_that_crashes_has_not_passed():
    def explode(view):
        raise RuntimeError("boom")

    exploding = _FakeRule("explodes", 1, RuleScope.WITHIN_VERSION, explode)
    records = synthetic_mouza(MouzaSpec(seed=1))

    with pytest.raises(RuntimeError):
        Engine((exploding,)).run(records, REG, as_of=TODAY)

    lenient = Engine((exploding,), on_error=OnRuleError.ABSTAIN)
    result = lenient.run(records, REG, as_of=TODAY)
    assert result.certain_errors == ()
    assert len(result.abstentions) == 1
    assert "RuntimeError" in result.abstentions[0].message


def test_engine_result_counts_by_class():
    findings = (
        _finding(),
        _finding(finding_class=FindingClass.CONFLICT),
        _finding(finding_class=FindingClass.UNVERIFIABLE, missing_witness="w"),
    )
    result = EngineResult(findings, ("r",), TODAY)
    assert len(result) == 3
    assert result.counts()["certain_error"] == 1
    assert result.by_validation_class()[2] == 3


# ==========================================================================
# the test double: a real Class 2 conservation rule
# ==========================================================================


def _leaf_sum_rule(view: SingleVersionView):
    """Do the leaf parcels sum to the stated mouza total?

    Written here rather than shipped: it proves the rule contract works before any
    rule module exists. Note it abstains rather than passing when the total is
    missing — which is exactly what the jamabandi profile produces.
    """
    mouza = view.records.mouza
    subject = Subject(EntityType.MOUZA, mouza.id, display=mouza.name)
    if mouza.area_stated is None:
        return [
            Finding(
                rule_id="test.leaf_sum",
                validation_class=2,
                finding_class=FindingClass.UNVERIFIABLE,
                subjects=(subject,),
                message="no stated mouza total, so the trial balance cannot run",
                missing_witness="mouza.area_stated",
                as_of=view.as_of,
            )
        ]
    stated = mouza.area_stated.area
    total = Area.zero(stated.ladder_id)
    for leaf in view.index.leaves():
        if leaf.area_stated is None:
            return [
                Finding(
                    rule_id="test.leaf_sum",
                    validation_class=2,
                    finding_class=FindingClass.UNVERIFIABLE,
                    subjects=(Subject(EntityType.KHESRA, leaf.id),),
                    message="a parcel states no area",
                    missing_witness="khesra.area_stated",
                    as_of=view.as_of,
                )
            ]
        total = total + leaf.area_stated.area
    if total == stated:
        return []
    from kavach.units import format_area

    return [
        Finding(
            rule_id="test.leaf_sum",
            validation_class=2,
            finding_class=FindingClass.CERTAIN_ERROR,
            subjects=(subject,),
            message="parcels do not sum to the stated mouza total",
            evidence={
                "parcels_sum_to": format_area(total, view.registry),
                "mouza_states": format_area(stated, view.registry),
                "difference": format_area(total - stated, view.registry),
            },
            as_of=view.as_of,
        )
    ]


LEAF_SUM = _FakeRule("test.leaf_sum", 2, RuleScope.WITHIN_VERSION, _leaf_sum_rule)


# ==========================================================================
# the generator
# ==========================================================================


@pytest.mark.parametrize("profile", list(DocumentProfile))
@pytest.mark.parametrize("seed", [1, 2, 3, 17, 99])
def test_generated_mouzas_hold_every_invariant_by_construction(seed, profile):
    records = synthetic_mouza(MouzaSpec(seed=seed, profile=profile))
    assert verify_synthetic_invariants(records, REG) == ()


@settings(max_examples=40)
@given(
    st.integers(min_value=1, max_value=10_000),
    st.sampled_from(list(DocumentProfile)),
    st.integers(min_value=2, max_value=20),
    st.integers(min_value=0, max_value=100),
)
def test_generator_holds_invariants_across_the_parameter_space(
    seed, profile, root_khesras, subdivide_percent
):
    records = synthetic_mouza(
        MouzaSpec(
            seed=seed,
            profile=profile,
            root_khesras=root_khesras,
            subdivide_percent=subdivide_percent,
            total_area=5_000,
        )
    )
    assert verify_synthetic_invariants(records, REG) == ()


def test_generation_is_deterministic():
    assert synthetic_mouza(MouzaSpec(seed=42)) == synthetic_mouza(MouzaSpec(seed=42))
    assert synthetic_mouza(MouzaSpec(seed=42)) != synthetic_mouza(MouzaSpec(seed=43))


def test_everything_generated_is_labelled_synthetic():
    records = synthetic_mouza(MouzaSpec(seed=5))
    assert is_synthetic(records)
    assert records.source.startswith("synthetic:")
    assert all(owner.name_raw.startswith("SYNTH-") for owner in records.owners)
    assert records.mouza.name.startswith("SYNTH-")


def test_profiles_differ_in_which_witnesses_exist():
    """EVIDENCE.md E2, E3, E6 — this is what Class 8 will be counting."""
    khatian = synthetic_mouza(MouzaSpec(seed=8, profile=DocumentProfile.KHATIAN))
    jamabandi = synthetic_mouza(MouzaSpec(seed=8, profile=DocumentProfile.JAMABANDI))
    combined = synthetic_mouza(MouzaSpec(seed=8, profile=DocumentProfile.COMBINED))

    assert all(h.share is not None for h in khatian.holdings)
    assert all(h.area_claimed is None for h in khatian.holdings)

    assert all(h.share is None for h in jamabandi.holdings)
    assert all(h.area_claimed is not None for h in jamabandi.holdings)
    assert all(k.tenure is None for k in jamabandi.khesras)
    assert jamabandi.mouza.area_stated is None
    assert jamabandi.mouza.tenure_totals == ()

    assert all(h.share is not None for h in combined.holdings)
    assert all(h.area_claimed is not None for h in combined.holdings)
    assert combined.mouza.tenure_totals


def test_nothing_generated_contains_an_inexact_number():
    for profile in DocumentProfile:
        records = synthetic_mouza(MouzaSpec(seed=13, profile=profile))
        assert_exact(records, f"synthetic[{profile}]")


def test_a_generated_mouza_survives_json_round_trip_exactly():
    records = synthetic_mouza(MouzaSpec(seed=21))
    restored = RecordSet.model_validate_json(records.model_dump_json())
    assert restored == records
    assert verify_synthetic_invariants(restored, REG) == ()


def test_the_invariant_checker_actually_catches_corruption():
    """A checker that never fails would make every mutation test meaningless."""
    records = synthetic_mouza(MouzaSpec(seed=4))
    victim = records.khesras[0]
    broken = records.model_copy(
        update={
            "khesras": (victim.model_copy(update={"local_number": "0"}),)
            + records.khesras[1:]
        }
    )
    assert verify_synthetic_invariants(broken, REG)


# ==========================================================================
# THE headline assertion
# ==========================================================================


@pytest.mark.parametrize("seed", [1, 7, 23, 101, 999])
def test_engine_finds_nothing_wrong_with_a_clean_mouza(seed):
    """HANDOFF_BUILD.md 5.1. Any finding here is a false positive."""
    records = synthetic_mouza(MouzaSpec(seed=seed, profile=DocumentProfile.COMBINED))
    result = Engine((LEAF_SUM,)).run(records, REG, as_of=records.as_of)
    assert result.certain_errors == (), [str(f) for f in result.certain_errors]
    assert result.abstentions == ()


def test_a_missing_witness_produces_an_abstention_not_a_pass():
    """The jamabandi profile states no mouza total, so the trial balance cannot run."""
    records = synthetic_mouza(MouzaSpec(seed=7, profile=DocumentProfile.JAMABANDI))
    result = Engine((LEAF_SUM,)).run(records, REG, as_of=records.as_of)
    assert result.certain_errors == ()
    assert len(result.abstentions) == 1
    assert result.abstentions[0].missing_witness == "mouza.area_stated"


def test_the_engine_localises_a_real_corruption_end_to_end():
    clean = synthetic_mouza(MouzaSpec(seed=7))
    case = apply_mutation("one_unit_added_to_parcel", clean, REG, seed=1)
    result = Engine((LEAF_SUM,)).run(case.mutated, REG, as_of=case.mutated.as_of)

    assert len(result.certain_errors) == 1
    finding = result.certain_errors[0]
    assert finding.primary_subject.entity_id == clean.mouza.id
    assert finding.evidence["difference"] == "1 decimal"
    assert score_case(case, result).localised


# ==========================================================================
# the mutation engine
# ==========================================================================


CLEAN = synthetic_mouza(MouzaSpec(seed=11, profile=DocumentProfile.COMBINED))


def test_every_mutation_applies_to_a_combined_mouza():
    names = {case.name for case in all_mutation_cases(CLEAN, REG, seed=3)}
    assert names == set(MUTATIONS), set(MUTATIONS) - names


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_mutation_changes_the_records(name):
    case = apply_mutation(name, CLEAN, REG, seed=3)
    assert case.mutated != case.clean
    assert case.expected


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_mutation_breaks_exactly_what_it_claims_to(name):
    """A corruption that breaks nothing would silently inflate recall later."""
    case = apply_mutation(name, CLEAN, REG, seed=3)
    assert bool(case.broken_invariants) is case.breaks_invariants, case.broken_invariants


def test_removing_a_witness_breaks_no_invariant_and_that_is_the_point():
    """Absence of a witness is not an error. Only a witness census can see it."""
    case = apply_mutation("witness_removed", CLEAN, REG, seed=3)
    assert case.broken_invariants == ()
    assert case.mutated.mouza.area_stated is None
    assert case.expected[0].finding_class is FindingClass.UNVERIFIABLE
    assert case.expected[0].validation_class == 8


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_mutations_are_deterministic(name):
    first = apply_mutation(name, CLEAN, REG, seed=3)
    second = apply_mutation(name, CLEAN, REG, seed=3)
    assert first.mutated == second.mutated
    assert first.expected == second.expected


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_every_mutation_is_grounded_in_a_document(name):
    """No corruption is invented for convenience; each cites where it comes from."""
    mutator = MUTATIONS[name]
    assert "HANDOFF_BUILD.md" in mutator.grounding or "EVIDENCE.md" in mutator.grounding


def test_deleting_a_sequence_member_breaks_two_invariants_not_one():
    """The spec table implies one finding per mutation. Deletions break two."""
    case = apply_mutation("sequence_member_deleted", CLEAN, REG, seed=3)
    assert case.expected_classes == {2, 3}
    case = apply_mutation("sequence_gap_renumbered", CLEAN, REG, seed=3)
    assert case.expected_classes == {3}


def test_mutated_records_still_contain_no_inexact_numbers():
    for case in all_mutation_cases(CLEAN, REG, seed=3):
        assert not walk_for_floats(case.mutated, case.name)


# ==========================================================================
# scoring — precision, recall, localisation
# ==========================================================================


def _result_from(case: MutationCase, entity_id: str | None = None) -> EngineResult:
    """An engine result that reports each expected finding, optionally mislocalised."""
    findings = tuple(
        Finding(
            rule_id="fake",
            validation_class=e.validation_class,
            finding_class=e.finding_class,
            subjects=(Subject(e.entity_type, entity_id or e.entity_id),),
            message=e.note or "found",
            missing_witness=(
                "witness" if e.finding_class is FindingClass.UNVERIFIABLE else None
            ),
        )
        for e in case.expected
    )
    return EngineResult(findings, ("fake",), None)


RAN_AND_FOUND_NOTHING = EngineResult((), ("fake",), None)
NO_RULE_RAN = EngineResult((), (), None)


def test_a_perfect_engine_scores_full_recall_and_localisation():
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    score = summarise(cases, [_result_from(c) for c in cases], RAN_AND_FOUND_NOTHING)
    assert score.recall == 1
    assert score.localisation_rate == 1
    assert score.precision == 1


def test_a_blind_engine_scores_zero_recall():
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    score = summarise(cases, [RAN_AND_FOUND_NOTHING for _ in cases], RAN_AND_FOUND_NOTHING)
    assert score.recall == 0
    assert score.localisation_rate is None
    assert score.precision is None


def test_right_class_wrong_parcel_counts_as_detected_but_not_localised():
    """HANDOFF_BUILD.md 5.2: the right village is not the right parcel."""
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    score = summarise(
        cases, [_result_from(c, entity_id="SOMEWHERE-ELSE") for c in cases],
        RAN_AND_FOUND_NOTHING,
    )
    assert score.recall == 1
    assert score.localised == 0
    assert score.localisation_rate == 0


def test_false_positives_on_clean_input_lower_precision():
    """Clean input is the only record set known to contain no defect, so it is the
    only place a false positive can be observed."""
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    noisy_clean = EngineResult((_finding(), _finding()), ("fake",), None)
    score = summarise(cases, [_result_from(c) for c in cases], noisy_clean)
    assert score.precision is not None and score.precision < 1
    assert score.clean_certain_errors == 2


def test_collateral_findings_are_not_counted_as_false_positives():
    """A duplicated khata really does make several parcels over-claimed. Reporting
    them is correct behaviour, and must not be scored as an error."""
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    elsewhere = [_result_from(c, entity_id="SOMEWHERE-ELSE") for c in cases]
    score = summarise(cases, elsewhere, RAN_AND_FOUND_NOTHING)
    assert score.collateral > 0
    assert score.clean_certain_errors == 0
    assert score.precision == 1


def test_no_rule_having_run_is_not_the_same_as_scoring_zero():
    """The distinction the whole project rests on: absent is not measured-as-empty."""
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    nothing_ran = summarise(cases, [NO_RULE_RAN for _ in cases], NO_RULE_RAN)
    assert nothing_ran.rules_run == 0
    assert nothing_ran.recall is None
    assert nothing_ran.precision is None
    assert "no rule ran" in nothing_ran.report()

    ran_and_missed = summarise(
        cases, [RAN_AND_FOUND_NOTHING for _ in cases], RAN_AND_FOUND_NOTHING
    )
    assert ran_and_missed.rules_run == 1
    assert ran_and_missed.recall == 0


def test_the_score_report_prints_real_numbers():
    cases = all_mutation_cases(CLEAN, REG, seed=3)
    report = summarise(cases, [_result_from(c) for c in cases], RAN_AND_FOUND_NOTHING).report()
    assert "recall" in report and "localisation" in report and "precision" in report
    assert "measured, not asserted" in report


# ==========================================================================
# classification schemes
# ==========================================================================


def test_disputed_classes_are_marked_and_not_citable():
    """EVIDENCE.md E9 — sources disagree, so the data says so."""
    scheme = SCHEMES.get("bihar.khatiyan")
    assert "gairmazrua_malik" in scheme.disputed_codes
    assert not scheme.tenure_class("gairmazrua_malik").is_citable
    assert scheme.tenure_class("raiyati").is_citable


def test_government_land_drives_the_only_permitted_branch():
    scheme = SCHEMES.get("bihar.khatiyan")
    assert scheme.is_government("gairmazrua_aam")
    assert not scheme.is_government("raiyati")


def test_land_use_is_empty_so_land_use_rules_must_abstain():
    assert SCHEMES.get("bihar.khatiyan").land_use == ()
    assert SCHEMES.get("bihar.khatiyan").land_use_note


def test_a_class_without_a_source_is_refused(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        '{"schemes": [{"id": "x", "tenure_classes": [{"code": "a", "label": "A", '
        '"government": false, "transferable": true, "confidence": "sourced", '
        '"source": "  "}]}]}',
        encoding="utf-8",
    )
    with pytest.raises(ClassificationError, match="source"):
        load_schemes(path)
