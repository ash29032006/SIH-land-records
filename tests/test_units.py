"""Tests for kavach.units.

Two of these are load-bearing for the whole project rather than for this module:

* `test_no_float_in_area_source` parses `units.py` and `ladders.json` and fails
  if an inexact number, a `float` reference, or a `/` operator appears. That is
  AGENTS.md 3.1 turned into something a machine checks. This *test* file uses
  `float` freely, on purpose: it is not on an area path, and it has to name the
  thing it is banning.

* `test_conversion_refuses_between_structurally_identical_bihar_ladders` is the
  reason Area carries a ladder id at all. Two ladders can have identical
  structure and still not be interchangeable.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from fractions import Fraction
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from kavach.units import (
    Area,
    AreaParseError,
    ConversionRefused,
    DEFAULT_LADDERS_PATH,
    LadderDataError,
    LadderMismatch,
    NotIntegral,
    UnknownLadder,
    UnknownUnit,
    convert,
    default_registry,
    exact_ratio,
    format_area,
    load_registry,
    parse_area,
    sum_areas,
)

REG = default_registry()
BIHAR = "bihar.unspecified"
PATNA = "bihar.patna"
MITHILA = "bihar.mithila"
PUNJAB = "punjab.standard"
DECCAN = "deccan.standard"
JAMABANDI = "bihar.jamabandi"
METRIC = "metric.hectare"
ALL_LADDERS = [BIHAR, PATNA, MITHILA, PUNJAB, DECCAN, JAMABANDI, METRIC]
ANCHORED = [PUNJAB, DECCAN, JAMABANDI, METRIC]

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "kavach"
KAVACH_SOURCES = tuple(sorted(PACKAGE_ROOT.glob("*.py")))


# ==========================================================================
# the invariant that protects every other number in the project
# ==========================================================================

BANNED_IMPORTS = {"math", "cmath", "decimal", "statistics", "numpy", "numpy.core"}

# `random` itself is fine — integer draws are exact. These specific methods are not.
BANNED_ATTRIBUTES = {
    "random", "uniform", "gauss", "normalvariate", "lognormvariate", "expovariate",
    "betavariate", "gammavariate", "paretovariate", "weibullvariate",
    "vonmisesvariate", "triangular",
}


def test_every_module_in_the_package_is_scanned():
    """The guard is worthless if a new module can quietly escape it."""
    names = {path.name for path in KAVACH_SOURCES}
    assert "units.py" in names and "records.py" in names
    assert len(KAVACH_SOURCES) >= 5, f"only found {names}"


@pytest.mark.parametrize("source", KAVACH_SOURCES, ids=lambda p: p.name)
def test_no_float_in_area_source(source):
    """No inexact arithmetic may exist anywhere in the package.

    Every module here is on an area or share code path. `/` is banned outright
    rather than argued about case by case: int/int silently yields a float, so
    `Fraction(a, b)` and `//` are used instead and the ban stays checkable.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    problems: list[str] = []

    for node in ast.walk(tree):
        where = f"{source.name}:{getattr(node, 'lineno', '?')}"

        if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRIBUTES:
            problems.append(f"{where}: '.{node.attr}' returns an inexact number")

        if isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
            problems.append(f"{where}: inexact literal {node.value!r}")

        if isinstance(node, ast.Name) and node.id == "float":
            problems.append(f"{where}: reference to 'float'")

        if isinstance(node, ast.Attribute) and node.attr == "float":
            problems.append(f"{where}: attribute access '.float'")

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            problems.append(
                f"{where}: true division '/'. int/int yields a float. "
                "Use Fraction(a, b) or '//'."
            )

        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Div):
            problems.append(f"{where}: augmented true division '/='")

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED_IMPORTS:
                    problems.append(f"{where}: import of {alias.name!r}")

        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BANNED_IMPORTS:
                problems.append(f"{where}: import from {node.module!r}")

    assert not problems, "inexact arithmetic on an area path:\n  " + "\n  ".join(problems)


def test_ladder_data_file_contains_no_inexact_literal():
    def refuse(raw: str):
        pytest.fail(f"{DEFAULT_LADDERS_PATH} contains the inexact literal {raw!r}")

    with DEFAULT_LADDERS_PATH.open(encoding="utf-8") as handle:
        json.load(handle, parse_float=refuse)


