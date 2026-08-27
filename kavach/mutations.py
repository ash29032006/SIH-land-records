"""Mutation engine — one known corruption at a time, with its expected finding.

HANDOFF_BUILD.md 5.2. Each mutation is a named, reproducible, pure transformation of
a clean synthetic mouza. Because the corruption is known exactly, precision, recall
and *localisation* can be measured with no labelled data and no annotator — which is
the same claim the pitch makes about rules generating their own ground truth.

Three places where building this contradicted the spec table, all deliberate:

1. **Deleting a sequence member breaks two invariants, not one.** The area goes with
   the record, so the parent no longer sums. `sequence_member_deleted` therefore
   expects both a Class 3 and a Class 2 finding. `sequence_gap_renumbered` is the
   isolated single-corruption version.

2. **"Duplicate khata per owner" is not an error in Bihar.** Textual partition gives
   each heir their own jamabandi on the same survey number (EVIDENCE.md E1, E3), so
   one person legitimately holds several khatas. The real corruption is *the same
   holding recorded twice*, which is what `khata_duplicated` does.

3. **Flipping a parcel's tenure is arithmetically invisible** unless the mouza states
   its per-tenure subtotals separately — the partition still sums either way. That is
   why `Mouza.tenure_totals` exists.

Removing a witness is in here too, and it is the one mutation that must break *no*
invariant. That is the point: absence of a witness is not an error, and only a witness
census can see it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Mapping, Sequence

from kavach.findings import EngineResult, FindingClass
from kavach.records import AreaStatement, EntityType, RecordSet
from kavach.synthetic import (
    DocumentProfile,
    MouzaSpec,
    synthetic_mouza,
    verify_synthetic_invariants,
)
from kavach.units import Area, LadderRegistry, default_registry, format_area

__all__ = [
    "CaseScore",
    "ExpectedFinding",
    "MUTATIONS",
    "MutationCase",
    "MutationScore",
    "Mutator",
    "UnknownMutation",
    "all_mutation_cases",
    "apply_mutation",
    "score_case",
    "summarise",
]


class UnknownMutation(Exception):
    pass


class MutationNotApplicable(Exception):
    """This clean mouza does not contain the shape this mutation needs."""


@dataclass(frozen=True)
class ExpectedFinding:
    """What the engine ought to say once the corruption is applied."""

    validation_class: int
    finding_class: FindingClass
    entity_type: EntityType
    entity_id: str
    note: str = ""


@dataclass(frozen=True)
class MutationCase:
    name: str
    description: str
    grounding: str
    clean: RecordSet
    mutated: RecordSet
    expected: tuple[ExpectedFinding, ...]
    broken_invariants: tuple[str, ...]
    breaks_invariants: bool = True

    @property
    def expected_entity_ids(self) -> frozenset[str]:
        return frozenset(e.entity_id for e in self.expected)

    @property
    def expected_classes(self) -> frozenset[int]:
        return frozenset(e.validation_class for e in self.expected)


Apply = Callable[[RecordSet, random.Random, LadderRegistry], tuple[RecordSet, tuple[ExpectedFinding, ...]]]


@dataclass(frozen=True)
class Mutator:
    name: str
    description: str
    grounding: str
    apply: Apply
    breaks_invariants: bool = True
    needs_classification: bool = False
    needs_claimed_areas: bool = False


# --------------------------------------------------------------------------
# small pure helpers
# --------------------------------------------------------------------------


def _replace(items: Sequence, entity_id: str, updater) -> tuple:
    return tuple(updater(item) if item.id == entity_id else item for item in items)


def _drop(items: Sequence, entity_ids: frozenset[str]) -> tuple:
    return tuple(item for item in items if item.id not in entity_ids)


def _restate(statement: AreaStatement, units: Fraction, registry: LadderRegistry) -> AreaStatement:
    """Move an area statement to a new value, keeping `as_written` consistent.

    Keeping the written form in step matters: a mutation that changed the value and
    left the string stale would corrupt two things at once and stop isolating the
    finding under test.
    """
    area = Area(statement.area.ladder_id, units)
    return statement.model_copy(
        update={"area": area, "as_written": format_area(area, registry)}
    )


def _pick(rng: random.Random, items: Sequence, what: str):
    if not items:
        raise MutationNotApplicable(f"clean mouza contains no {what}")
    return rng.choice(list(items))


# --------------------------------------------------------------------------
# the mutations
# --------------------------------------------------------------------------


def _subdivision_numbered_zero(clean, rng, registry):
    children = [k for k in clean.khesras if k.parent_khesra_id is not None]
    target = _pick(rng, children, "sub-divided khesra")
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id, lambda k: k.model_copy(update={"local_number": "0"})
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "sub-division numbering starts at 1, never 0"),
    )


def _khesra_number_blank(clean, rng, registry):
    target = _pick(rng, clean.khesras, "khesra")
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id, lambda k: k.model_copy(update={"local_number": ""})
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "blank khesra number"),
    )


def _khata_number_zero(clean, rng, registry):
    target = _pick(rng, clean.khatas, "khata")
    mutated = clean.model_copy(
        update={
            "khatas": _replace(
                clean.khatas, target.id, lambda k: k.model_copy(update={"number": "0"})
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHATA, target.id,
                        "khata number recorded as 0"),
    )


def _one_unit_added_to_parcel(clean, rng, registry):
    index = clean.index(clean.as_of)
    target = _pick(rng, index.leaves(), "leaf khesra")
    if target.area_stated is None:
        raise MutationNotApplicable("leaf has no stated area")
    inflated = _restate(target.area_stated, target.area_stated.area.count + 1, registry)
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id, lambda k: k.model_copy(
                    update={"area_stated": inflated, "area_restatements": ()}
                )
            )
        }
    )
    expected = [
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "parcel area no longer reconciles"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.MOUZA, clean.mouza.id,
                        "trial balance off by one smallest unit"),
    ]
    if target.parent_khesra_id:
        expected.append(
            ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA,
                            target.parent_khesra_id, "children no longer sum to parent")
        )
    return mutated, tuple(expected)


def _one_unit_added_to_holding(clean, rng, registry):
    with_areas = [h for h in clean.holdings if h.area_claimed is not None]
    target = _pick(rng, with_areas, "holding with a claimed area")
    inflated = _restate(target.area_claimed, target.area_claimed.area.count + 1, registry)
    mutated = clean.model_copy(
        update={
            "holdings": _replace(
                clean.holdings, target.id,
                lambda h: h.model_copy(update={"area_claimed": inflated}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHATA, target.khata_id,
                        "khata holdings no longer sum to its stated total"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.khesra_id,
                        "claimed areas exceed the parcel"),
    )


def _sequence_gap_renumbered(clean, rng, registry):
    index = clean.index(clean.as_of)
    families = [
        (parent_id, kids) for parent_id, kids in index.children.items() if len(kids) >= 2
    ]
    if not families:
        raise MutationNotApplicable("no sub-divided khesra with siblings")
    parent_id, kids = _pick(rng, families, "sibling group")
    highest = max(kids, key=lambda k: int(k.local_number))
    gap_number = str(int(highest.local_number) + 1)
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, highest.id,
                lambda k: k.model_copy(update={"local_number": gap_number}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, parent_id,
                        f"sub-division sequence skips {highest.local_number}"),
    )


def _sequence_member_deleted(clean, rng, registry):
    index = clean.index(clean.as_of)
    families = [
        (parent_id, kids) for parent_id, kids in index.children.items() if len(kids) >= 2
    ]
    if not families:
        raise MutationNotApplicable("no sub-divided khesra with siblings")
    parent_id, kids = _pick(rng, families, "sibling group")
    victim = min(kids, key=lambda k: int(k.local_number))

    doomed = {victim.id}
    frontier = [victim.id]
    while frontier:
        current = frontier.pop()
        for child in index.children.get(current, ()):
            doomed.add(child.id)
            frontier.append(child.id)

    mutated = clean.model_copy(
        update={
            "khesras": _drop(clean.khesras, frozenset(doomed)),
            "holdings": tuple(h for h in clean.holdings if h.khesra_id not in doomed),
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, parent_id,
                        "sub-division sequence has a hole"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, parent_id,
                        "children no longer sum to parent — deletion takes the area with it"),
    )


def _khata_duplicated(clean, rng, registry):
    index = clean.index(clean.as_of)
    source = _pick(rng, clean.khatas, "khata")
    copy_id = f"{source.id}-DUP"
    duplicate = source.model_copy(update={"id": copy_id})
    copied_memberships = tuple(
        m.model_copy(update={"id": f"{m.id}-DUP", "khata_id": copy_id})
        for m in index.memberships_by_khata.get(source.id, ())
    )
    copied_holdings = tuple(
        h.model_copy(update={"id": f"{h.id}-DUP", "khata_id": copy_id})
        for h in index.holdings_by_khata.get(source.id, ())
    )
    mutated = clean.model_copy(
        update={
            "khatas": clean.khatas + (duplicate,),
            "memberships": clean.memberships + copied_memberships,
            "holdings": clean.holdings + copied_holdings,
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHATA, copy_id,
                        "the same holding recorded twice under a second khata"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.MOUZA, clean.mouza.id,
                        "khata totals now exceed the mouza total"),
    )


def _tenure_flipped(clean, rng, registry):
    classified = [k for k in clean.khesras if k.tenure]
    if not clean.mouza.tenure_totals:
        raise MutationNotApplicable(
            "mouza states no per-tenure subtotals, so a flip is arithmetically invisible"
        )
    target = _pick(rng, classified, "classified khesra")
    others = [t.code for t in clean.mouza.tenure_totals if t.code != target.tenure]
    if not others:
        raise MutationNotApplicable("only one tenure class present")
    flipped = rng.choice(others)
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(update={"tenure": flipped}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.MOUZA, clean.mouza.id,
                        f"tenure subtotals no longer reconcile ({target.tenure} -> {flipped})"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "this parcel's classification changed"),
    )


def _written_area_unnormalised(clean, rng, registry):
    ladder = registry.get(clean.ladder_id)
    base = ladder.base_above(ladder.smallest)
    if base is None:
        raise MutationNotApplicable("single-unit ladder cannot carry")
    index = clean.index(clean.as_of)
    candidates = [
        k for k in index.leaves()
        if k.area_stated is not None and k.area_stated.area.count >= base
    ]
    target = _pick(rng, candidates, "parcel large enough to carry")
    count = target.area_stated.area.count
    # Same value, written without carrying: "143 decimal" instead of "1 acre 43 decimal".
    unnormalised = f"{count.numerator} {ladder.smallest}" if count.denominator == 1 else None
    if unnormalised is None:
        raise MutationNotApplicable("parcel area is not a whole number of smallest units")
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(
                    update={
                        "area_stated": k.area_stated.model_copy(
                            update={"as_written": unnormalised}
                        )
                    }
                ),
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        f"{unnormalised!r} should have carried into {ladder.units[-2]}"),
    )


def _holding_orphaned(clean, rng, registry):
    target = _pick(rng, clean.holdings, "holding")
    mutated = clean.model_copy(
        update={
            "holdings": _replace(
                clean.holdings, target.id,
                lambda h: h.model_copy(update={"khesra_id": "KHS-MISSING"}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.HOLDING, target.id,
                        "holding points at a khesra that does not exist"),
    )


def _witness_removed(clean, rng, registry):
    if clean.mouza.area_stated is None:
        raise MutationNotApplicable("mouza already states no total")
    mutated = clean.model_copy(
        update={
            "mouza": clean.mouza.model_copy(
                update={"area_stated": None, "tenure_totals": ()}
            )
        }
    )
    return mutated, (
        ExpectedFinding(8, FindingClass.UNVERIFIABLE, EntityType.MOUZA, clean.mouza.id,
                        "no stated mouza total: the trial balance cannot run at all"),
    )


def _identifier_charset_corrupted(clean, rng, registry):
    """A digit misread as a letter — the classic transcription slip."""
    candidates = [k for k in clean.khesras if "1" in k.local_number]
    target = _pick(rng, candidates, "parcel numbered with a 1")
    corrupted = target.local_number.replace("1", "l", 1)
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(update={"local_number": corrupted}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        f"{corrupted!r} read for {target.local_number!r}"),
    )


def _written_area_disagrees(clean, rng, registry):
    """The written string says one thing and the stored value another."""
    index = clean.index(clean.as_of)
    candidates = [
        k for k in index.leaves()
        if k.area_stated is not None and k.area_stated.as_written
    ]
    target = _pick(rng, candidates, "parcel with a written area")
    inflated = Area(
        target.area_stated.area.ladder_id, target.area_stated.area.count + 1
    )
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(
                    update={
                        "area_stated": k.area_stated.model_copy(
                            update={"as_written": format_area(inflated, registry)}
                        )
                    }
                ),
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "written form no longer matches the stored value"),
    )


def _mutation_predates_survey(clean, rng, registry):
    """A mutation dated before the survey that created the record."""
    if not clean.mutations or clean.mouza.survey_date is None:
        raise MutationNotApplicable("no dated mutations to move")
    target = _pick(rng, clean.mutations, "mutation")
    impossible = clean.mouza.survey_date.replace(
        year=clean.mouza.survey_date.year - 1
    )
    mutated = clean.model_copy(
        update={
            "mutations": _replace(
                clean.mutations, target.id,
                lambda m: m.model_copy(update={"date": impossible}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(1, FindingClass.CERTAIN_ERROR, EntityType.MUTATION, target.id,
                        "impossible chronology"),
    )


def _parcel_moved_to_another_mouza(clean, rng, registry):
    """A parcel of another village left inside this jamabandi."""
    target = _pick(rng, clean.khesras, "khesra")
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(update={"mouza_id": "MZ-ELSEWHERE"}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "parcel belongs to a different mouza"),
    )


def _holding_recorded_twice(clean, rng, registry):
    """The same khata recorded as holding the same parcel twice."""
    target = _pick(rng, clean.holdings, "holding")
    duplicate = target.model_copy(update={"id": f"{target.id}-TWICE"})
    mutated = clean.model_copy(update={"holdings": clean.holdings + (duplicate,)})
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.HOLDING, duplicate.id,
                        "the same holding written down twice"),
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA,
                        target.khesra_id, "parcel is now over-claimed"),
    )


def _khata_number_duplicated(clean, rng, registry):
    """Two khatas carrying the same number in one mouza."""
    if len(clean.khatas) < 2:
        raise MutationNotApplicable("need two khatas")
    first, second = clean.khatas[0], clean.khatas[1]
    mutated = clean.model_copy(
        update={
            "khatas": _replace(
                clean.khatas, second.id,
                lambda k: k.model_copy(update={"number": first.number}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHATA, second.id,
                        "khata number is not unique in the mouza"),
    )


def _co_owner_share_inflated(clean, rng, registry):
    """One co-owner's share raised so the khata's shares exceed one."""
    with_shares = [m for m in clean.memberships if m.share is not None]
    target = _pick(rng, with_shares, "membership with a share")
    mutated = clean.model_copy(
        update={
            "memberships": _replace(
                clean.memberships, target.id,
                lambda m: m.model_copy(update={"share": m.share + Fraction(1, 10)}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHATA, target.khata_id,
                        "co-owner shares no longer sum to one"),
    )


def _restated_area_corrupted(clean, rng, registry):
    """The hectare column of the rakba field disagrees with the acre column."""
    candidates = [k for k in clean.khesras if k.area_restatements]
    target = _pick(rng, candidates, "parcel restating its area")
    first = target.area_restatements[0]
    bumped = first.model_copy(
        update={"area": Area(first.area.ladder_id, first.area.count + 1)}
    )
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(
                    update={"area_restatements": (bumped,) + k.area_restatements[1:]}
                ),
            )
        }
    )
    return mutated, (
        ExpectedFinding(2, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, target.id,
                        "the same area stated in two unit systems disagrees"),
    )


def _parcel_area_removed(clean, rng, registry):
    """A parcel's area blanked. Not an error — it makes conservation unverifiable."""
    index = clean.index(clean.as_of)
    target = _pick(rng, index.leaves(), "leaf khesra")
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, target.id,
                lambda k: k.model_copy(
                    update={"area_stated": None, "area_restatements": ()}
                ),
            )
        }
    )
    return mutated, (
        ExpectedFinding(8, FindingClass.UNVERIFIABLE, EntityType.MOUZA, clean.mouza.id,
                        "a parcel states no area, so the trial balance cannot run"),
    )


