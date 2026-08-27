"""Exact area arithmetic for Kavach.

Invariants this module exists to hold (AGENTS.md 3.1, HANDOFF_BUILD.md 3.5):

1. **No inexact binary numbers, anywhere.** Not in the source, not in the ladder
   data, not in anything this module returns. `tests/test_units.py` parses this
   file's AST and fails the build if one appears. That is also why `/` never
   appears below: `Fraction(a, b)` and `//` are used instead, so the ban can be
   checked statically rather than argued about.

2. **An Area is an exact count of one ladder's smallest unit**, held as a
   `Fraction`. Conservation is `==` over sums. Nothing rounds, ever.

3. **An Area carries the identity of the ladder it was measured in.** A bare
   integer count of dhur is ambiguous: the bigha is not physically constant
   across Bihar districts, so `bihar.patna` and `bihar.mithila` have identical
   ladder *structure* and are still not interchangeable. Two Areas are equal
   only if their ladder ids match.

4. **Cross-ladder arithmetic needs a declared exact rational on both ladders,
   or it refuses.** `ConversionRefused` is not a failure to compute. It is the
   module declining to invent a conversion factor it does not have. Callers in
   the rules engine turn that refusal into `UNVERIFIABLE` — never into a pass,
   and never into a guess.

5. **Un-normalised input is preserved, not silently carried.** "27 katha" in a
   base-20 ladder is a transcription artefact and a Class 1 finding. `parse_area`
   computes its exact value *and* reports `is_normalised=False`. Carrying it
   quietly to "1 bigha 7 katha" would destroy the finding before any rule ran.

Same-ladder arithmetic needs no registry lookup, which is what lets rules stay
pure functions (AGENTS.md 3.2). Only parsing, formatting and conversion need a
registry, and it is always passed in explicitly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

__all__ = [
    "Area",
    "AreaParseError",
    "ConversionRefused",
    "DEFAULT_LADDERS_PATH",
    "LadderDataError",
    "LadderMismatch",
    "LadderRegistry",
    "NotIntegral",
    "ParsedArea",
    "UnitError",
    "UnitLadder",
    "UnknownLadder",
    "UnknownUnit",
    "convert",
    "default_registry",
    "exact_ratio",
    "format_area",
    "load_registry",
    "parse_area",
    "sum_areas",
]

DEFAULT_LADDERS_PATH = Path(__file__).with_name("ladders.json")


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------


class UnitError(Exception):
    """Base class for every failure raised by this module."""


class UnknownLadder(UnitError):
    """No ladder with that id is registered."""


class UnknownUnit(UnitError):
    """A unit name that the ladder does not define and no alias resolves."""


class LadderMismatch(UnitError):
    """Arithmetic or comparison between two Areas measured in different ladders."""


class ConversionRefused(UnitError):
    """Cross-ladder conversion with no declared exact rational on both sides.

    Deliberate. A ladder without an anchor has an unmeasured physical size, and
    inventing a factor here would manufacture conservation violations that look
    like findings.
    """


class NotIntegral(UnitError):
    """An exact area was requested as a whole number of smallest units and is not one."""


class AreaParseError(UnitError):
    """Input could not be read as an area in the given ladder."""


class LadderDataError(UnitError):
    """The ladder data file is malformed, or contains an inexact number."""


# --------------------------------------------------------------------------
# exactness gate
# --------------------------------------------------------------------------


def _exact(value: object) -> Fraction:
    """Accept only exact numeric types. Everything else is a bug, loudly."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    raise TypeError(
        "area quantities must be int or Fraction, got "
        f"{type(value).__name__!r}. Inexact binary numbers are banned from every "
        "area path (AGENTS.md 3.1) because conservation is checked with '=='."
    )


def _reject_inexact_literal(raw: str):
    raise LadderDataError(
        f"ladder data contains the inexact literal {raw!r}. Exact rationals are "
        "written as [numerator, denominator] integer pairs."
    )