def _walk_for_floats(obj, path: str, found: list[str]) -> None:
    if isinstance(obj, float) or isinstance(obj, complex):
        found.append(f"{path} = {obj!r}")
        return
    if isinstance(obj, Fraction):
        if not isinstance(obj.numerator, int) or not isinstance(obj.denominator, int):
            found.append(f"{path} is a Fraction over non-integers")
        return
    if isinstance(obj, (str, bytes, int, bool)) or obj is None:
        return
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for field in dataclasses.fields(obj):
            _walk_for_floats(getattr(obj, field.name), f"{path}.{field.name}", found)
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            _walk_for_floats(value, f"{path}[{key!r}]", found)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for index, value in enumerate(obj):
            _walk_for_floats(value, f"{path}[{index}]", found)
        return
    try:
        items = dict(obj)
    except (TypeError, ValueError):
        return
    for key, value in items.items():
        _walk_for_floats(value, f"{path}[{key!r}]", found)


def test_no_float_in_returned_values():
    """Every public entry point, exercised, must return only exact numbers."""
    ladder = REG.get(BIHAR)
    area = ladder.area(bigha=3, katha=11, dhur=7)
    results = {
        "registry": REG,
        "ladder": ladder,
        "area": area,
        "sum": sum_areas([area, area]),
        "difference": area - area,
        "scaled": area * Fraction(1, 3),
        "split": area.split([Fraction(1, 3), Fraction(2, 3)]),
        "decompose": ladder.decompose(area.count),
        "compose": ladder.compose({"bigha": 1, "katha": 2}),
        "parsed": parse_area("27 katha", BIHAR, REG),
        "formatted": format_area(area, REG),
        "converted": convert(Area(PUNJAB, Fraction(160)), DECCAN, REG),
        "ratio": exact_ratio(PUNJAB, DECCAN, REG),
    }
    found: list[str] = []
    _walk_for_floats(results, "results", found)
    assert not found, "inexact values returned:\n  " + "\n  ".join(found)


def test_area_rejects_inexact_input():
    with pytest.raises(TypeError):
        Area(BIHAR, 1.5)
    with pytest.raises(TypeError):
        Area(BIHAR, 2.0)
    with pytest.raises(TypeError):
        Area(BIHAR, Fraction(1)) * 0.5
    with pytest.raises(TypeError):
        REG.get(BIHAR).area(katha=1.0)


# ==========================================================================
# ladders are data
# ==========================================================================


def test_registry_loads_the_bundled_ladders():
    assert set(REG.ids()) == set(ALL_LADDERS)


@pytest.mark.parametrize(
    "ladder_id, expected",
    [
        (BIHAR, {"bigha": 400, "katha": 20, "dhur": 1}),
        (PUNJAB, {"acre": 160, "kanal": 20, "marla": 1}),
        (DECCAN, {"acre": 40, "guntha": 1}),
    ],
)
def test_ladder_factors_are_exact_integers(ladder_id, expected):
    ladder = REG.get(ladder_id)
    for unit, factor in expected.items():
        assert ladder.factor(unit) == factor
        assert isinstance(ladder.factor(unit), int)


def test_ladder_bases_come_from_the_handoff_document():
    """HANDOFF_BUILD.md 3.5 for the first three; EVIDENCE.md E4/E10 for the rest."""
    assert REG.get(BIHAR).bases == (20, 20)
    assert REG.get(PUNJAB).bases == (8, 20)
    assert REG.get(DECCAN).bases == (40,)
    assert REG.get(JAMABANDI).bases == (100,)
    assert REG.get(METRIC).bases == (100, 100)


def test_every_anchored_ladder_agrees_on_one_acre():
    """Four independently written anchors must describe the same piece of ground.

    This is the arithmetic behind EVIDENCE.md E10: the rakba field states one area
    in three unit systems, so they have to be exactly reconcilable or the check is
    worthless.
    """
    one_acre = {
        PUNJAB: REG.get(PUNJAB).area(acre=1),
        DECCAN: REG.get(DECCAN).area(acre=1),
        JAMABANDI: REG.get(JAMABANDI).area(acre=1),
    }
    in_metric = {
        ladder_id: convert(area, METRIC, REG) for ladder_id, area in one_acre.items()
    }
    assert len(set(in_metric.values())) == 1
    # 1 acre = 4046.8564224 m2 exactly, held as an exact rational
    assert next(iter(in_metric.values())).count == Fraction(40468564224, 10000000)
    # and a hectare written to 4 dp is a whole number of centiare
    assert REG.get(METRIC).area(hectare=0) + Area(METRIC, Fraction(4047)) == parse_area(
        "4047 centiare", METRIC, REG
    ).area


