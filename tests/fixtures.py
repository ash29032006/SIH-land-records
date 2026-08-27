"""Tiny hand-built record sets for per-rule fixtures. Not collected by pytest.

AGENTS.md 4.2 requires three fixtures per rule: one that violates it, one that
passes it, and one where the witness is missing. These builders keep each of those
down to a few lines so the third one never gets skipped for being tedious.
"""

from __future__ import annotations

import datetime as dt
from fractions import Fraction

from kavach.findings import SingleVersionView
from kavach.records import (
    AreaStatement,
    Holding,
    Khata,
    Khesra,
    Membership,
    Mouza,
    Owner,
    Provenance,
    RecordSet,
    SetKind,
    TenureTotal,
)
from kavach.units import Area, default_registry

REG = default_registry()
LADDER = "bihar.jamabandi"
TODAY = dt.date(2026, 1, 1)
SURVEY = dt.date(1900, 1, 1)

__all__ = [
    "LADDER", "REG", "SURVEY", "TODAY",
    "area", "holding", "khata", "khesra", "membership", "mouza", "owner",
    "records", "run", "stated", "view",
]


def area(units) -> Area:
    return Area(LADDER, Fraction(units))


def stated(units, as_written: str | None = "auto", ladder: str = LADDER) -> AreaStatement:
    value = Area(ladder, Fraction(units))
    if as_written == "auto":
        from kavach.units import format_area

        as_written = format_area(value, REG)
    return AreaStatement(
        area=value,
        as_written=as_written,
        provenance=Provenance(document_id="FIX-DOC", page=1),
    )


def mouza(**kw) -> Mouza:
    base = dict(
        id="MZ", name="FIX-MOUZA", district="FIX-DISTRICT", ladder_id=LADDER,
        survey_date=SURVEY, valid_from=SURVEY,
    )
    base.update(kw)
    return Mouza(**base)


def khesra(khesra_id: str, local_number: str = "1", **kw) -> Khesra:
    base = dict(id=khesra_id, mouza_id="MZ", local_number=local_number, valid_from=SURVEY)
    base.update(kw)
    return Khesra(**base)


def khata(khata_id: str, number: str = "2001", **kw) -> Khata:
    base = dict(id=khata_id, mouza_id="MZ", number=number, valid_from=SURVEY)
    base.update(kw)
    return Khata(**base)


def owner(owner_id: str, name: str = "FIX-OWNER", **kw) -> Owner:
    base = dict(id=owner_id, name_raw=name, valid_from=SURVEY)
    base.update(kw)
    return Owner(**base)


def holding(holding_id: str, khata_id: str, khesra_id: str, **kw) -> Holding:
    base = dict(id=holding_id, khata_id=khata_id, khesra_id=khesra_id, valid_from=SURVEY)
    base.update(kw)
    return Holding(**base)


def membership(membership_id: str, khata_id: str, owner_id: str, **kw) -> Membership:
    base = dict(id=membership_id, khata_id=khata_id, owner_id=owner_id, valid_from=SURVEY)
    base.update(kw)
    return Membership(**base)


def records(*, undated: bool = False, **kw) -> RecordSet:
    """A record set. `undated=True` makes it MULTI_VERSION so undated rows are UNKNOWN."""
    base = dict(
        mouza=kw.pop("mouza", mouza()),
        kind=SetKind.MULTI_VERSION if undated else SetKind.SNAPSHOT,
        as_of=None if undated else TODAY,
        source="fixture",
    )
    base.update(kw)
    if undated:
        base["as_of"] = None
    return RecordSet(**base)


def view(record_set: RecordSet, as_of: dt.date | None = TODAY) -> SingleVersionView:
    return SingleVersionView.of(record_set, REG, as_of)


def run(rule, record_set: RecordSet, as_of: dt.date | None = TODAY):
    return list(rule(view(record_set, as_of)))