# --------------------------------------------------------------------------
# ladders
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitLadder:
    """One region's unit ladder. Loaded from data; never hardcoded in a rule.

    `units` runs largest to smallest. `bases[i]` is how many `units[i + 1]`
    make one `units[i]`, so `len(bases) == len(units) - 1`.

    `smallest_unit_in_sqm` is the declared exact rational that permits
    cross-ladder arithmetic, or `None` when the physical size of this ladder's
    units has not been measured from a source we hold.
    """

    id: str
    region: str
    units: tuple[str, ...]
    bases: tuple[int, ...]
    aliases: Mapping[str, str]
    smallest_unit_in_sqm: Fraction | None
    anchor_source: str | None
    notes: str

    @property
    def smallest(self) -> str:
        return self.units[-1]

    @property
    def largest(self) -> str:
        return self.units[0]

    @property
    def is_anchored(self) -> bool:
        return self.smallest_unit_in_sqm is not None

    def canonical(self, unit: str) -> str:
        """Resolve a written unit name to a canonical one. Case- and space-insensitive."""
        key = unit.strip().lower()
        if key in self.units:
            return key
        resolved = self.aliases.get(key)
        if resolved is not None:
            return resolved
        raise UnknownUnit(
            f"{unit!r} is not a unit of ladder {self.id!r} "
            f"(units: {', '.join(self.units)})"
        )

    def factor(self, unit: str) -> int:
        """How many smallest units make one `unit`. Exact integer, always."""
        name = self.canonical(unit)
        index = self.units.index(name)
        result = 1
        for base in self.bases[index:]:
            result = result * base
        return result

    def base_above(self, unit: str) -> int | None:
        """The base this unit carries into. `None` for the largest unit."""
        name = self.canonical(unit)
        index = self.units.index(name)
        if index == 0:
            return None
        return self.bases[index - 1]

    def decompose(self, count: Fraction) -> tuple[Fraction, ...]:
        """Split an exact count of smallest units into components, largest first.

        Any non-integral remainder lands on the smallest unit as a Fraction. It
        is never rounded away.
        """
        exact = _exact(count)
        negative = exact < 0
        remaining = -exact if negative else exact
        parts: list[Fraction] = []
        for name in self.units[:-1]:
            size = self.factor(name)
            whole = remaining // size
            remaining = remaining - (whole * size)
            parts.append(Fraction(whole))
        parts.append(remaining)
        if negative:
            parts = [-part for part in parts]
        return tuple(parts)

    def compose(self, components: Mapping[str, object]) -> Fraction:
        """Sum written components into an exact count of smallest units."""
        total = Fraction(0)
        for written, quantity in components.items():
            name = self.canonical(written)
            total = total + (_exact(quantity) * self.factor(name))
        return total

    def area(self, **components: object) -> "Area":
        """Convenience constructor: `ladder.area(bigha=1, katha=7)`."""
        return Area(self.id, self.compose(components))

    def zero(self) -> "Area":
        return Area(self.id, Fraction(0))


@dataclass(frozen=True)
class LadderRegistry:
    """An immutable set of ladders, keyed by id."""

    ladders: Mapping[str, UnitLadder]

    def get(self, ladder_id: str) -> UnitLadder:
        try:
            return self.ladders[ladder_id]
        except KeyError:
            raise UnknownLadder(
                f"no ladder {ladder_id!r} is registered "
                f"(known: {', '.join(self.ids())})"
            ) from None

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.ladders))

    def __contains__(self, ladder_id: object) -> bool:
        return ladder_id in self.ladders

    def __len__(self) -> int:
        return len(self.ladders)


def _anchor_from_data(raw: object, ladder_id: str) -> Fraction | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        raise LadderDataError(
            f"ladder {ladder_id!r}: smallest_unit_in_sqm must be null or a "
            "[numerator, denominator] pair of integers"
        )
    numerator, denominator = raw
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise LadderDataError(
            f"ladder {ladder_id!r}: anchor numerator and denominator must be integers"
        )
    if numerator <= 0 or denominator <= 0:
        raise LadderDataError(
            f"ladder {ladder_id!r}: anchor must be a positive rational"
        )
    return Fraction(numerator, denominator)


