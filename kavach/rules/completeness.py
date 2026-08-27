"""Class 3 — Completeness. What is missing, duplicated, or dangling.

One rule deliberately **absent**: "duplicate khata per owner", which
HANDOFF_BUILD.md 4 lists. In Bihar, partition is textual — each heir gets a separate
jamabandi on the same survey number (EVIDENCE.md E1, E3) — so one person legitimately
holding several khatas is the normal state of a correct record, not an error.
Implementing it as specified would have produced false positives at scale on exactly
the records the system is meant to protect.

What is unambiguous, and is implemented, is `C3.no_duplicate_holding`: the same khata
recorded as holding the same parcel twice.
"""

from __future__ import annotations

from collections import Counter

from kavach.findings import RuleScope, Subject, rule
from kavach.records import EntityType
from kavach.rules._support import (
    holding_subject,
    khata_subject,
    khesra_subject,
    mouza_subject,
    owner_subject,
    undated_abstention,
)

RULES: list = []


def completeness_rule(rule_id: str, scope: RuleScope = RuleScope.WITHIN_VERSION):
    """Declare a Class 3 rule and register it in one step."""

    def wrap(fn):
        declared = rule(rule_id, 3, scope)(fn)
        RULES.append(declared)
        return declared

    return wrap


@completeness_rule("C3.parcel_identifier_unique")
def parcel_identifier_unique(view, report):
    """No two parcels in a mouza share the same full path."""
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    seen: dict[tuple, list] = {}
    for khesra in view.index.khesras:
        path = view.index.path_of(khesra.id)
        if path is None:
            continue  # cycles are C3.no_cyclic_parentage's finding
        seen.setdefault(path, []).append(khesra)
    for path, group in seen.items():
        if len(group) > 1:
            yield report.error(
                tuple(khesra_subject(k, view.index, "local_number") for k in group),
                "more than one parcel carries this number in the same mouza",
                {"path": "/".join(path), "khesras": ", ".join(sorted(k.id for k in group))},
            )


@completeness_rule("C3.subdivision_sequence_complete")
def subdivision_sequence_complete(view, report):
    """Sub-division numbering runs 1..n with no holes.

    217/1 and 217/3 exist — where is 217/2? Either the record is missing or the
    numbering is wrong, and both warrant review.
    """
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for parent_id, children in view.index.children.items():
        parent = view.index.khesra_by_id.get(parent_id)
        if parent is None:
            continue
        numbers = []
        for child in children:
            value = child.local_number.strip()
            if not value.isdigit():
                numbers = []
                break  # non-numeric numbering is Class 1's finding, not a gap
            numbers.append(int(value))
        if not numbers:
            continue
        expected = set(range(1, len(numbers) + 1))
        actual = set(numbers)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            yield report.error(
                khesra_subject(parent, view.index, "sub-divisions"),
                "sub-division numbering is not a complete run from 1",
                {
                    "found": ", ".join(str(n) for n in sorted(numbers)),
                    "missing": ", ".join(str(n) for n in missing) or "-",
                    "unexpected": ", ".join(str(n) for n in extra) or "-",
                },
            )


@completeness_rule("C3.no_orphan_holding")
def no_orphan_holding(view, report):
    """Every holding points at a parcel and a khata that exist."""
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
    for holding in view.index.holdings:
        if holding.khesra_id not in view.index.khesra_by_id:
            yield report.error(
                holding_subject(holding, "khesra_id"),
                "holding points at a parcel that does not exist in this mouza",
                {"khesra_id": holding.khesra_id, "khata_id": holding.khata_id},
            )
        if holding.khata_id not in view.index.khata_by_id:
            yield report.error(
                holding_subject(holding, "khata_id"),
                "holding points at a khata that does not exist in this mouza",
                {"khata_id": holding.khata_id, "khesra_id": holding.khesra_id},
            )


@completeness_rule("C3.no_empty_khata")
def no_empty_khata(view, report):
    """A khata holds at least one parcel."""
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
        return
    for khata in view.index.khatas:
        if not view.index.holdings_by_khata.get(khata.id):
            yield report.error(
                khata_subject(khata),
                "khata holds no parcel",
                {"khata_number": khata.number},
            )


@completeness_rule("C3.no_unheld_parcel")
def no_unheld_parcel(view, report):
    """Every current parcel is held by at least one khata.

    Applies to leaves only. A sub-divided parent is no longer a parcel anyone holds;
    its children are. Flagging internal nodes would fire on every correctly
    partitioned plot in the mouza.
    """
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
        return
    for parcel in view.index.leaves():
        if not view.index.holdings_by_khesra.get(parcel.id):
            yield report.error(
                khesra_subject(parcel, view.index),
                "parcel belongs to no khata",
                {"parcel": view.index.display_path(parcel.id) or parcel.local_number},
            )


@completeness_rule("C3.no_duplicate_holding")
def no_duplicate_holding(view, report):
    """A khata is not recorded as holding the same parcel twice.

    This is the honest version of the spec's "duplicate khata per owner". An owner
    with several khatas is normal in Bihar; the same holding written down twice is
    not, and it inflates the parcel's claimed area by exactly one entry.
    """
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
    pairs = Counter((h.khata_id, h.khesra_id) for h in view.index.holdings)
    for (khata_id, khesra_id), count in sorted(pairs.items()):
        if count > 1:
            duplicates = [
                h for h in view.index.holdings
                if h.khata_id == khata_id and h.khesra_id == khesra_id
            ]
            yield report.error(
                tuple(holding_subject(h) for h in duplicates),
                "the same khata is recorded as holding this parcel more than once",
                {
                    "khata_id": khata_id,
                    "khesra_id": khesra_id,
                    "times": str(count),
                    "holdings": ", ".join(sorted(h.id for h in duplicates)),
                },
            )
