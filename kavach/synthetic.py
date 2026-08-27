"""Synthetic mouza generator — every invariant holds by construction.

HANDOFF_BUILD.md 5.1. This produces record sets in which areas partition exactly,
sub-division sequences are gapless, shares sum to exactly one, no identifier repeats,
and the tenure subtotals reconcile. The first assertion of the whole project is that
the engine finds nothing wrong with one of these.

**Everything this module produces is labelled synthetic** (AGENTS.md 2). `RecordSet.source`
carries the `synthetic:` prefix, owner names are `SYNTH-OWNER-nnnn`, and
`is_synthetic()` exists so nothing here can be mistaken for measurement.

`verify_synthetic_invariants` is deliberately **not** built on the rules engine. It
re-derives every invariant from the finished record set. If the generator and the
checker shared code, the mutation tests would be circular and would prove nothing.

Document profiles matter as much as size. Real inputs differ in which witnesses exist,
and that is exactly what Class 8 measures:

* `KHATIAN`   — classification and shares present, no per-holding areas
* `JAMABANDI` — no classification, no shares, per-holding areas present, no mouza total
                (EVIDENCE.md E2, E3, E6)
* `COMBINED`  — both lineages reconciled; every witness present
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction


from kavach.classifications import SchemeRegistry, default_schemes
from kavach.records import (
    AreaStatement,
    Holding,
    Khata,
    Khesra,
    Membership,
    Mouza,
    Mutation,
    Owner,
    Provenance,
    RecordSet,
    Registration,
    SetKind,
    TenureTotal,
    EntityType,
)
from kavach.units import Area, LadderRegistry, convert, default_registry, format_area, parse_area

__all__ = [
    "DocumentProfile",
    "MouzaSpec",
    "SYNTHETIC_SOURCE_PREFIX",
    "is_synthetic",
    "synthetic_mouza",
    "verify_synthetic_invariants",
]

SYNTHETIC_SOURCE_PREFIX = "synthetic:"


class DocumentProfile(StrEnum):
    KHATIAN = "khatian"
    JAMABANDI = "jamabandi"
    COMBINED = "combined"


@dataclass(frozen=True)
class MouzaSpec:
    """Parameters for one synthetic mouza. Deterministic given `seed`."""

    seed: int = 1
    ladder_id: str = "bihar.jamabandi"
    profile: DocumentProfile = DocumentProfile.COMBINED
    scheme_id: str = "bihar.khatiyan"
    root_khesras: int = 12
    total_area: int = 20_000
    subdivide_percent: int = 40
    max_depth: int = 3
    max_children: int = 4
    max_holders_per_parcel: int = 3
    max_owners_per_khata: int = 3
    khatas: int = 10
    mutations: int = 4
    first_survey_number: int = 101
    survey_date: dt.date = dt.date(1900, 1, 1)
    as_of: dt.date = dt.date(2026, 1, 1)

    def __post_init__(self) -> None:
        if self.total_area < self.root_khesras:
            raise ValueError(
                f"total_area {self.total_area} cannot be partitioned into "
                f"{self.root_khesras} parcels of at least one unit each"
            )
        for name in ("root_khesras", "max_children", "max_holders_per_parcel",
                     "max_owners_per_khata", "khatas"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if not 0 <= self.subdivide_percent <= 100:
            raise ValueError("subdivide_percent must be between 0 and 100")
        if self.max_children < 2 and self.subdivide_percent > 0:
            raise ValueError("max_children must be at least 2 to subdivide")
        if self.as_of < self.survey_date:
            raise ValueError("as_of cannot precede survey_date")

    @property
    def source(self) -> str:
        return (
            f"{SYNTHETIC_SOURCE_PREFIX}seed={self.seed}"
            f":profile={self.profile}:ladder={self.ladder_id}"
        )


def is_synthetic(records: RecordSet) -> bool:
    """True when this record set was generated, not measured."""
    return records.source.startswith(SYNTHETIC_SOURCE_PREFIX)


# --------------------------------------------------------------------------
# exact integer partition
# --------------------------------------------------------------------------


def _compose(rng: random.Random, total: int, parts: int) -> list[int]:
    """Split `total` into `parts` positive integers that sum to it exactly."""
    if parts < 1:
        raise ValueError("need at least one part")
    if total < parts:
        raise ValueError(f"cannot split {total} into {parts} positive parts")
    if parts == 1:
        return [total]
    cuts = sorted(rng.sample(range(1, total), parts - 1))
    out: list[int] = []
    previous = 0
    for cut in cuts:
        out.append(cut - previous)
        previous = cut
    out.append(total - previous)
    return out


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------


def synthetic_mouza(
    spec: MouzaSpec | None = None,
    registry: LadderRegistry | None = None,
    schemes: SchemeRegistry | None = None,
) -> RecordSet:
    spec = spec or MouzaSpec()
    registry = registry or default_registry()
    schemes = schemes or default_schemes()
    ladder = registry.get(spec.ladder_id)
    scheme = schemes.get(spec.scheme_id)
    rng = random.Random(spec.seed)

    wants_classification = spec.profile in (
        DocumentProfile.KHATIAN,
        DocumentProfile.COMBINED,
    )
    wants_shares = spec.profile in (DocumentProfile.KHATIAN, DocumentProfile.COMBINED)
    wants_claimed_areas = spec.profile in (
        DocumentProfile.JAMABANDI,
        DocumentProfile.COMBINED,
    )
    wants_mouza_total = spec.profile in (
        DocumentProfile.KHATIAN,
        DocumentProfile.COMBINED,
    )
    wants_restatements = spec.profile is DocumentProfile.COMBINED

    def statement(units: int, page: int) -> AreaStatement:
        area = Area(spec.ladder_id, Fraction(units))
        return AreaStatement(
            area=area,
            as_written=format_area(area, registry),
            provenance=Provenance(
                document_id=f"SYNTH-DOC-{spec.seed}", page=page, cell=None
            ),
        )

    # -- spatial spine: roots, then recursive sub-division ------------------

    khesras: list[Khesra] = []
    leaf_area: dict[str, int] = {}
    node_area: dict[str, int] = {}
    counter = [0]

    def new_khesra_id() -> str:
        counter[0] += 1
        return f"KHS-{counter[0]:04d}"

    def build(parent_id: str | None, local_number: str, units: int, depth: int) -> str:
        khesra_id = new_khesra_id()
        node_area[khesra_id] = units
        can_split = (
            depth < spec.max_depth
            and units >= 2
            and rng.randint(1, 100) <= spec.subdivide_percent
        )
        children: list[str] = []
        if can_split:
            child_count = rng.randint(2, min(spec.max_children, units))
            for position, child_units in enumerate(
                _compose(rng, units, child_count), start=1
            ):
                children.append(
                    build(khesra_id, str(position), child_units, depth + 1)
                )
        tenure = (
            rng.choice(scheme.tenure_codes) if wants_classification and not children else None
        )
        khesras.append(
            Khesra(
                id=khesra_id,
                mouza_id="MZ-SYNTH",
                parent_khesra_id=parent_id,
                local_number=local_number,
                area_stated=statement(units, page=1 + depth),
                area_restatements=(
                    (
                        AreaStatement(
                            area=convert(
                                Area(spec.ladder_id, Fraction(units)),
                                "metric.hectare",
                                registry,
                            ),
                            as_written=None,
                            provenance=Provenance(
                                document_id=f"SYNTH-DOC-{spec.seed}",
                                page=1 + depth,
                                cell="rakba/hectare",
                            ),
                        ),
                    )
                    if wants_restatements and ladder.is_anchored
                    else ()
                ),
                tenure=tenure,
                land_use=None,
                classification_scheme=spec.scheme_id if tenure else None,
                valid_from=spec.survey_date,
            )
        )
        if not children:
            leaf_area[khesra_id] = units
        return khesra_id

    for index, units in enumerate(_compose(rng, spec.total_area, spec.root_khesras)):
        build(None, str(spec.first_survey_number + index), units, depth=1)

    # -- allocate leaves to khatas -----------------------------------------

    slots: list[tuple[str, int]] = []
    for khesra_id in sorted(leaf_area):
        units = leaf_area[khesra_id]
        holders = rng.randint(1, min(spec.max_holders_per_parcel, units))
        for part in _compose(rng, units, holders):
            slots.append((khesra_id, part))

    holders_per_leaf = max(
        (sum(1 for k, _ in slots if k == leaf) for leaf in leaf_area), default=1
    )
    khata_count = max(holders_per_leaf, min(spec.khatas, len(slots)))

    khatas = [
        Khata(
            id=f"KHT-{n:04d}",
            mouza_id="MZ-SYNTH",
            number=str(2000 + n),
            valid_from=spec.survey_date,
        )
        for n in range(1, khata_count + 1)
    ]

    # Round-robin. A run of h consecutive slots over a cycle of `khata_count`
    # distinct khatas lands on h distinct khatas whenever h <= khata_count, which
    # `holders_per_leaf` guarantees. Dealing every slot guarantees no empty khata,
    # because len(slots) >= khata_count.
    holdings: list[Holding] = []
    for position, (khesra_id, part) in enumerate(slots):
        khata = khatas[position % khata_count]
        holdings.append(
            Holding(
                id=f"HLD-{position + 1:04d}",
                khata_id=khata.id,
                khesra_id=khesra_id,
                share=Fraction(part, leaf_area[khesra_id]) if wants_shares else None,
                area_claimed=(
                    statement(part, page=7) if wants_claimed_areas else None
                ),
                valid_from=spec.survey_date,
            )
        )

    # -- khata stated totals, from the holdings just built ------------------

    khata_units: dict[str, int] = {}
    for holding, (_, part) in zip(holdings, slots):
        khata_units[holding.khata_id] = khata_units.get(holding.khata_id, 0) + part
    khatas = [
        khata.model_copy(update={"area_stated": statement(khata_units[khata.id], page=6)})
        for khata in khatas
    ]

    # -- owners: each belongs to exactly one khata --------------------------

    owners: list[Owner] = []
    memberships: list[Membership] = []
    for khata in khatas:
        count = rng.randint(1, spec.max_owners_per_khata)
        for position in range(count):
            owner_id = f"OWN-{len(owners) + 1:04d}"
            owners.append(
                Owner(
                    id=owner_id,
                    name_raw=f"SYNTH-OWNER-{len(owners) + 1:04d}",
                    qualifiers=(f"s/o SYNTH-PARENT-{len(owners) + 1:04d}",),
                    valid_from=spec.survey_date,
                )
            )
            memberships.append(
                Membership(
                    id=f"MEM-{len(memberships) + 1:04d}",
                    khata_id=khata.id,
                    owner_id=owner_id,
                    share=Fraction(1, count) if wants_shares else None,
                    valid_from=spec.survey_date,
                )
            )

    # -- mouza totals -------------------------------------------------------

    tenure_totals: list[TenureTotal] = []
    if wants_classification:
        by_code: dict[str, int] = {}
        for khesra in khesras:
            if khesra.tenure:
                by_code[khesra.tenure] = by_code.get(khesra.tenure, 0) + node_area[khesra.id]
        tenure_totals = [
            TenureTotal(code=code, area_stated=statement(by_code[code], page=2))
            for code in sorted(by_code)
        ]

    mouza = Mouza(
        id="MZ-SYNTH",
        name=f"SYNTH-MOUZA-{spec.seed:04d}",
        district="SYNTH-DISTRICT",
        subdistrict="SYNTH-CIRCLE",
        subdistrict_term="circle",
        ladder_id=spec.ladder_id,
        area_stated=statement(spec.total_area, page=1) if wants_mouza_total else None,
        tenure_totals=tuple(tenure_totals),
        classification_scheme=spec.scheme_id if wants_classification else None,
        survey_date=spec.survey_date,
        valid_from=spec.survey_date,
    )

    # -- mutation and registration events -----------------------------------

    span = (spec.as_of - spec.survey_date).days
    leaf_ids = sorted(leaf_area)
    mutation_events = [
        Mutation(
            id=f"MUT-{n + 1:04d}",
            mouza_id=mouza.id,
            subject_type=EntityType.KHESRA,
            subject_id=rng.choice(leaf_ids),
            date=spec.survey_date + dt.timedelta(days=rng.randint(1, max(1, span))),
            kind=rng.choice(("sale", "inheritance", "partition")),
            order_ref=f"SYNTH-ORDER-{n + 1:04d}",
            valid_from=spec.survey_date,
        )
        for n in range(spec.mutations)
    ]

    registrations = (
        tuple(
            Registration(
                id=f"REG-{n + 1:04d}",
                mouza_id=mouza.id,
                khesra_id=event.subject_id,
                external_system="SYNTH-REGISTRY",
                reference=f"SYNTH-DEED-{n + 1:04d}",
                date=event.date,
                valid_from=spec.survey_date,
            )
            for n, event in enumerate(mutation_events)
        )
        if spec.profile is DocumentProfile.COMBINED
        else ()
    )

    return RecordSet(
        mouza=mouza,
        kind=SetKind.SNAPSHOT,
        as_of=spec.as_of,
        source=spec.source,
        khesras=tuple(khesras),
        khatas=tuple(khatas),
        owners=tuple(owners),
        memberships=tuple(memberships),
        holdings=tuple(holdings),
        mutations=tuple(mutation_events),
        registrations=registrations,
    )


# --------------------------------------------------------------------------
# independent invariant check
# --------------------------------------------------------------------------


def verify_synthetic_invariants(
    records: RecordSet,
    registry: LadderRegistry | None = None,
    schemes: SchemeRegistry | None = None,
) -> tuple[str, ...]:
    """Re-derive every promised invariant from the finished record set.

    Returns violation descriptions; empty means clean. This is a *constructive*
    check ("did the generator build what it said"), not a diagnostic rule engine.
    Keeping the two implementations separate is what stops the mutation tests from
    being circular.
    """
    registry = registry or default_registry()
    schemes = schemes or default_schemes()
    problems: list[str] = []
    index = records.index(records.as_of)
    ladder_id = records.ladder_id

    def units_of(statement: AreaStatement | None) -> Fraction | None:
        if statement is None:
            return None
        if statement.area.ladder_id != ladder_id:
            problems.append(
                f"area in ladder {statement.area.ladder_id!r}, expected {ladder_id!r}"
            )
            return None
        return statement.area.count

    # -- identity and structure --------------------------------------------

    seen_ids = [k.id for k in records.khesras]
    if len(set(seen_ids)) != len(seen_ids):
        problems.append("duplicate khesra id")
    if index.cyclic_khesra_ids:
        problems.append(f"cyclic khesra parentage: {sorted(index.cyclic_khesra_ids)}")

    for khesra in records.khesras:
        if khesra.mouza_id != records.mouza.id:
            problems.append(f"khesra {khesra.id} belongs to mouza {khesra.mouza_id}")
        if not khesra.local_number.strip():
            problems.append(f"khesra {khesra.id} has a blank local_number")
        elif khesra.local_number.strip() == "0":
            problems.append(f"khesra {khesra.id} is numbered 0")
    for khata in records.khatas:
        if khata.mouza_id != records.mouza.id:
            problems.append(f"khata {khata.id} belongs to mouza {khata.mouza_id}")
        if not khata.number.strip() or khata.number.strip() == "0":
            problems.append(f"khata {khata.id} has number {khata.number!r}")

    # -- sub-division sequences are 1..n, gapless ---------------------------

    for parent_id, children in index.children.items():
        numbers = sorted(child.local_number for child in children)
        expected = sorted(str(n) for n in range(1, len(children) + 1))
        if numbers != expected:
            problems.append(
                f"khesra {parent_id} children numbered {numbers}, expected {expected}"
            )
    roots = [k.local_number for k in index.roots()]
    if len(set(roots)) != len(roots):
        problems.append("duplicate root survey number")

    # -- areas partition exactly -------------------------------------------

    for khesra in records.khesras:
        units = units_of(khesra.area_stated)
        if units is None:
            problems.append(f"khesra {khesra.id} has no stated area")
            continue
        if units <= 0:
            problems.append(f"khesra {khesra.id} has non-positive area {units}")
        children = index.children.get(khesra.id, ())
        if children:
            child_total = sum(
                (units_of(c.area_stated) or Fraction(0) for c in children), Fraction(0)
            )
            if child_total != units:
                problems.append(
                    f"khesra {khesra.id}: children sum to {child_total}, parent states {units}"
                )
        written = khesra.area_stated.as_written
        if written is not None:
            parsed = parse_area(written, ladder_id, registry)
            if parsed.area != khesra.area_stated.area:
                problems.append(
                    f"khesra {khesra.id}: as_written {written!r} parses to "
                    f"{parsed.area.count}, stated {units}"
                )
            if not parsed.is_normalised:
                problems.append(
                    f"khesra {khesra.id}: as_written {written!r} is un-normalised"
                )
        for restatement in khesra.area_restatements:
            converted = convert(khesra.area_stated.area, restatement.area.ladder_id, registry)
            if converted != restatement.area:
                problems.append(
                    f"khesra {khesra.id}: restatement in "
                    f"{restatement.area.ladder_id} disagrees with the primary area"
                )

    leaves = index.leaves()
    leaf_total = sum(
        (units_of(k.area_stated) or Fraction(0) for k in leaves), Fraction(0)
    )
    mouza_units = units_of(records.mouza.area_stated)
    if mouza_units is not None and leaf_total != mouza_units:
        problems.append(
            f"leaf areas sum to {leaf_total}, mouza states {mouza_units}"
        )
    if index.undetermined_leaves():
        problems.append("some khesras have undetermined leaf status")

    # -- holdings ----------------------------------------------------------

    leaf_ids = {k.id for k in leaves}
    for holding in records.holdings:
        if holding.khesra_id not in index.khesra_by_id:
            problems.append(f"holding {holding.id} references missing khesra")
            continue
        if holding.khata_id not in index.khata_by_id:
            problems.append(f"holding {holding.id} references missing khata")
        if holding.khesra_id not in leaf_ids:
            problems.append(
                f"holding {holding.id} attaches to non-leaf khesra {holding.khesra_id}"
            )

    for leaf in leaves:
        attached = index.holdings_by_khesra.get(leaf.id, ())
        if not attached:
            problems.append(f"leaf khesra {leaf.id} is held by no khata")
            continue
        if len({h.khata_id for h in attached}) != len(attached):
            problems.append(f"khesra {leaf.id} is held twice by the same khata")
        shares = [h.share for h in attached if h.share is not None]
        if shares and sum(shares, Fraction(0)) != 1:
            problems.append(
                f"khesra {leaf.id}: holding shares sum to {sum(shares, Fraction(0))}"
            )
        claimed = [units_of(h.area_claimed) for h in attached]
        if all(c is not None for c in claimed):
            total = sum(claimed, Fraction(0))
            if total != units_of(leaf.area_stated):
                problems.append(
                    f"khesra {leaf.id}: claimed areas sum to {total}, "
                    f"parcel states {units_of(leaf.area_stated)}"
                )

    for khata in records.khatas:
        attached = index.holdings_by_khata.get(khata.id, ())
        if not attached:
            problems.append(f"khata {khata.id} holds nothing")
            continue
        stated = units_of(khata.area_stated)
        computed_parts = [units_of(h.area_claimed) for h in attached]
        if stated is not None and all(part is not None for part in computed_parts):
            computed = sum(computed_parts, Fraction(0))
            if computed != stated:
                problems.append(
                    f"khata {khata.id}: holdings sum to {computed}, states {stated}"
                )

    khata_totals = [units_of(k.area_stated) for k in records.khatas]
    if mouza_units is not None and all(t is not None for t in khata_totals):
        grand = sum(khata_totals, Fraction(0))
        if grand != mouza_units:
            problems.append(
                f"khata totals sum to {grand}, mouza states {mouza_units} "
                "(the trial balance)"
            )

    # -- memberships and owners --------------------------------------------

    for khata in records.khatas:
        members = index.memberships_by_khata.get(khata.id, ())
        if not members:
            problems.append(f"khata {khata.id} has no owner")
            continue
        shares = [m.share for m in members if m.share is not None]
        if shares and sum(shares, Fraction(0)) != 1:
            problems.append(
                f"khata {khata.id}: owner shares sum to {sum(shares, Fraction(0))}"
            )
    for owner in records.owners:
        held = index.memberships_by_owner.get(owner.id, ())
        if len({m.khata_id for m in held}) > 1:
            problems.append(f"owner {owner.id} appears in more than one khata")
        if not held:
            problems.append(f"owner {owner.id} belongs to no khata")

    # -- classification -----------------------------------------------------

    if records.mouza.tenure_totals:
        scheme = schemes.get(records.mouza.classification_scheme or "")
        by_code: dict[str, Fraction] = {}
        for khesra in records.khesras:
            if khesra.tenure:
                scheme.tenure_class(khesra.tenure)
                by_code[khesra.tenure] = by_code.get(khesra.tenure, Fraction(0)) + (
                    units_of(khesra.area_stated) or Fraction(0)
                )
        for total in records.mouza.tenure_totals:
            stated = units_of(total.area_stated)
            actual = by_code.get(total.code, Fraction(0))
            if stated != actual:
                problems.append(
                    f"tenure {total.code}: parcels sum to {actual}, mouza states {stated}"
                )
        if mouza_units is not None:
            grand = sum(by_code.values(), Fraction(0))
            if grand != mouza_units:
                problems.append(
                    f"classified areas sum to {grand}, mouza states {mouza_units}"
                )

    # -- chronology ---------------------------------------------------------

    survey = records.mouza.survey_date
    if survey is not None:
        for event in records.mutations:
            if event.date is not None and event.date < survey:
                problems.append(
                    f"mutation {event.id} dated {event.date}, before survey {survey}"
                )

    return tuple(problems)
