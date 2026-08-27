"""Class 8 — the witness census. Not a check.

For each parcel this records how many checks *could* run at all, given the records
present. That produces the **verifiability rate**: the fraction of checks that have a
witness, as opposed to the fraction that pass.

It is a rate, not an error rate. A parcel with no second witness is not wrong; it is
unexaminable, and nobody currently measures how much of the register is in that state.

Two properties matter (AGENTS.md 3.5):

* It must be computable **when every other class abstains** — it reads presence, never
  values, so it still returns a number on a record set nothing else can touch.
* The denominator is a fixed, named list of witnesses. A rate whose denominator moves
  with the data is not a measurement.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from kavach.findings import RuleScope, rule
from kavach.records import Index, RecordSet
from kavach.rules._support import khesra_subject, mouza_subject
from kavach.units import LadderRegistry, default_registry

RULES: list = []

WITNESSES: tuple[tuple[str, str], ...] = (
    ("own_area", "the parcel states its own area"),
    ("own_area_written", "the area is recorded as it was written"),
    ("cross_unit_restatement", "the area is restated in a second unit system"),
    ("parent_area", "the parent parcel states an area to reconcile against"),
    ("child_areas", "every sub-plot states an area"),
    ("mouza_total", "the mouza states a total"),
    ("holding_claimed_area", "at least one holding states a claimed area"),
    ("holding_share", "at least one holding states a share"),
    ("khata_total", "every holding khata states a total"),
    ("co_owner_shares", "every owner of every holding khata has a recorded share"),
    ("tenure_class", "the parcel carries a tenure class"),
    ("tenure_subtotal", "the mouza states a subtotal for that tenure class"),
)

WITNESS_NAMES: tuple[str, ...] = tuple(name for name, _ in WITNESSES)


def census_rule(rule_id: str, scope: RuleScope = RuleScope.WITHIN_VERSION):
    def wrap(fn):
        declared = rule(rule_id, 8, scope)(fn)
        RULES.append(declared)
        return declared

    return wrap


@dataclass(frozen=True)
class ParcelCensus:
    """Which witnesses exist for one parcel. Presence only, never values."""

    khesra_id: str
    display: str
    present: tuple[str, ...]
    absent: tuple[str, ...]

    @property
    def possible(self) -> int:
        return len(self.present)

    @property
    def total(self) -> int:
        return len(self.present) + len(self.absent)

    @property
    def rate(self) -> Fraction | None:
        return Fraction(self.possible, self.total) if self.total else None

    @property
    def is_unexaminable(self) -> bool:
        """No witness at all. Nothing about this parcel can be checked by anything."""
        return self.possible == 0


@dataclass(frozen=True)
class WitnessCensus:
    parcels: tuple[ParcelCensus, ...]
    as_of: dt.date | None
    source: str

    @property
    def verifiability_rate(self) -> Fraction | None:
        """Witnesses present over witnesses possible, across every parcel."""
        possible = sum(p.possible for p in self.parcels)
        total = sum(p.total for p in self.parcels)
        return Fraction(possible, total) if total else None

    @property
    def unexaminable(self) -> tuple[ParcelCensus, ...]:
        return tuple(p for p in self.parcels if p.is_unexaminable)

    def by_witness(self) -> Mapping[str, Fraction]:
        """Per-witness availability, so the rate can be explained rather than asserted."""
        out: dict[str, Fraction] = {}
        if not self.parcels:
            return out
        for name in WITNESS_NAMES:
            hits = sum(1 for p in self.parcels if name in p.present)
            out[name] = Fraction(hits, len(self.parcels))
        return out

    def report(self) -> str:
        lines = [
            "witness census — a rate, not an error rate",
            f"  source                 {self.source}",
            f"  as of                  {self.as_of}",
            f"  parcels                {len(self.parcels)}",
            f"  unexaminable parcels   {len(self.unexaminable)}",
        ]
        rate = self.verifiability_rate
        if rate is None:
            lines.append("  verifiability rate     None (no parcels)")
        else:
            percent = (100 * rate.numerator) // rate.denominator
            lines.append(f"  verifiability rate     {rate} (~{percent}%)")
        lines.append("")
        lines.append("  witness availability")
        for name, share in self.by_witness().items():
            percent = (100 * share.numerator) // share.denominator
            lines.append(f"    {name:24} {percent:>3}%")
        return "\n".join(lines)


def _witnesses_for(khesra, index: Index, records: RecordSet) -> tuple[list[str], list[str]]:
    present: list[str] = []
    holdings = index.holdings_by_khesra.get(khesra.id, ())
    khatas = [index.khata_by_id.get(h.khata_id) for h in holdings]
    children = index.children.get(khesra.id, ())

    checks = {
        "own_area": khesra.area_stated is not None,
        "own_area_written": bool(khesra.area_stated and khesra.area_stated.as_written),
        "cross_unit_restatement": bool(khesra.area_restatements),
        "parent_area": bool(
            khesra.parent_khesra_id
            and (parent := index.khesra_by_id.get(khesra.parent_khesra_id))
            and parent.area_stated is not None
        ),
        "child_areas": bool(children) and all(c.area_stated is not None for c in children),
        "mouza_total": records.mouza.area_stated is not None,
        "holding_claimed_area": any(h.area_claimed is not None for h in holdings),
        "holding_share": any(h.share is not None for h in holdings),
        "khata_total": bool(khatas) and all(
            k is not None and k.area_stated is not None for k in khatas
        ),
        "co_owner_shares": bool(khatas)
        and all(
            k is not None
            and (members := index.memberships_by_khata.get(k.id, ()))
            and all(m.share is not None for m in members)
            for k in khatas
        ),
        "tenure_class": khesra.tenure is not None,
        "tenure_subtotal": bool(khesra.tenure)
        and any(t.code == khesra.tenure for t in records.mouza.tenure_totals),
    }
    absent = [name for name in WITNESS_NAMES if not checks[name]]
    present = [name for name in WITNESS_NAMES if checks[name]]
    return present, absent


def witness_census(
    records: RecordSet,
    registry: LadderRegistry | None = None,
    as_of: dt.date | None = None,
) -> WitnessCensus:
    """Count what could be checked. Runs when every other class abstains."""
    registry = registry or default_registry()
    index = records.index(as_of if as_of is not None else records.as_of)
    parcels = []
    for khesra in index.leaves():
        present, absent = _witnesses_for(khesra, index, records)
        parcels.append(
            ParcelCensus(
                khesra_id=khesra.id,
                display=index.display_path(khesra.id) or khesra.local_number,
                present=tuple(present),
                absent=tuple(absent),
            )
        )
    return WitnessCensus(
        parcels=tuple(parcels), as_of=index.as_of, source=records.source
    )


def verifiability_rate(
    records: RecordSet,
    registry: LadderRegistry | None = None,
    as_of: dt.date | None = None,
) -> Fraction | None:
    """The fraction of checks that have a witness at all. `None` if there is nothing."""
    return witness_census(records, registry, as_of).verifiability_rate