def _parentage_loop_introduced(clean, rng, registry):
    """A parcel made its own ancestor, so paths and leaf status become undefined."""
    index = clean.index(clean.as_of)
    families = [
        (parent_id, kids) for parent_id, kids in index.children.items() if kids
    ]
    if not families:
        raise MutationNotApplicable("no sub-divided khesra")
    parent_id, kids = _pick(rng, families, "sibling group")
    child = kids[0]
    mutated = clean.model_copy(
        update={
            "khesras": _replace(
                clean.khesras, parent_id,
                lambda k: k.model_copy(update={"parent_khesra_id": child.id}),
            )
        }
    )
    return mutated, (
        ExpectedFinding(3, FindingClass.CERTAIN_ERROR, EntityType.KHESRA, parent_id,
                        "parcel parentage now contains a loop"),
    )


MUTATIONS: Mapping[str, Mutator] = {
    m.name: m
    for m in (
        Mutator("subdivision_numbered_zero",
                "Set one sub-division's number to 0.",
                "HANDOFF_BUILD.md 5.2; EVIDENCE.md E5 records '0' entries as a measured "
                "error class in roughly 6% of Bihar RoRs.",
                _subdivision_numbered_zero),
        Mutator("khesra_number_blank",
                "Blank one khesra number.",
                "EVIDENCE.md E5: missing khata and khesra numbers, measured.",
                _khesra_number_blank),
        Mutator("khata_number_zero",
                "Record a khata number as 0.",
                "EVIDENCE.md E5: khata number mentioned as zero/blank.",
                _khata_number_zero),
        Mutator("one_unit_added_to_parcel",
                "Add one smallest unit to a single parcel, written form kept in step.",
                "HANDOFF_BUILD.md 5.2 'add 1 dhur to one plot'.",
                _one_unit_added_to_parcel),
        Mutator("one_unit_added_to_holding",
                "Add one smallest unit to a single holding's claimed area.",
                "HANDOFF_BUILD.md 5.2, localised to the khata as the table specifies.",
                _one_unit_added_to_holding, needs_claimed_areas=True),
        Mutator("sequence_gap_renumbered",
                "Renumber the highest sibling so the sequence skips a number.",
                "HANDOFF_BUILD.md 4 Class 3. Isolated: conservation is untouched.",
                _sequence_gap_renumbered),
        Mutator("sequence_member_deleted",
                "Delete a sub-division and its descendants outright.",
                "HANDOFF_BUILD.md 5.2 'delete a sequence member'. Breaks TWO invariants, "
                "because the area leaves with the record.",
                _sequence_member_deleted),
        Mutator("khata_duplicated",
                "Duplicate a khata with its memberships and holdings.",
                "HANDOFF_BUILD.md 5.2, restated: an owner holding several khatas is normal "
                "in Bihar (EVIDENCE.md E1/E3), so the corruption is a duplicated holding.",
                _khata_duplicated),
        Mutator("tenure_flipped",
                "Flip one parcel's tenure class.",
                "HANDOFF_BUILD.md 5.2. Only detectable because the mouza states per-tenure "
                "subtotals separately.",
                _tenure_flipped, needs_classification=True),
        Mutator("written_area_unnormalised",
                "Write a parcel's area without carrying into the unit above.",
                "HANDOFF_BUILD.md 4 Class 1 'unit carry'; HANDOFF_BUILD.md 3.5 '27 katha'.",
                _written_area_unnormalised),
        Mutator("holding_orphaned",
                "Point a holding at a khesra that does not exist.",
                "HANDOFF_BUILD.md 4 Class 3 'no orphan khesra'.",
                _holding_orphaned),
        Mutator("identifier_charset_corrupted",
                "Misread a digit as a letter in a parcel number.",
                "HANDOFF_BUILD.md 4 Class 1 charset: '2l7' read for '217'.",
                _identifier_charset_corrupted),
        Mutator("written_area_disagrees",
                "Change the written area string without changing the stored value.",
                "HANDOFF_BUILD.md 3.5 and EVIDENCE.md E5: area entries are a measured "
                "error class.",
                _written_area_disagrees),
        Mutator("mutation_predates_survey",
                "Date a mutation before the survey that created the record.",
                "HANDOFF_BUILD.md 4 Class 1 date ordering.",
                _mutation_predates_survey),
        Mutator("parcel_moved_to_another_mouza",
                "Leave a parcel of another village inside this jamabandi.",
                "EVIDENCE.md E11: Bihar's Parimarjan portal lists correction of "
                "'Jamabandi with khesra of multiple mauja' as something citizens apply "
                "for, so this is a documented real state.",
                _parcel_moved_to_another_mouza),
        Mutator("holding_recorded_twice",
                "Write the same holding down twice.",
                "HANDOFF_BUILD.md 5.2, restated. See EVIDENCE.md E1 for why the "
                "spec's 'duplicate khata per owner' is not the corruption.",
                _holding_recorded_twice),
        Mutator("khata_number_duplicated",
                "Give two khatas the same number.",
                "HANDOFF_BUILD.md 4 Class 3 uniqueness.",
                _khata_number_duplicated),
        Mutator("co_owner_share_inflated",
                "Raise one co-owner's share so the khata exceeds one.",
                "HANDOFF_BUILD.md 4 Class 2: co-owner shares sum to exactly 1.",
                _co_owner_share_inflated, needs_classification=False),
        Mutator("restated_area_corrupted",
                "Make the hectare column disagree with the acre column.",
                "EVIDENCE.md E10: rakba is recorded three times in three unit systems, "
                "which makes the row its own second witness.",
                _restated_area_corrupted),
        Mutator("parcel_area_removed",
                "Blank one parcel's area.",
                "EVIDENCE.md E5: area mentioned as zero or blank is measured at scale. "
                "Like witness_removed, this is an absence rather than an error.",
                _parcel_area_removed, breaks_invariants=True),
        Mutator("parentage_loop_introduced",
                "Make a parcel its own ancestor.",
                "HANDOFF_BUILD.md 4 Class 3. A loop makes paths and leaf status "
                "undefined, so it must surface before anything depending on them.",
                _parentage_loop_introduced),
        Mutator("witness_removed",
                "Remove the stated mouza total.",
                "HANDOFF_BUILD.md 5.2 last row. The one mutation that must break NO "
                "invariant: absence of a witness is not an error.",
                _witness_removed, breaks_invariants=False),
    )
}