def _ladder_from_data(entry: Mapping[str, object]) -> UnitLadder:
    try:
        ladder_id = entry["id"]
        units = tuple(entry["units"])
        bases = tuple(entry["bases"])
    except KeyError as missing:
        raise LadderDataError(f"ladder entry missing required key: {missing}") from None

    if not isinstance(ladder_id, str) or not ladder_id:
        raise LadderDataError("ladder id must be a non-empty string")
    if len(units) < 1:
        raise LadderDataError(f"ladder {ladder_id!r}: needs at least one unit")
    if len(bases) != len(units) - 1:
        raise LadderDataError(
            f"ladder {ladder_id!r}: expected {len(units) - 1} bases for "
            f"{len(units)} units, got {len(bases)}"
        )
    if len(set(units)) != len(units):
        raise LadderDataError(f"ladder {ladder_id!r}: duplicate unit name")
    for name in units:
        if not isinstance(name, str) or name != name.strip().lower():
            raise LadderDataError(
                f"ladder {ladder_id!r}: unit names must be lowercase and unpadded, "
                f"got {name!r}"
            )
    for base in bases:
        if not isinstance(base, int) or isinstance(base, bool) or base < 2:
            raise LadderDataError(
                f"ladder {ladder_id!r}: every base must be an integer >= 2, got {base!r}"
            )

    aliases_raw = entry.get("aliases") or {}
    if not isinstance(aliases_raw, dict):
        raise LadderDataError(f"ladder {ladder_id!r}: aliases must be an object")
    aliases: dict[str, str] = {}
    for written, target in aliases_raw.items():
        if target not in units:
            raise LadderDataError(
                f"ladder {ladder_id!r}: alias {written!r} points at {target!r}, "
                "which is not a unit of this ladder"
            )
        aliases[written.strip().lower()] = target

    anchor = _anchor_from_data(entry.get("smallest_unit_in_sqm"), ladder_id)
    anchor_source = entry.get("anchor_source")
    if anchor is not None and not anchor_source:
        raise LadderDataError(
            f"ladder {ladder_id!r}: an anchor requires a citation in anchor_source. "
            "An unsourced conversion factor is a fabricated measurement."
        )

    return UnitLadder(
        id=ladder_id,
        region=str(entry.get("region", "")),
        units=units,
        bases=bases,
        aliases=MappingProxyType(aliases),
        smallest_unit_in_sqm=anchor,
        anchor_source=anchor_source if isinstance(anchor_source, str) else None,
        notes=str(entry.get("notes", "")),
    )


def load_registry(path: Path | str | None = None) -> LadderRegistry:
    """Load ladders from JSON. Rejects any inexact literal in the file."""
    source = Path(path) if path is not None else DEFAULT_LADDERS_PATH
    with source.open(encoding="utf-8") as handle:
        data = json.load(handle, parse_float=_reject_inexact_literal)
    entries = data.get("ladders")
    if not isinstance(entries, list) or not entries:
        raise LadderDataError(f"{source}: no ladders defined")
    ladders: dict[str, UnitLadder] = {}
    for entry in entries:
        ladder = _ladder_from_data(entry)
        if ladder.id in ladders:
            raise LadderDataError(f"{source}: duplicate ladder id {ladder.id!r}")
        ladders[ladder.id] = ladder
    return LadderRegistry(MappingProxyType(ladders))


_DEFAULT_REGISTRY: LadderRegistry | None = None


