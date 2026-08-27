"""Class 2 — Conservation. The double-entry core.

Land is conserved: a village's total area has not changed since the settlement
survey, so records that violate that conservation are provably wrong with no ground
truth, no annotator and no model. This is the part of the system nobody else has.

**Tolerance policy, declared explicitly (HANDOFF_BUILD.md 4).** Every comparison here
is exact equality over `Fraction` counts of a ladder's smallest unit. There is no
epsilon anywhere in this module and there is no parameter to add one. If a real
corpus later forces a tolerance it must arrive as a named, justified parameter on a
specific rule — never as a magic constant buried in a comparison.

Conservation sums **leaves as of a date**. `is_leaf` is derived, never stored, so a
sub-divided parent cannot be counted twice.
"""

from __future__ import annotations

from fractions import Fraction

from kavach.findings import RuleScope, rule
from kavach.records import LeafStatus
from kavach.rules._support import (
    holding_subject,
    khata_subject,
    khesra_subject,
    mouza_subject,
    undated_abstention,
    units_of,
)
from kavach.units import Area, ConversionRefused, convert, format_area

RULES: list = []


def conservation_rule(rule_id: str, scope: RuleScope = RuleScope.WITHIN_VERSION):
    """Declare a Class 2 rule and register it in one step."""

    def wrap(fn):
        declared = rule(rule_id, 2, scope)(fn)
        RULES.append(declared)
        return declared

    return wrap


def _text(count: Fraction, ladder_id: str, registry) -> str:
    return format_area(Area(ladder_id, count), registry)


@conservation_rule("C2.children_sum_to_parent")
def children_sum_to_parent(view, report):
    """Sub-plot areas sum to the parent plot's area, exactly."""
    abstention = undated_abstention(report, view, "khesras", view.index.unknown_khesras)
    if abstention:
        yield abstention
    for parent in view.index.khesras:
        children = view.index.children.get(parent.id, ())
        if not children:
            continue
        stated = units_of(parent.area_stated)
        if stated is None:
            yield report.abstain(
                khesra_subject(parent, view.index, "area_stated"),
                "parent states no area, so its children cannot be reconciled against it",
                missing_witness="khesra.area_stated",
            )
            continue
        missing = [c for c in children if c.area_stated is None]
        if missing:
            yield report.abstain(
                khesra_subject(parent, view.index),
                f"{len(missing)} of {len(children)} sub-plots state no area",
                missing_witness="khesra.area_stated",
                evidence={"without_area": ", ".join(sorted(c.id for c in missing))},
            )
            continue
        total = sum((units_of(c.area_stated) for c in children), Fraction(0))
        if total != stated:
            yield report.error(
                khesra_subject(parent, view.index, "area_stated"),
                "sub-plot areas do not sum to the parent plot",
                {
                    "children_sum_to": _text(total, parent.area_stated.area.ladder_id, view.registry),
                    "parent_states": _text(stated, parent.area_stated.area.ladder_id, view.registry),
                    "difference": _text(total - stated, parent.area_stated.area.ladder_id, view.registry),
                    "children": ", ".join(sorted(c.id for c in children)),
                },
            )


@conservation_rule("C2.leaves_sum_to_mouza")
def leaves_sum_to_mouza(view, report):
    """Every current parcel in the mouza sums to the mouza's stated total.

    The trial balance. Sums leaves only — a sub-divided parent is no longer a parcel
    that holds area, and counting it would double the ground it sits on.
    """
    mouza = view.records.mouza
    subject = mouza_subject(mouza, "area_stated")
    if mouza.area_stated is None:
        yield report.abstain(
            subject,
            "the mouza states no total, so the trial balance cannot run",
            missing_witness="mouza.area_stated",
        )
        return
    undetermined = view.index.undetermined_leaves()
    if undetermined:
        yield report.abstain(
            subject,
            f"{len(undetermined)} parcels have undetermined leaf status, so the set "
            "of current parcels is not known",
            missing_witness="khesra validity dates",
            evidence={"parcels": ", ".join(sorted(k.id for k in undetermined)[:10])},
        )
        return
    leaves = view.index.leaves()
    missing = [k for k in leaves if k.area_stated is None]
    if missing:
        yield report.abstain(
            subject,
            f"{len(missing)} of {len(leaves)} current parcels state no area",
            missing_witness="khesra.area_stated",
            evidence={"without_area": ", ".join(sorted(k.id for k in missing)[:10])},
        )
        return
    ladder_id = mouza.area_stated.area.ladder_id
    total = sum((units_of(k.area_stated) for k in leaves), Fraction(0))
    stated = units_of(mouza.area_stated)
    if total != stated:
        yield report.error(
            subject,
            "current parcels do not sum to the stated mouza total",
            {
                "parcels_sum_to": _text(total, ladder_id, view.registry),
                "mouza_states": _text(stated, ladder_id, view.registry),
                "difference": _text(total - stated, ladder_id, view.registry),
                "parcel_count": str(len(leaves)),
            },
        )