def test_a_decimal_is_one_hundredth_of_an_acre():
    """EVIDENCE.md E4: 1 decimal = 435.6 sq ft = 0.01 acre."""
    ladder = REG.get(JAMABANDI)
    assert ladder.factor("acre") == 100
    assert convert(ladder.area(decimal=100), METRIC, REG) == convert(
        ladder.area(acre=1), METRIC, REG
    )


def test_aliases_resolve_and_unknown_units_raise():
    ladder = REG.get(BIHAR)
    assert ladder.canonical("Kattha") == "katha"
    assert ladder.canonical("  DHOOR ") == "dhur"
    with pytest.raises(UnknownUnit):
        ladder.canonical("marla")


def test_unknown_ladder_raises():
    with pytest.raises(UnknownLadder):
        REG.get("gujarat.standard")


@pytest.mark.parametrize(
    "entry, fragment",
    [
        ({"id": "x", "units": ["a", "b"], "bases": []}, "expected 1 bases"),
        ({"id": "x", "units": ["a", "b"], "bases": [1]}, ">= 2"),
        ({"id": "x", "units": ["a", "a"], "bases": [20]}, "duplicate unit"),
        (
            {"id": "x", "units": ["a", "b"], "bases": [20], "aliases": {"q": "z"}},
            "not a unit",
        ),
        (
            {
                "id": "x",
                "units": ["a", "b"],
                "bases": [20],
                "smallest_unit_in_sqm": [1, 2],
            },
            "anchor_source",
        ),
    ],
)
def test_malformed_ladder_data_is_rejected(tmp_path, entry, fragment):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"ladders": [entry]}), encoding="utf-8")
    with pytest.raises(LadderDataError) as caught:
        load_registry(path)
    assert fragment in str(caught.value)


def test_inexact_literal_in_ladder_data_is_rejected(tmp_path):
    path = tmp_path / "inexact.json"
    path.write_text(
        '{"ladders": [{"id": "x", "units": ["a", "b"], "bases": [20], '
        '"smallest_unit_in_sqm": 25.29}]}',
        encoding="utf-8",
    )
    with pytest.raises(LadderDataError):
        load_registry(path)