def apply_mutation(
    name: str,
    clean: RecordSet,
    registry: LadderRegistry | None = None,
    *,
    seed: int = 0,
) -> MutationCase:
    """Apply one named corruption. Deterministic for a given clean set and seed."""
    registry = registry or default_registry()
    try:
        mutator = MUTATIONS[name]
    except KeyError:
        raise UnknownMutation(
            f"no mutation {name!r} (known: {', '.join(sorted(MUTATIONS))})"
        ) from None
    rng = random.Random(_stable_seed(name, seed))
    mutated, expected = mutator.apply(clean, rng, registry)
    return MutationCase(
        name=mutator.name,
        description=mutator.description,
        grounding=mutator.grounding,
        clean=clean,
        mutated=mutated,
        expected=expected,
        broken_invariants=verify_synthetic_invariants(mutated, registry),
        breaks_invariants=mutator.breaks_invariants,
    )


def _stable_seed(name: str, seed: int) -> int:
    """Reproducible across processes, unlike hash()."""
    total = seed
    for position, character in enumerate(name):
        total = (total * 131 + ord(character) + position) % 2_147_483_647
    return total


def all_mutation_cases(
    clean: RecordSet,
    registry: LadderRegistry | None = None,
    *,
    seed: int = 0,
) -> tuple[MutationCase, ...]:
    """Every mutation this clean mouza can support. Skips ones it cannot."""
    registry = registry or default_registry()
    cases: list[MutationCase] = []
    for name in MUTATIONS:
        try:
            cases.append(apply_mutation(name, clean, registry, seed=seed))
        except MutationNotApplicable:
            continue
    return tuple(cases)


