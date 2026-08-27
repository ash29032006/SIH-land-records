"""Class 1 — Grammar. The field is its own witness, so a violation is certain.

These are the cheapest checks in the system: no second document, no OCR, no portal,
no model. They run on tabular records as they stand.

Every rule here abstains over records it cannot date, rather than silently including
or excluding them (Ruling 2).
"""

from __future__ import annotations

from kavach.findings import RuleScope, rule
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