def default_registry() -> LadderRegistry:
    """The bundled ladders, loaded once.

    Rules must take a registry as an argument rather than reaching for this, so
    that they stay pure (AGENTS.md 3.2). It exists for tests, tools and the
    presentation boundary.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = load_registry()
    return _DEFAULT_REGISTRY


# --------------------------------------------------------------------------
# area
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Area:
    """An exact area: a count of `ladder_id`'s smallest unit.

    Equality is ladder-scoped on purpose. `Area("bihar.patna", 400)` and
    `Area("bihar.mithila", 400)` are both "1 bigha" and are not equal, because
    the two bighas are not the same amount of ground.
    """

    ladder_id: str
    count: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.ladder_id, str) or not self.ladder_id:
            raise TypeError("Area.ladder_id must be a non-empty string")
        object.__setattr__(self, "count", _exact(self.count))

    # -- construction ------------------------------------------------------

    @classmethod
    def zero(cls, ladder_id: str) -> "Area":
        return cls(ladder_id, Fraction(0))

    # -- predicates --------------------------------------------------------

    @property
    def is_zero(self) -> bool:
        return self.count == 0

    @property
    def is_negative(self) -> bool:
        return self.count < 0

    @property
    def is_integral(self) -> bool:
        """True when this is a whole number of the ladder's smallest unit."""
        return self.count.denominator == 1

    def as_int(self) -> int:
        if not self.is_integral:
            raise NotIntegral(
                f"{self!r} is not a whole number of smallest units; it is "
                f"{self.count.numerator}/{self.count.denominator}"
            )
        return self.count.numerator

    # -- arithmetic --------------------------------------------------------

    def _same_ladder(self, other: "Area") -> None:
        if not isinstance(other, Area):
            raise TypeError(f"expected Area, got {type(other).__name__!r}")
        if other.ladder_id != self.ladder_id:
            raise LadderMismatch(
                f"cannot combine an area in {self.ladder_id!r} with one in "
                f"{other.ladder_id!r}. Convert explicitly, and be ready for "
                "ConversionRefused."
            )

    def __add__(self, other: "Area") -> "Area":
        self._same_ladder(other)
        return Area(self.ladder_id, self.count + other.count)

    def __sub__(self, other: "Area") -> "Area":
        self._same_ladder(other)
        return Area(self.ladder_id, self.count - other.count)

    def __neg__(self) -> "Area":
        return Area(self.ladder_id, -self.count)

    def __abs__(self) -> "Area":
        return Area(self.ladder_id, abs(self.count))

    def __mul__(self, factor: object) -> "Area":
        return Area(self.ladder_id, self.count * _exact(factor))

    __rmul__ = __mul__

    def __lt__(self, other: "Area") -> bool:
        self._same_ladder(other)
        return self.count < other.count

    def __le__(self, other: "Area") -> bool:
        self._same_ladder(other)
        return self.count <= other.count

    def __gt__(self, other: "Area") -> bool:
        self._same_ladder(other)
        return self.count > other.count

    def __ge__(self, other: "Area") -> bool:
        self._same_ladder(other)
        return self.count >= other.count

    # -- partition ---------------------------------------------------------

    def split(self, shares: Sequence[object]) -> tuple["Area", ...]:
        """Partition exactly by shares that must sum to exactly 1.

        Parts may be non-integral counts of the smallest unit. That is correct:
        an undivided half share of an odd number of dhur is half a dhur, and
        rounding it would break the conservation check downstream.
        """
        exact_shares = [_exact(share) for share in shares]
        if not exact_shares:
            raise ValueError("cannot split an area into zero parts")
        total = sum(exact_shares, Fraction(0))
        if total != 1:
            raise ValueError(
                f"shares must sum to exactly 1, got {total}. Co-owner shares are "
                "Fractions precisely so this is checkable with '=='."
            )
        return tuple(Area(self.ladder_id, self.count * share) for share in exact_shares)

    def __repr__(self) -> str:
        if self.count.denominator == 1:
            quantity = str(self.count.numerator)
        else:
            quantity = f"{self.count.numerator}/{self.count.denominator}"
        return f"Area({self.ladder_id!r}, {quantity} smallest)"


def sum_areas(areas: Iterable[Area], *, ladder_id: str | None = None) -> Area:
    """Exact sum. Raises on mixed ladders; needs `ladder_id` for an empty sum."""
    total: Area | None = None
    for area in areas:
        if not isinstance(area, Area):
            raise TypeError(f"expected Area, got {type(area).__name__!r}")
        if total is None:
            if ladder_id is not None and area.ladder_id != ladder_id:
                raise LadderMismatch(
                    f"expected areas in {ladder_id!r}, got one in {area.ladder_id!r}"
                )
            total = area
        else:
            total = total + area
    if total is not None:
        return total
    if ladder_id is None:
        raise ValueError(
            "summing an empty sequence needs an explicit ladder_id: a zero area "
            "still has to say which ladder it is zero in"
        )
    return Area.zero(ladder_id)


# --------------------------------------------------------------------------
# cross-ladder conversion
# --------------------------------------------------------------------------


def exact_ratio(
    source_ladder_id: str, target_ladder_id: str, registry: LadderRegistry
) -> Fraction:
    """How many target smallest-units make one source smallest-unit. Exact.

    Raises `ConversionRefused` unless both ladders carry a declared anchor.
    """
    source = registry.get(source_ladder_id)
    target = registry.get(target_ladder_id)
    if source.id == target.id:
        return Fraction(1)
    unanchored = [
        ladder.id for ladder in (source, target) if not ladder.is_anchored
    ]
    if unanchored:
        raise ConversionRefused(
            f"cannot convert {source.id!r} -> {target.id!r}: no declared exact "
            f"rational for {', '.join(unanchored)}. The physical size of those "
            "units has not been measured from a source we hold, and this module "
            "does not invent conversion factors. A rule hitting this must emit "
            "UNVERIFIABLE."
        )
    source_anchor = source.smallest_unit_in_sqm
    target_anchor = target.smallest_unit_in_sqm
    assert source_anchor is not None and target_anchor is not None
    return Fraction(
        source_anchor.numerator * target_anchor.denominator,
        source_anchor.denominator * target_anchor.numerator,
    )