# --------------------------------------------------------------------------
# scoring — precision, recall, localisation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CaseScore:
    case_name: str
    detected: bool
    localised: bool
    matching_findings: int
    certain_errors: int
    collateral: int
    """CERTAIN_ERRORs that do not name a directly-corrupted entity.

    These are **not** false positives. The clean record set holds every invariant
    by construction, so a certain error on a mutated set is caused by the injected
    corruption — a duplicated khata really does make several parcels over-claimed,
    and reporting those is correct. Collateral measures how far one corruption
    propagates, which is a reviewer-load signal, not an error rate."""


def score_case(case: MutationCase, result: EngineResult) -> CaseScore:
    """Did the engine find *this* corruption, on *this* record?

    `detected` means a finding of the right validation class and finding class
    exists. `localised` additionally requires it to name one of the entities the
    mutation actually touched — HANDOFF_BUILD.md 5.2's "right parcel, not merely the
    right village".
    """
    wanted = {(e.validation_class, e.finding_class) for e in case.expected}
    targets = case.expected_entity_ids

    matching = [
        f for f in result.findings if (f.validation_class, f.finding_class) in wanted
    ]
    localised = [
        f for f in matching if any(s.entity_id in targets for s in f.subjects)
    ]
    collateral = [
        f
        for f in result.certain_errors
        if not any(s.entity_id in targets for s in f.subjects)
    ]
    return CaseScore(
        case_name=case.name,
        detected=bool(matching),
        localised=bool(localised),
        matching_findings=len(matching),
        certain_errors=len(result.certain_errors),
        collateral=len(collateral),
    )