def test_an_anchor_without_a_citation_is_rejected(tmp_path):
    """An unsourced conversion factor is a fabricated measurement (AGENTS.md 2)."""
    path = tmp_path / "unsourced.json"
    path.write_text(
        json.dumps(
            {
                "ladders": [
                    {
                        "id": "x",
                        "units": ["a", "b"],
                        "bases": [20],
                        "smallest_unit_in_sqm": [1, 1],
                        "anchor_source": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LadderDataError):
        load_registry(path)


def test_bihar_ladders_are_unanchored_and_say_why():
    for ladder_id in (BIHAR, PATNA, MITHILA):
        ladder = REG.get(ladder_id)
        assert ladder.smallest_unit_in_sqm is None
        assert ladder.anchor_source is None
        assert ladder.notes


# ==========================================================================
# ladder identity is part of the value
# ==========================================================================


def test_same_count_in_different_ladders_is_not_equal():
    """One bigha in Patna and one bigha in Mithila are not the same ground."""
    assert Area(PATNA, Fraction(400)) != Area(MITHILA, Fraction(400))


def test_arithmetic_across_ladders_raises():
    with pytest.raises(LadderMismatch):
        Area(PATNA, Fraction(1)) + Area(MITHILA, Fraction(1))
    with pytest.raises(LadderMismatch):
        Area(PATNA, Fraction(1)) - Area(BIHAR, Fraction(1))
    with pytest.raises(LadderMismatch):
        Area(PATNA, Fraction(1)) < Area(MITHILA, Fraction(1))
    with pytest.raises(LadderMismatch):
        sum_areas([Area(PATNA, Fraction(1)), Area(MITHILA, Fraction(1))])


def test_conversion_refuses_between_structurally_identical_bihar_ladders():
    """Identical structure, unmeasured physical size: refuse, do not guess."""
    patna = REG.get(PATNA)
    mithila = REG.get(MITHILA)
    assert patna.units == mithila.units and patna.bases == mithila.bases

    with pytest.raises(ConversionRefused) as caught:
        convert(Area(PATNA, Fraction(400)), MITHILA, REG)
    message = str(caught.value)
    assert PATNA in message and MITHILA in message
    assert "UNVERIFIABLE" in message


def test_conversion_refuses_when_one_side_is_unanchored():
    with pytest.raises(ConversionRefused):
        convert(Area(BIHAR, Fraction(400)), PUNJAB, REG)
    with pytest.raises(ConversionRefused):
        convert(Area(PUNJAB, Fraction(160)), BIHAR, REG)


def test_conversion_to_the_same_ladder_is_identity():
    area = Area(BIHAR, Fraction(543))
    assert convert(area, BIHAR, REG) is area
    assert exact_ratio(BIHAR, BIHAR, REG) == 1


def test_anchored_conversion_is_an_exact_rational():
    """Both ladders anchor to the defined acre, so 1 guntha == 4 marla exactly."""
    assert exact_ratio(DECCAN, PUNJAB, REG) == Fraction(4)
    assert exact_ratio(PUNJAB, DECCAN, REG) == Fraction(1, 4)

    one_acre_punjab = REG.get(PUNJAB).area(acre=1)
    one_acre_deccan = REG.get(DECCAN).area(acre=1)
    assert convert(one_acre_punjab, DECCAN, REG) == one_acre_deccan
    assert convert(one_acre_deccan, PUNJAB, REG) == one_acre_punjab
    assert format_area(convert(one_acre_deccan, PUNJAB, REG), REG) == "1 acre"


# ==========================================================================
# parse / format at the presentation boundary
# ==========================================================================


def test_parse_normalised_area():
    parsed = parse_area("1 bigha 7 katha 3 dhur", BIHAR, REG)
    assert parsed.area == Area(BIHAR, Fraction(543))
    assert parsed.is_normalised
    assert parsed.over_base == ()


def test_unnormalised_input_keeps_its_value_and_reports_the_artefact():
    """"27 katha" in a base-20 ladder is a Class 1 finding, not something to fix."""
    parsed = parse_area("27 katha", BIHAR, REG)
    assert parsed.area == Area(BIHAR, Fraction(540))
    assert parsed.is_normalised is False
    assert parsed.over_base == ("katha",)
    assert parsed.components == (("katha", Fraction(27)),)
    # the carried form has the same value, and is NOT what was written
    assert format_area(parsed.area, REG) == "1 bigha 7 katha"


def test_fraction_above_the_smallest_unit_is_an_artefact_too():
    parsed = parse_area("3/2 katha", BIHAR, REG)
    assert parsed.area == Area(BIHAR, Fraction(30))
    assert parsed.is_normalised is False
    assert parsed.fractional_above_smallest == ("katha",)


def test_parse_uses_aliases_and_ignores_case():
    assert parse_area("2 Bigah 3 KATTHA", BIHAR, REG).area == Area(BIHAR, Fraction(860))


@pytest.mark.parametrize(
    "text",
    ["", "   ", "bigha", "1 bigha 2 bigha", "1 bigha oops", "1/0 dhur", "1 marla"],
)
def test_bad_area_strings_raise(text):
    with pytest.raises((AreaParseError, UnknownUnit)):
        parse_area(text, BIHAR, REG)


def test_format_zero_and_negative():
    assert format_area(Area(BIHAR, Fraction(0)), REG) == "0 dhur"
    assert format_area(Area(BIHAR, Fraction(-543)), REG) == "-1 bigha 7 katha 3 dhur"
    assert parse_area("-1 bigha 7 katha 3 dhur", BIHAR, REG).area == Area(
        BIHAR, Fraction(-543)
    )


def test_format_omits_zero_components():
    assert format_area(REG.get(BIHAR).area(bigha=2, dhur=5), REG) == "2 bigha 5 dhur"


def test_non_integral_area_survives_display():
    half = Area(BIHAR, Fraction(1, 2))
    assert format_area(half, REG) == "1/2 dhur"
    assert parse_area("1/2 dhur", BIHAR, REG).area == half
    with pytest.raises(NotIntegral):
        half.as_int()


# ==========================================================================
# exactness properties
# ==========================================================================

exact_counts = st.one_of(
    st.integers(min_value=-10**6, max_value=10**6).map(Fraction),
    st.fractions(
        min_value=Fraction(-10**4), max_value=Fraction(10**4), max_denominator=64
    ),
)


@st.composite
def areas(draw, ladder_ids=ALL_LADDERS):
    return Area(draw(st.sampled_from(ladder_ids)), draw(exact_counts))


@st.composite
def share_lists(draw):
    size = draw(st.integers(min_value=1, max_value=6))
    weights = draw(
        st.lists(
            st.integers(min_value=1, max_value=1000), min_size=size, max_size=size
        )
    )
    total = sum(weights)
    return [Fraction(weight, total) for weight in weights]


@given(areas())
def test_roundtrip_internal_display_internal(area):
    """An area rendered for display and read back is unchanged. Exactly."""
    text = format_area(area, REG)
    assert parse_area(text, area.ladder_id, REG).area == area


@given(areas())
def test_roundtrip_display_internal_display(area):
    """Canonical display strings are fixed points of parse-then-format."""
    text = format_area(area, REG)
    assert format_area(parse_area(text, area.ladder_id, REG).area, REG) == text


@given(areas(), share_lists())
def test_partition_by_share_resums_exactly(area, shares):
    """Split a parcel, re-sum, get the original back. No tolerance, no epsilon."""
    parts = area.split(shares)
    assert sum_areas(parts) == area


@given(
    st.sampled_from(ALL_LADDERS),
    st.lists(st.integers(min_value=0, max_value=10**7), min_size=1, max_size=12),
)
def test_integer_partition_resums_exactly(ladder_id, counts):
    parts = [Area(ladder_id, Fraction(count)) for count in counts]
    assert sum_areas(parts, ladder_id=ladder_id) == Area(ladder_id, Fraction(sum(counts)))


@given(st.sampled_from(ALL_LADDERS), exact_counts)
def test_decompose_then_compose_is_identity(ladder_id, count):
    ladder = REG.get(ladder_id)
    parts = ladder.decompose(count)
    assert ladder.compose(dict(zip(ladder.units, parts))) == count


@given(st.sampled_from(ALL_LADDERS), st.integers(min_value=0, max_value=10**9))
def test_decompose_always_produces_a_normalised_form(ladder_id, count):
    """Nothing decompose emits can ever be a unit-carry violation."""
    ladder = REG.get(ladder_id)
    parts = ladder.decompose(Fraction(count))
    for name, quantity in zip(ladder.units, parts):
        assert quantity.denominator == 1
        base = ladder.base_above(name)
        if base is not None:
            assert quantity < base


@given(st.integers(min_value=-10**6, max_value=10**6))
def test_anchored_conversion_roundtrips_exactly(count):
    area = Area(PUNJAB, Fraction(count))
    there = convert(area, DECCAN, REG)
    assert convert(there, PUNJAB, REG) == area


@st.composite
def area_pairs(draw):
    """Two areas in the same ladder, by construction rather than by filtering."""
    ladder_id = draw(st.sampled_from(ALL_LADDERS))
    return (
        Area(ladder_id, draw(exact_counts)),
        Area(ladder_id, draw(exact_counts)),
    )


@given(area_pairs())
def test_addition_is_exact_and_ladder_scoped(pair):
    left, right = pair
    assert (left + right).count == left.count + right.count
    assert (left + right) - right == left
    assert left + right == right + left


@given(share_lists())
def test_shares_must_sum_to_exactly_one(shares):
    assume(len(shares) > 1)
    broken = list(shares)
    broken[0] = broken[0] + Fraction(1, 7)
    with pytest.raises(ValueError):
        Area(BIHAR, Fraction(400)).split(broken)


def test_empty_sum_needs_an_explicit_ladder():
    with pytest.raises(ValueError):
        sum_areas([])
    assert sum_areas([], ladder_id=BIHAR) == Area.zero(BIHAR)