def convert(area: Area, target_ladder_id: str, registry: LadderRegistry) -> Area:
    """Convert an Area into another ladder, exactly, or refuse."""
    if area.ladder_id == target_ladder_id:
        return area
    ratio = exact_ratio(area.ladder_id, target_ladder_id, registry)
    return Area(target_ladder_id, area.count * ratio)


# --------------------------------------------------------------------------
# presentation boundary: parse and format
# --------------------------------------------------------------------------

_TOKEN = re.compile(r"(?P<quantity>\d+(?:/\d+)?)\s*(?P<unit>[A-Za-z]+)")


@dataclass(frozen=True)
class ParsedArea:
    """The result of reading an area off a document.

    `area` is the exact value. `components` is what was actually written, in
    written order, before any carrying. `is_normalised` is False when a
    component should have carried into the unit above it — "27 katha" in a
    base-20 ladder. That is a Class 1 finding, so the fact is preserved here
    rather than quietly fixed.
    """

    area: Area
    components: tuple[tuple[str, Fraction], ...]
    is_normalised: bool
    over_base: tuple[str, ...]
    fractional_above_smallest: tuple[str, ...]


def parse_area(text: str, ladder_id: str, registry: LadderRegistry) -> ParsedArea:
    """Read "1 bigha 7 katha 3 dhur" into an exact Area, reporting artefacts."""
    ladder = registry.get(ladder_id)
    raw = text.strip()
    if not raw:
        raise AreaParseError("empty area string")

    negative = raw.startswith("-")
    if negative:
        raw = raw[1:].strip()

    matches = list(_TOKEN.finditer(raw))
    if not matches:
        raise AreaParseError(f"no quantity/unit pairs found in {text!r}")

    consumed = 0
    for match in matches:
        gap = raw[consumed : match.start()]
        if gap.strip():
            raise AreaParseError(f"unreadable fragment {gap.strip()!r} in {text!r}")
        consumed = match.end()
    trailing = raw[consumed:]
    if trailing.strip():
        raise AreaParseError(f"unreadable fragment {trailing.strip()!r} in {text!r}")

    components: list[tuple[str, Fraction]] = []
    seen: set[str] = set()
    total = Fraction(0)
    over_base: list[str] = []
    fractional_above_smallest: list[str] = []

    for match in matches:
        written = match.group("unit")
        name = ladder.canonical(written)
        if name in seen:
            raise AreaParseError(f"unit {name!r} appears twice in {text!r}")
        seen.add(name)

        quantity_text = match.group("quantity")
        if "/" in quantity_text:
            numerator_text, denominator_text = quantity_text.split("/", 1)
            denominator = int(denominator_text)
            if denominator == 0:
                raise AreaParseError(f"zero denominator in {text!r}")
            quantity = Fraction(int(numerator_text), denominator)
        else:
            quantity = Fraction(int(quantity_text))

        base = ladder.base_above(name)
        if base is not None and quantity >= base:
            over_base.append(name)
        if name != ladder.smallest and quantity.denominator != 1:
            fractional_above_smallest.append(name)

        components.append((name, quantity))
        total = total + (quantity * ladder.factor(name))

    if negative:
        total = -total

    return ParsedArea(
        area=Area(ladder_id, total),
        components=tuple(components),
        is_normalised=not over_base and not fractional_above_smallest,
        over_base=tuple(over_base),
        fractional_above_smallest=tuple(fractional_above_smallest),
    )


def _format_quantity(quantity: Fraction) -> str:
    if quantity.denominator == 1:
        return str(quantity.numerator)
    return f"{quantity.numerator}/{quantity.denominator}"


def format_area(area: Area, registry: LadderRegistry) -> str:
    """Canonical display form: largest unit first, zero components omitted.

    This is the only place an area becomes a string, and it is the presentation
    boundary named in HANDOFF_BUILD.md 3.5.
    """
    ladder = registry.get(area.ladder_id)
    magnitude = abs(area.count)
    parts = ladder.decompose(magnitude)
    pieces = [
        f"{_format_quantity(quantity)} {name}"
        for name, quantity in zip(ladder.units, parts)
        if quantity != 0
    ]
    if not pieces:
        pieces = [f"0 {ladder.smallest}"]
    body = " ".join(pieces)
    if area.count < 0:
        return f"-{body}"
    return body
