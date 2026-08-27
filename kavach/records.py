"""The canonical Phase 1 record model.

Shape and rationale are in `SCHEMA.md`; the sourced facts that forced three of its
corrections are in `EVIDENCE.md`. The short version of what is unusual here:

* **Two spines, joined.** Area lives on the spatial spine (Mouza -> recursive Khesra).
  Rights live on the tenurial spine (Mouza -> Khata -> Owner). `Holding` joins them
  many-to-many, because in Bihar partition is textual and several jamabandis do exist
  under one survey number (EVIDENCE.md E1).

* **Almost everything is optional.** `share`, `area_claimed`, `tenure`, `land_use` and
  the stated totals are all nullable, because real records omit them — measurably so.
  A missing value is not zero and not an error. It makes a check `UNVERIFIABLE`, which
  is a first-class output (AGENTS.md 3.3).

* **`is_leaf` is derived from an as-of date**, never stored. A stale leaf flag silently
  double-counts a parcel in the mouza trial balance.

* **Validity is declared on the container.** An undated record is not assumed current;
  see `SetKind` and `validity_status`.

* **No inexact numbers.** Shares are `Fraction`, areas are `kavach.units.Area`. The
  AST guard in `tests/test_units.py` scans this file too.

This module is data and derivation only. It performs no I/O, so rules built on it can
stay pure functions (AGENTS.md 3.2).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Any, Iterable, Mapping, Sequence

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    model_validator,
)

from kavach.units import Area

__all__ = [
    "AreaStatement",
    "EntityType",
    "ExactShare",
    "Holding",
    "Index",
    "Khata",
    "Khesra",
    "LeafStatus",
    "Membership",
    "Mouza",
    "Mutation",
    "Owner",
    "Provenance",
    "RecordSet",
    "Registration",
    "SetKind",
    "TemporalRecord",
    "TenureTotal",
    "ValidityStatus",
    "validity_status",
]

MAX_KHESRA_DEPTH = 32


# --------------------------------------------------------------------------
# exact scalars at the pydantic boundary
# --------------------------------------------------------------------------


def _to_exact_fraction(value: Any) -> Any:
    """Accept only exact representations of a rational. Reject the rest.

    A share read from JSON arrives as "1/3" or [1, 3]. Both are exact. Anything
    that is not on this list is refused rather than coerced, because a share is
    compared with '==' against 1.
    """
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise ValueError("a share must be a number, not a boolean")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"{value!r} is not an exact rational") from exc
    if isinstance(value, (list, tuple)) and len(value) == 2:
        numerator, denominator = value
        if isinstance(numerator, int) and isinstance(denominator, int):
            if denominator == 0:
                raise ValueError("a share cannot have a zero denominator")
            return Fraction(numerator, denominator)
    raise ValueError(
        f"cannot read {type(value).__name__!r} as an exact share. Use a Fraction, an "
        "int, an 'n/d' string, or an [n, d] pair. Inexact binary numbers are banned "
        "from every area and share path (AGENTS.md 3.1)."
    )


def _to_area(value: Any) -> Any:
    if isinstance(value, Area):
        return value
    if isinstance(value, Mapping):
        try:
            return Area(value["ladder_id"], _to_exact_fraction(value["count"]))
        except KeyError as missing:
            raise ValueError(f"an area needs {missing} as well") from None
    raise ValueError(
        f"cannot read {type(value).__name__!r} as an Area. An Area is "
        '{"ladder_id": ..., "count": "n/d"} — it always names its ladder.'
    )


ExactShare = Annotated[
    Fraction,
    BeforeValidator(_to_exact_fraction),
    PlainSerializer(str, return_type=str),
]

ExactArea = Annotated[
    Area,
    BeforeValidator(_to_area),
    PlainSerializer(
        lambda area: {"ladder_id": area.ladder_id, "count": str(area.count)},
        return_type=dict,
    ),
]


# --------------------------------------------------------------------------
# enums
# --------------------------------------------------------------------------


class EntityType(StrEnum):
    MOUZA = "mouza"
    KHESRA = "khesra"
    KHATA = "khata"
    OWNER = "owner"
    MEMBERSHIP = "membership"
    HOLDING = "holding"
    MUTATION = "mutation"
    REGISTRATION = "registration"


class SetKind(StrEnum):
    """How a RecordSet's undated records should be read.

    This is a declaration made once on the container, not a default applied
    silently per record.
    """

    SNAPSHOT = "snapshot"
    MULTI_VERSION = "multi_version"


class ValidityStatus(StrEnum):
    VALID = "valid"
    SUPERSEDED = "superseded"
    NOT_YET_VALID = "not_yet_valid"
    UNKNOWN = "unknown"


class LeafStatus(StrEnum):
    """Whether a khesra is still an atomic parcel at a given date."""

    LEAF = "leaf"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# base
# --------------------------------------------------------------------------


class KavachModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )


class TemporalRecord(KavachModel):
    """Anything that can be superseded carries a half-open validity interval.

    `[valid_from, valid_to)`. Either end may be `None`, meaning unknown — which is
    not the same as open, and is handled explicitly by `validity_status`.
    """

    valid_from: dt.date | None = None
    valid_to: dt.date | None = None

    @model_validator(mode="after")
    def _interval_is_ordered(self):
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError(
                f"valid_to {self.valid_to} must be after valid_from {self.valid_from}"
            )
        return self


def validity_status(
    record: TemporalRecord,
    as_of: dt.date | None,
    *,
    set_kind: SetKind,
    snapshot_as_of: dt.date | None,
) -> ValidityStatus:
    """Was this record in force at `as_of`? `UNKNOWN` is a real answer.

    An undated record in a `SNAPSHOT` set is valid at that snapshot's date and
    unknown at any other. An undated record in a `MULTI_VERSION` set is always
    unknown — that is exactly the case where a naive engine reports duplicate
    khatas that are really just superseded rows.
    """
    if as_of is None:
        return ValidityStatus.VALID

    starts, ends = record.valid_from, record.valid_to

    if starts is None and ends is None:
        if set_kind is SetKind.SNAPSHOT and snapshot_as_of == as_of:
            return ValidityStatus.VALID
        return ValidityStatus.UNKNOWN

    if starts is not None and as_of < starts:
        return ValidityStatus.NOT_YET_VALID
    if ends is not None and as_of >= ends:
        return ValidityStatus.SUPERSEDED
    if starts is None:
        return ValidityStatus.UNKNOWN
    return ValidityStatus.VALID


# --------------------------------------------------------------------------
# value objects
# --------------------------------------------------------------------------


class Provenance(KavachModel):
    """Where a value came from. Not a confidence — there is no model yet."""

    document_id: str
    page: int | None = None
    cell: str | None = None
    note: str | None = None


class Identifier(KavachModel):
    """A scheme-qualified identifier: khasra, survey no., gat no., jamabandi sankhya.

    A list of these, rather than fixed columns, because khata is not patta and
    Maharashtra's 7/12 has no khata at all (SCHEMA.md 6).
    """

    scheme: str
    value: str


class AreaStatement(KavachModel):
    """One written assertion of an area.

    `as_written` is the raw document string, kept so the unit-carry check has
    something to check — normalising "27 katha" to "1 bigha 7 katha" on load would
    delete a Class 1 finding before Class 1 ran.
    """

    area: ExactArea
    as_written: str | None = None
    provenance: Provenance | None = None


# --------------------------------------------------------------------------
# entities
# --------------------------------------------------------------------------


class TenureTotal(KavachModel):
    """A per-tenure subtotal stated independently of the parcels.

    Without these, flipping one parcel from raiyati to gairmazrua is arithmetically
    undetectable: the partition still sums to the mouza total. HANDOFF_BUILD.md 5.2
    expects that flip to be caught by Class 2, which is only possible if the mouza
    states the subtotals separately. Discovered while writing the mutation engine.
    """

    code: str
    area_stated: AreaStatement


class Mouza(TemporalRecord):
    id: str
    name: str
    district: str
    subdistrict: str | None = None
    subdistrict_term: str | None = None
    ladder_id: str
    identifiers: tuple[Identifier, ...] = ()
    area_stated: AreaStatement | None = None
    tenure_totals: tuple[TenureTotal, ...] = ()
    classification_scheme: str | None = None
    survey_date: dt.date | None = None

    @model_validator(mode="after")
    def _total_needs_provenance(self):
        """SCHEMA.md 4: a mouza total without a source cannot anchor a trial balance."""
        if self.area_stated is not None and self.area_stated.provenance is None:
            raise ValueError(
                f"mouza {self.id!r}: area_stated requires provenance. A conservation "
                "failure measured against an unsourced, undated total is not evidence "
                "that the records are wrong."
            )
        return self


class Khesra(TemporalRecord):
    """The atomic parcel — and, when sub-divided, the internal node above them.

    `local_number` is one path segment ("217", or "1" for 217/1), never the whole
    path. Sub-division is recursion through `parent_khesra_id`, unbounded in depth,
    so 217/1/2 needs no new level.
    """

    id: str
    mouza_id: str
    parent_khesra_id: str | None = None
    local_number: str
    identifiers: tuple[Identifier, ...] = ()
    area_stated: AreaStatement | None = None
    area_restatements: tuple[AreaStatement, ...] = ()
    tenure: str | None = None
    land_use: str | None = None
    classification_scheme: str | None = None

    @model_validator(mode="after")
    def _not_its_own_parent(self):
        if self.parent_khesra_id == self.id:
            raise ValueError(f"khesra {self.id!r} is its own parent")
        return self


class Khata(TemporalRecord):
    """The tenurial account. Holds no area itself beyond what the document states."""

    id: str
    mouza_id: str
    number: str
    identifiers: tuple[Identifier, ...] = ()
    area_stated: AreaStatement | None = None


class Owner(TemporalRecord):
    """Identity is fuzzy by construction. There is no reliable key.

    Any rule that depends on matching two Owners emits CONFLICT or ANOMALY, never
    CERTAIN_ERROR. `name_raw` is what the document said, unmodified.
    """

    id: str
    name_raw: str
    qualifiers: tuple[str, ...] = ()


class Membership(TemporalRecord):
    """An owner's stake in a khata.

    `share` is normally `None`: EVIDENCE.md E2 records that Bihar jamabandis with
    multiple owners state no shares at all. So "co-owner shares sum to 1" abstains
    on real input rather than passing.
    """

    id: str
    khata_id: str
    owner_id: str
    share: ExactShare | None = None


class Holding(TemporalRecord):
    """The many-to-many join between a khata and a khesra — the thing SCHEMA.md added.

    Both `share` and `area_claimed` are optional and neither is required. On Bihar
    jamabandi input `area_claimed` is the populated one and `share` is empty
    (EVIDENCE.md E3); a blank-area jamabandi is also a documented real state
    (EVIDENCE.md E5) and makes this holding's conservation check UNVERIFIABLE.
    """

    id: str
    khata_id: str
    khesra_id: str
    share: ExactShare | None = None
    area_claimed: AreaStatement | None = None


class Mutation(TemporalRecord):
    id: str
    mouza_id: str
    subject_type: EntityType
    subject_id: str
    date: dt.date | None = None
    kind: str | None = None
    order_ref: str | None = None
    from_state: str | None = None
    to_state: str | None = None


class Registration(TemporalRecord):
    id: str
    mouza_id: str
    khesra_id: str | None = None
    external_system: str
    reference: str
    date: dt.date | None = None


# --------------------------------------------------------------------------
# the container
# --------------------------------------------------------------------------


class RecordSet(KavachModel):
    """Everything known about one mouza, plus how to read its dates.

    `kind` and `as_of` are the declaration that makes Ruling 2 real: they say once,
    in one place, how an undated record should be treated, instead of every rule
    guessing.
    """

    mouza: Mouza
    kind: SetKind
    source: str
    as_of: dt.date | None = None
    khesras: tuple[Khesra, ...] = ()
    khatas: tuple[Khata, ...] = ()
    owners: tuple[Owner, ...] = ()
    memberships: tuple[Membership, ...] = ()
    holdings: tuple[Holding, ...] = ()
    mutations: tuple[Mutation, ...] = ()
    registrations: tuple[Registration, ...] = ()

    @model_validator(mode="after")
    def _snapshot_declares_its_date(self):
        if self.kind is SetKind.SNAPSHOT and self.as_of is None:
            raise ValueError(
                "a SNAPSHOT record set must state its as_of date. Without one there "
                "is no date at which its undated records can be called current."
            )
        return self

    @property
    def ladder_id(self) -> str:
        return self.mouza.ladder_id

    def index(self, as_of: dt.date | None = None) -> "Index":
        return Index.build(self, as_of)


# --------------------------------------------------------------------------
# derived views
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Index:
    """Derived structure over a RecordSet at one as-of date.

    Everything here is computed, never stored on an entity: leaf status, paths,
    parent/child links, and which records could not be dated. Rules read this and
    remain pure.

    `unknown_*` is the load-bearing part. Records whose validity could not be
    determined are neither included nor silently dropped — they are handed to the
    rule so it can abstain instead of guessing.
    """

    records: RecordSet
    as_of: dt.date | None
    khesras: tuple[Khesra, ...]
    khatas: tuple[Khata, ...]
    owners: tuple[Owner, ...]
    memberships: tuple[Membership, ...]
    holdings: tuple[Holding, ...]
    unknown_khesras: tuple[Khesra, ...]
    unknown_khatas: tuple[Khata, ...]
    unknown_memberships: tuple[Membership, ...]
    unknown_holdings: tuple[Holding, ...]
    khesra_by_id: Mapping[str, Khesra]
    khata_by_id: Mapping[str, Khata]
    owner_by_id: Mapping[str, Owner]
    children: Mapping[str, tuple[Khesra, ...]]
    unknown_children: Mapping[str, tuple[Khesra, ...]]
    holdings_by_khata: Mapping[str, tuple[Holding, ...]]
    holdings_by_khesra: Mapping[str, tuple[Holding, ...]]
    memberships_by_khata: Mapping[str, tuple[Membership, ...]]
    memberships_by_owner: Mapping[str, tuple[Membership, ...]]
    cyclic_khesra_ids: frozenset[str]

    @classmethod
    def build(cls, records: RecordSet, as_of: dt.date | None = None) -> "Index":
        def partition(items: Sequence[TemporalRecord]):
            live, unknown = [], []
            for item in items:
                status = validity_status(
                    item,
                    as_of,
                    set_kind=records.kind,
                    snapshot_as_of=records.as_of,
                )
                if status is ValidityStatus.VALID:
                    live.append(item)
                elif status is ValidityStatus.UNKNOWN:
                    unknown.append(item)
            return tuple(live), tuple(unknown)

        khesras, unknown_khesras = partition(records.khesras)
        khatas, unknown_khatas = partition(records.khatas)
        owners, _ = partition(records.owners)
        memberships, unknown_memberships = partition(records.memberships)
        holdings, unknown_holdings = partition(records.holdings)

        def group(items, key):
            out: dict[str, list] = {}
            for item in items:
                out.setdefault(key(item), []).append(item)
            return {k: tuple(v) for k, v in out.items()}

        children = group(
            [k for k in khesras if k.parent_khesra_id], lambda k: k.parent_khesra_id
        )
        unknown_children = group(
            [k for k in unknown_khesras if k.parent_khesra_id],
            lambda k: k.parent_khesra_id,
        )

        khesra_by_id = {k.id: k for k in khesras}
        cyclic = cls._find_cycles(khesra_by_id)

        return cls(
            records=records,
            as_of=as_of,
            khesras=khesras,
            khatas=khatas,
            owners=owners,
            memberships=memberships,
            holdings=holdings,
            unknown_khesras=unknown_khesras,
            unknown_khatas=unknown_khatas,
            unknown_memberships=unknown_memberships,
            unknown_holdings=unknown_holdings,
            khesra_by_id=khesra_by_id,
            khata_by_id={k.id: k for k in khatas},
            owner_by_id={o.id: o for o in owners},
            children=children,
            unknown_children=unknown_children,
            holdings_by_khata=group(holdings, lambda h: h.khata_id),
            holdings_by_khesra=group(holdings, lambda h: h.khesra_id),
            memberships_by_khata=group(memberships, lambda m: m.khata_id),
            memberships_by_owner=group(memberships, lambda m: m.owner_id),
            cyclic_khesra_ids=cyclic,
        )

    @staticmethod
    def _find_cycles(khesra_by_id: Mapping[str, Khesra]) -> frozenset[str]:
        """Parent pointers that loop. A data error, reported rather than raised."""
        cyclic: set[str] = set()
        for start in khesra_by_id:
            seen: set[str] = set()
            current: str | None = start
            steps = 0
            while current is not None and steps <= MAX_KHESRA_DEPTH:
                if current in seen:
                    cyclic.update(seen)
                    break
                seen.add(current)
                node = khesra_by_id.get(current)
                current = node.parent_khesra_id if node else None
                steps += 1
            else:
                if current is not None:
                    cyclic.update(seen)
        return frozenset(cyclic)

    # -- derived predicates ------------------------------------------------

    def leaf_status(self, khesra_id: str) -> LeafStatus:
        """Is this still an atomic parcel at `as_of`? Derived, never stored.

        `UNKNOWN` when the only children found could not be dated — in that case
        we genuinely do not know whether this parcel still holds area, and a
        conservation rule must abstain rather than double-count it.
        """
        if self.children.get(khesra_id):
            return LeafStatus.INTERNAL
        if self.unknown_children.get(khesra_id):
            return LeafStatus.UNKNOWN
        return LeafStatus.LEAF

    def leaves(self) -> tuple[Khesra, ...]:
        return tuple(
            k for k in self.khesras if self.leaf_status(k.id) is LeafStatus.LEAF
        )

    def undetermined_leaves(self) -> tuple[Khesra, ...]:
        return tuple(
            k for k in self.khesras if self.leaf_status(k.id) is LeafStatus.UNKNOWN
        )

    def path_of(self, khesra_id: str) -> tuple[str, ...] | None:
        """Local numbers from root to this khesra. `None` if it sits in a cycle."""
        if khesra_id in self.cyclic_khesra_ids:
            return None
        segments: list[str] = []
        current: str | None = khesra_id
        steps = 0
        while current is not None:
            node = self.khesra_by_id.get(current)
            if node is None:
                break
            segments.append(node.local_number)
            current = node.parent_khesra_id
            steps += 1
            if steps > MAX_KHESRA_DEPTH:
                return None
        return tuple(reversed(segments))

    def display_path(self, khesra_id: str, separator: str = "/") -> str | None:
        path = self.path_of(khesra_id)
        return separator.join(path) if path is not None else None

    def depth_of(self, khesra_id: str) -> int | None:
        path = self.path_of(khesra_id)
        return len(path) if path is not None else None

    def siblings_of(self, khesra_id: str) -> tuple[Khesra, ...]:
        node = self.khesra_by_id.get(khesra_id)
        if node is None:
            return ()
        if node.parent_khesra_id is None:
            return tuple(k for k in self.khesras if k.parent_khesra_id is None)
        return self.children.get(node.parent_khesra_id, ())

    def roots(self) -> tuple[Khesra, ...]:
        return tuple(k for k in self.khesras if k.parent_khesra_id is None)

    def has_undated_records(self) -> bool:
        return bool(
            self.unknown_khesras
            or self.unknown_khatas
            or self.unknown_memberships
            or self.unknown_holdings
        )
