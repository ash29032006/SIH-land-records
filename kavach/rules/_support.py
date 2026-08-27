"""Shared helpers for rule authors. No rule logic lives here.

Subject builders exist so that findings localise consistently — HANDOFF_BUILD.md
5.2 measures whether the engine names the right *parcel*, and a rule that hand-rolls
its own subject will eventually name the village instead.
"""

from __future__ import annotations

from fractions import Fraction

from kavach.findings import Subject
from kavach.records import AreaStatement, EntityType, Index
from kavach.units import Area, LadderRegistry, format_area

__all__ = [
    "area_text",
    "holding_subject",
    "khata_subject",
    "khesra_subject",
    "membership_subject",
    "mouza_subject",
    "owner_subject",
    "undated_abstention",
    "units_of",
]


def khesra_subject(khesra, index: Index | None = None, field: str | None = None) -> Subject:
    display = index.display_path(khesra.id) if index else None
    return Subject(EntityType.KHESRA, khesra.id, field, display or khesra.local_number)


def khata_subject(khata, field: str | None = None) -> Subject:
    return Subject(EntityType.KHATA, khata.id, field, f"khata {khata.number}")


def mouza_subject(mouza, field: str | None = None) -> Subject:
    return Subject(EntityType.MOUZA, mouza.id, field, mouza.name)


def owner_subject(owner, field: str | None = None) -> Subject:
    return Subject(EntityType.OWNER, owner.id, field, owner.name_raw)


def holding_subject(holding, field: str | None = None) -> Subject:
    return Subject(
        EntityType.HOLDING, holding.id, field,
        f"{holding.khata_id} in {holding.khesra_id}",
    )


def membership_subject(membership, field: str | None = None) -> Subject:
    return Subject(
        EntityType.MEMBERSHIP, membership.id, field,
        f"{membership.owner_id} in {membership.khata_id}",
    )


def units_of(statement: AreaStatement | None) -> Fraction | None:
    """The exact count, or None when nothing was stated. Never a default of zero."""
    return None if statement is None else statement.area.count


def area_text(area: Area, registry: LadderRegistry) -> str:
    return format_area(area, registry)


def undated_abstention(report, view, kind: str, undated):
    """One abstention when records of unknown validity exist.

    Ruling 2 made real: a WITHIN_VERSION rule may not silently include or drop
    records it cannot date. It says so instead.
    """
    if not undated:
        return None
    return report.abstain(
        mouza_subject(view.records.mouza),
        f"{len(undated)} {kind} could not be dated, so this rule could not be "
        f"evaluated over the whole record set at {view.as_of}",
        missing_witness="validity dates",
        evidence={"undated": ", ".join(sorted(r.id for r in undated)[:10])},
    )
