"""Class 1 — Grammar. The field is its own witness, so a violation is certain.

These are the cheapest checks in the system: no second document, no OCR, no portal,
no model. They run on tabular records as they stand.

Every rule here abstains over records it cannot date, rather than silently including
or excluding them (Ruling 2).
"""

from __future__ import annotations

from kavach.findings import RuleScope, Subject, rule
from kavach.units import UnitError, format_area, parse_area
from kavach.records import EntityType
from kavach.rules._support import (
    khata_subject,
    khesra_subject,
    mouza_subject,
    undated_abstention,
)

RULES: list = []


def grammar_rule(rule_id: str, scope: RuleScope = RuleScope.WITHIN_VERSION):
    """Declare a Class 1 rule and register it in one step."""

    def wrap(fn):
        declared = rule(rule_id, 1, scope)(fn)
        RULES.append(declared)
        return declared

    return wrap


@grammar_rule("C1.subdivision_number_positive")
def subdivision_number_positive(view, report):
    """Parcel numbering starts at 1, never 0 or negative."""
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for khesra in view.index.khesras:
        number = khesra.local_number.strip()
        if not number:
            continue  # blank is C1.identifier_present's job, not this rule's
        if number.lstrip("-").isdigit() and int(number) <= 0:
            yield report.error(
                khesra_subject(khesra, view.index, "local_number"),
                "parcel number is not positive; numbering starts at 1",
                {"local_number": khesra.local_number},
            )


@grammar_rule("C1.identifier_present")
def identifier_present(view, report):
    """Khesra and khata numbers must not be blank."""
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for khesra in view.index.khesras:
        if not khesra.local_number.strip():
            yield report.error(
                khesra_subject(khesra, view.index, "local_number"),
                "parcel number is blank",
                {"local_number": repr(khesra.local_number)},
            )
    for khata in view.index.khatas:
        if not khata.number.strip():
            yield report.error(
                khata_subject(khata, "number"),
                "khata number is blank",
                {"number": repr(khata.number)},
            )


_KHESRA_ALLOWED = set("0123456789/-")
_KHATA_ALLOWED = set("0123456789/-")


@grammar_rule("C1.identifier_charset")
def identifier_charset(view, report):
    """Parcel and khata numbers carry digits and separators only.

    Catches the classic transcription slip: '2l7' read for '217', where a lowercase
    L stands in for a one. A letter in a numeric identifier is certain, not likely.
    """
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for khesra in view.index.khesras:
        value = khesra.local_number.strip()
        stray = sorted(set(value) - _KHESRA_ALLOWED)
        if value and stray:
            yield report.error(
                khesra_subject(khesra, view.index, "local_number"),
                "parcel number contains characters that are not digits or separators",
                {"local_number": value, "stray_characters": "".join(stray)},
            )
    for khata in view.index.khatas:
        value = khata.number.strip()
        stray = sorted(set(value) - _KHATA_ALLOWED)
        if value and stray:
            yield report.error(
                khata_subject(khata, "number"),
                "khata number contains characters that are not digits or separators",
                {"number": value, "stray_characters": "".join(stray)},
            )


@grammar_rule("C1.area_positive")
def area_positive(view, report):
    """A stated area must be greater than zero.

    EVIDENCE.md E5 records area entered as zero or blank as a real, measured error
    class. Zero is treated as a violation; absent is not — absence makes downstream
    conservation UNVERIFIABLE and is reported by Class 8, not here.
    """
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for khesra in view.index.khesras:
        if khesra.area_stated is None:
            continue
        count = khesra.area_stated.area.count
        if count <= 0:
            yield report.error(
                khesra_subject(khesra, view.index, "area_stated"),
                "parcel area is not greater than zero",
                {"count": str(count)},
            )
    for khata in view.index.khatas:
        if khata.area_stated is None:
            continue
        count = khata.area_stated.area.count
        if count <= 0:
            yield report.error(
                khata_subject(khata, "area_stated"),
                "khata area is not greater than zero",
                {"count": str(count)},
            )


@grammar_rule("C1.unit_carry")
def unit_carry(view, report):
    """No written component may reach the base of the unit above it.

    "27 katha" in a base-20 ladder is a transcription artefact: it should have
    carried to "1 bigha 7 katha". The value is not wrong, the writing is — which is
    why `as_written` is stored rather than normalised away on load.
    """
    unwritten = [
        k for k in view.index.khesras if k.area_stated and not k.area_stated.as_written
    ]
    if unwritten:
        yield report.abstain(
            mouza_subject(view.records.mouza),
            f"{len(unwritten)} parcels state an area with no written form, so the "
            "carry cannot be checked for them",
            missing_witness="area_stated.as_written",
            evidence={"parcels": ", ".join(sorted(k.id for k in unwritten)[:10])},
        )
    for khesra in view.index.khesras:
        statement = khesra.area_stated
        if statement is None or not statement.as_written:
            continue
        try:
            parsed = parse_area(
                statement.as_written, statement.area.ladder_id, view.registry
            )
        except UnitError:
            continue  # unreadable is C1.area_written_matches_value's finding
        if not parsed.is_normalised:
            yield report.error(
                khesra_subject(khesra, view.index, "area_stated.as_written"),
                "written area was not carried into the unit above",
                {
                    "as_written": statement.as_written,
                    "should_read": format_area(parsed.area, view.registry),
                    "over_base": ", ".join(parsed.over_base) or "-",
                },
            )


@grammar_rule("C1.area_written_matches_value")
def area_written_matches_value(view, report):
    """The written area string must read back as the stored value."""
    unwritten = [
        k for k in view.index.khesras if k.area_stated and not k.area_stated.as_written
    ]
    if unwritten:
        yield report.abstain(
            mouza_subject(view.records.mouza),
            f"{len(unwritten)} parcels record no written form to compare against",
            missing_witness="area_stated.as_written",
        )
    for khesra in view.index.khesras:
        statement = khesra.area_stated
        if statement is None or not statement.as_written:
            continue
        try:
            parsed = parse_area(
                statement.as_written, statement.area.ladder_id, view.registry
            )
        except UnitError as exc:
            yield report.error(
                khesra_subject(khesra, view.index, "area_stated.as_written"),
                "written area cannot be read as an area in this ladder",
                {"as_written": statement.as_written, "reason": str(exc)},
            )
            continue
        if parsed.area != statement.area:
            yield report.error(
                khesra_subject(khesra, view.index, "area_stated"),
                "written area disagrees with the stored value",
                {
                    "as_written": statement.as_written,
                    "written_value": format_area(parsed.area, view.registry),
                    "stored_value": format_area(statement.area, view.registry),
                },
            )


@grammar_rule("C1.date_ordering")
def date_ordering(view, report):
    """A mutation cannot predate the survey that created the record."""
    survey = view.records.mouza.survey_date
    if survey is None:
        yield report.abstain(
            mouza_subject(view.records.mouza, "survey_date"),
            "no survey date, so mutation chronology cannot be checked",
            missing_witness="mouza.survey_date",
        )
        return
    undated = [m for m in view.records.mutations if m.date is None]
    if undated:
        yield report.abstain(
            mouza_subject(view.records.mouza),
            f"{len(undated)} mutations carry no date",
            missing_witness="mutation.date",
            evidence={"mutations": ", ".join(sorted(m.id for m in undated)[:10])},
        )
    for event in view.records.mutations:
        if event.date is not None and event.date < survey:
            yield report.error(
                Subject(EntityType.MUTATION, event.id, "date"),
                "mutation is dated before the survey that created the record",
                {"mutation_date": str(event.date), "survey_date": str(survey)},
            )