@dataclass(frozen=True)
class MutationScore:
    """Measured, never asserted. Whatever the numbers are, they are printed."""

    scores: tuple[CaseScore, ...]
    clean_certain_errors: int
    rules_run: int = 0
    """How many distinct rules actually executed. Zero makes every rate None:
    a rule that never ran did not score zero, it did not score."""

    @property
    def total(self) -> int:
        return len(self.scores)

    @property
    def detected(self) -> int:
        return sum(1 for s in self.scores if s.detected)

    @property
    def localised(self) -> int:
        return sum(1 for s in self.scores if s.localised)

    @property
    def collateral(self) -> int:
        """Findings downstream of a corruption. Consequences, not errors."""
        return sum(s.collateral for s in self.scores)

    @property
    def true_positives(self) -> int:
        """Every certain error raised on a mutated set.

        The clean set holds every invariant by construction and the harness asserts
        the engine finds nothing wrong with it, so each of these is caused by the
        injected corruption."""
        return sum(s.certain_errors for s in self.scores)

    @property
    def recall(self) -> Fraction | None:
        if not self.rules_run or not self.total:
            return None
        return Fraction(self.detected, self.total)

    @property
    def localisation_rate(self) -> Fraction | None:
        if not self.rules_run or not self.detected:
            return None
        return Fraction(self.localised, self.detected)

    @property
    def precision(self) -> Fraction | None:
        """True positives over true positives plus false positives.

        The only observable false positives are certain errors raised on **clean**
        input, because that is the only record set known to contain no defect. A
        certain error on a mutated set is a consequence of the corruption, however
        far from the mutation site it lands."""
        if not self.rules_run:
            return None
        denominator = self.true_positives + self.clean_certain_errors
        return Fraction(self.true_positives, denominator) if denominator else None

    @property
    def propagation(self) -> Fraction | None:
        """Certain errors raised per corruption. Reviewer load, not an error rate."""
        if not self.total:
            return None
        return Fraction(self.true_positives, self.total)

    def report(self) -> str:
        lines = [
            "mutation harness — measured, not asserted",
            f"  cases run              {self.total}",
            f"  detected               {self.detected}",
            f"  localised              {self.localised}",
            f"  true positives         {self.true_positives}",
            f"  collateral findings    {self.collateral}  (downstream of a corruption)",
            f"  FALSE POSITIVES, clean {self.clean_certain_errors}",
            f"  rules that ran         {self.rules_run}",
        ]
        for label, value in (
            ("recall", self.recall),
            ("localisation", self.localisation_rate),
            ("precision", self.precision),
        ):
            if value is None:
                reason = (
                    "no rule ran" if not self.rules_run else "nothing to measure yet"
                )
                lines.append(f"  {label:22} None ({reason})")
            else:
                percent = (100 * value.numerator) // value.denominator
                lines.append(f"  {label:22} {value} (~{percent}%)")
        spread = self.propagation
        if spread is None:
            lines.append(f"  {'propagation':22} None (no cases)")
        else:
            whole = spread.numerator // spread.denominator
            lines.append(
                f"  {'propagation':22} {spread} "
                f"(~{whole} findings per corruption — reviewer load, not error)"
            )
        return "\n".join(lines)


def summarise(
    cases: Sequence[MutationCase],
    results: Sequence[EngineResult],
    clean_result: EngineResult,
) -> MutationScore:
    if len(cases) != len(results):
        raise ValueError("each case needs exactly one engine result")
    ran = {name for result in results for name in result.rules_run}
    ran.update(clean_result.rules_run)
    return MutationScore(
        scores=tuple(score_case(c, r) for c, r in zip(cases, results)),
        clean_certain_errors=len(clean_result.certain_errors),
        rules_run=len(ran),
    )
