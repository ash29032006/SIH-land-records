"""Schema tests: exact scalars, the time axis, and derived structure.

Split out of test_harness.py, which had grown to cover four modules at once.
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