@conservation_rule("C2.holdings_sum_to_parcel")
def holdings_sum_to_parcel(view, report):
    """Claimed areas across all khatas holding a parcel sum to that parcel.

    This is the many-to-many join reconciling: several jamabandis do exist under one
    survey number (EVIDENCE.md E1), each stating its own extent, and together they
    must account for the parcel exactly once.
    """
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
    for parcel in view.index.leaves():
        holdings = view.index.holdings_by_khesra.get(parcel.id, ())
        if not holdings:
            continue  # unheld parcels are C3.no_unheld_parcel's finding
        stated = units_of(parcel.area_stated)
        if stated is None:
            yield report.abstain(
                khesra_subject(parcel, view.index, "area_stated"),
                "parcel states no area to reconcile its holdings against",
                missing_witness="khesra.area_stated",
            )
            continue
        without = [h for h in holdings if h.area_claimed is None]
        if without:
            yield report.abstain(
                khesra_subject(parcel, view.index),
                f"{len(without)} of {len(holdings)} holdings claim no area",
                missing_witness="holding.area_claimed",
                evidence={"holdings": ", ".join(sorted(h.id for h in without))},
            )
            continue
        ladder_id = parcel.area_stated.area.ladder_id
        total = sum((units_of(h.area_claimed) for h in holdings), Fraction(0))
        if total != stated:
            yield report.error(
                khesra_subject(parcel, view.index, "area_stated"),
                "claimed areas do not account for the parcel exactly",
                {
                    "claims_sum_to": _text(total, ladder_id, view.registry),
                    "parcel_states": _text(stated, ladder_id, view.registry),
                    "difference": _text(total - stated, ladder_id, view.registry),
                    "khatas": ", ".join(sorted(h.khata_id for h in holdings)),
                },
            )


@conservation_rule("C2.holdings_sum_to_khata")
def holdings_sum_to_khata(view, report):
    """A khata's holdings sum to the total that khata states."""
    abstention = undated_abstention(report, view, "khatas", view.index.unknown_khatas)
    if abstention:
        yield abstention
    for khata in view.index.khatas:
        stated = units_of(khata.area_stated)
        if stated is None:
            yield report.abstain(
                khata_subject(khata, "area_stated"),
                "khata states no total to reconcile its holdings against",
                missing_witness="khata.area_stated",
            )
            continue
        holdings = view.index.holdings_by_khata.get(khata.id, ())
        if not holdings:
            continue  # empty khatas are C3.no_empty_khata's finding
        without = [h for h in holdings if h.area_claimed is None]
        if without:
            yield report.abstain(
                khata_subject(khata),
                f"{len(without)} of {len(holdings)} holdings claim no area",
                missing_witness="holding.area_claimed",
            )
            continue
        ladder_id = khata.area_stated.area.ladder_id
        total = sum((units_of(h.area_claimed) for h in holdings), Fraction(0))
        if total != stated:
            yield report.error(
                khata_subject(khata, "area_stated"),
                "holdings do not sum to the khata's stated total",
                {
                    "holdings_sum_to": _text(total, ladder_id, view.registry),
                    "khata_states": _text(stated, ladder_id, view.registry),
                    "difference": _text(total - stated, ladder_id, view.registry),
                },
            )


@conservation_rule("C2.khata_totals_sum_to_mouza")
def khata_totals_sum_to_mouza(view, report):
    """Every khata total in the mouza sums to the mouza total.

    The trial balance seen from the tenurial spine instead of the spatial one. It
    catches a duplicated khata, which `C2.leaves_sum_to_mouza` cannot see at all.
    """
    mouza = view.records.mouza
    subject = mouza_subject(mouza, "area_stated")
    if mouza.area_stated is None:
        yield report.abstain(
            subject,
            "the mouza states no total to reconcile khata totals against",
            missing_witness="mouza.area_stated",
        )
        return
    abstention = undated_abstention(report, view, "khatas", view.index.unknown_khatas)
    if abstention:
        yield abstention
        return
    khatas = view.index.khatas
    without = [k for k in khatas if k.area_stated is None]
    if without:
        yield report.abstain(
            subject,
            f"{len(without)} of {len(khatas)} khatas state no total",
            missing_witness="khata.area_stated",
            evidence={"khatas": ", ".join(sorted(k.id for k in without)[:10])},
        )
        return
    ladder_id = mouza.area_stated.area.ladder_id
    total = sum((units_of(k.area_stated) for k in khatas), Fraction(0))
    stated = units_of(mouza.area_stated)
    if total != stated:
        yield report.error(
            subject,
            "khata totals do not sum to the stated mouza total",
            {
                "khatas_sum_to": _text(total, ladder_id, view.registry),
                "mouza_states": _text(stated, ladder_id, view.registry),
                "difference": _text(total - stated, ladder_id, view.registry),
                "khata_count": str(len(khatas)),
            },
        )


@conservation_rule("C2.co_owner_shares_sum_to_one")
def co_owner_shares_sum_to_one(view, report):
    """Co-owner shares in a khata sum to exactly one.

    EVIDENCE.md E2: Bihar jamabandis with multiple owners state **no shares at all**.
    So on real input this rule abstains rather than passing, and that abstention is
    probably the highest-volume honest output the engine produces.
    """
    abstention = undated_abstention(
        report, view, "memberships", view.index.unknown_memberships
    )
    if abstention:
        yield abstention
    for khata in view.index.khatas:
        members = view.index.memberships_by_khata.get(khata.id, ())
        if not members:
            continue  # ownerless khatas are C3.no_ownerless_khata's finding
        without = [m for m in members if m.share is None]
        if without:
            yield report.abstain(
                khata_subject(khata),
                f"{len(without)} of {len(members)} owners have no recorded share",
                missing_witness="membership.share",
                evidence={"owners": ", ".join(sorted(m.owner_id for m in without))},
            )
            continue
        total = sum((m.share for m in members), Fraction(0))
        if total != 1:
            yield report.error(
                khata_subject(khata, "memberships"),
                "co-owner shares do not sum to exactly one",
                {
                    "shares_sum_to": str(total),
                    "owner_count": str(len(members)),
                    "shares": ", ".join(str(m.share) for m in members),
                },
            )
