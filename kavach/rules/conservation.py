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


@conservation_rule("C2.holding_shares_sum_to_one")
def holding_shares_sum_to_one(view, report):
    """Undivided shares in one parcel sum to exactly one."""
    abstention = undated_abstention(report, view, "holdings", view.index.unknown_holdings)
    if abstention:
        yield abstention
    for parcel in view.index.leaves():
        holdings = view.index.holdings_by_khesra.get(parcel.id, ())
        if not holdings:
            continue
        without = [h for h in holdings if h.share is None]
        if without:
            yield report.abstain(
                khesra_subject(parcel, view.index),
                f"{len(without)} of {len(holdings)} holdings record no share",
                missing_witness="holding.share",
            )
            continue
        total = sum((h.share for h in holdings), Fraction(0))
        if total != 1:
            yield report.error(
                khesra_subject(parcel, view.index, "holdings"),
                "undivided shares in this parcel do not sum to exactly one",
                {"shares_sum_to": str(total),
                 "shares": ", ".join(str(h.share) for h in holdings)},
            )


@conservation_rule("C2.tenure_totals_reconcile")
def tenure_totals_reconcile(view, report):
    """Parcels of each tenure class sum to the subtotal the mouza states.

    This is what makes `raiyati_total + gairmazrua_total == mouza_total` checkable.
    Without independently stated subtotals, flipping one parcel from raiyati to
    gairmazrua is arithmetically invisible: the partition sums either way.

    EVIDENCE.md E6: the digitised jamabandi has no classification column at all, so
    on that input this rule abstains rather than passing.
    """
    mouza = view.records.mouza
    subject = mouza_subject(mouza, "tenure_totals")
    if not mouza.tenure_totals:
        yield report.abstain(
            subject,
            "the mouza states no per-tenure subtotals, so a misclassified parcel "
            "cannot be detected arithmetically",
            missing_witness="mouza.tenure_totals",
        )
        return
    unclassified = [k for k in view.index.leaves() if k.tenure is None]
    if unclassified:
        yield report.abstain(
            subject,
            f"{len(unclassified)} current parcels carry no tenure class",
            missing_witness="khesra.tenure",
            evidence={"parcels": ", ".join(sorted(k.id for k in unclassified)[:10])},
        )
        return
    by_code: dict[str, Fraction] = {}
    for parcel in view.index.leaves():
        if parcel.area_stated is None:
            yield report.abstain(
                khesra_subject(parcel, view.index, "area_stated"),
                "parcel states no area, so tenure subtotals cannot be reconciled",
                missing_witness="khesra.area_stated",
            )
            return
        by_code[parcel.tenure] = by_code.get(parcel.tenure, Fraction(0)) + units_of(
            parcel.area_stated
        )
    ladder_id = mouza.ladder_id
    for total in mouza.tenure_totals:
        stated = units_of(total.area_stated)
        actual = by_code.get(total.code, Fraction(0))
        if actual != stated:
            yield report.error(
                subject,
                f"parcels classified {total.code!r} do not sum to the stated subtotal",
                {
                    "tenure": total.code,
                    "parcels_sum_to": _text(actual, ladder_id, view.registry),
                    "mouza_states": _text(stated, ladder_id, view.registry),
                    "difference": _text(actual - stated, ladder_id, view.registry),
                },
            )
    unstated = sorted(set(by_code) - {t.code for t in mouza.tenure_totals})
    for code in unstated:
        yield report.error(
            subject,
            f"parcels are classified {code!r} but the mouza states no subtotal for it",
            {"tenure": code,
             "parcels_sum_to": _text(by_code[code], ladder_id, view.registry)},
        )


@conservation_rule("C2.cross_unit_restatement")
def cross_unit_restatement(view, report):
    """An area restated in another unit system must convert back exactly.

    EVIDENCE.md E10. The Bihar rakba field records one area **three times** — acres,
    decimal and hectares — on the same row. That is a second witness inside a single
    record: no other document, no OCR, no portal, no model. It is very likely the
    cheapest certain check in the whole system, and neither build document names it.

    Where a ladder carries no declared exact rational the conversion refuses, and the
    refusal becomes an abstention rather than a guess.
    """
    checked = 0
    for parcel in view.index.khesras:
        primary = parcel.area_stated
        if primary is None or not parcel.area_restatements:
            continue
        for restatement in parcel.area_restatements:
            try:
                converted = convert(
                    primary.area, restatement.area.ladder_id, view.registry
                )
            except ConversionRefused as refusal:
                yield report.abstain(
                    khesra_subject(parcel, view.index, "area_restatements"),
                    "the two unit systems cannot be reconciled exactly",
                    missing_witness="declared exact rational between ladders",
                    evidence={"reason": str(refusal)},
                )
                continue
            checked += 1
            if converted != restatement.area:
                yield report.error(
                    khesra_subject(parcel, view.index, "area_restatements"),
                    "the same area stated in two unit systems does not agree",
                    {
                        "primary": format_area(primary.area, view.registry),
                        "restated_as": format_area(restatement.area, view.registry),
                        "primary_converts_to": format_area(converted, view.registry),
                        "ladder": restatement.area.ladder_id,
                    },
                )
    if checked == 0:
        yield report.abstain(
            mouza_subject(view.records.mouza),
            "no parcel restates its area in a second unit system, so there is no "
            "second witness inside the record to check against",
            missing_witness="khesra.area_restatements",
        )


@conservation_rule("C2.share_matches_claimed_area")
def share_matches_claimed_area(view, report):
    """Where a holding records both a share and an area, they must agree.

    SCHEMA.md Correction 1: these are two separately stored values, never one derived
    from the other, precisely so their disagreement is visible. A record that states
    a half share of a hundred-decimal parcel and claims sixty decimal is telling you
    something, and collapsing the two fields on load would delete it.

    Both fields present at once is the rare case on real Bihar input, so this rule
    abstains often.
    """
    reconciled = 0
    for parcel in view.index.leaves():
        stated = units_of(parcel.area_stated)
        if stated is None:
            continue
        ladder_id = parcel.area_stated.area.ladder_id
        for holding in view.index.holdings_by_khesra.get(parcel.id, ()):
            if holding.share is None or holding.area_claimed is None:
                continue
            reconciled += 1
            implied = stated * holding.share
            claimed = units_of(holding.area_claimed)
            if implied != claimed:
                yield report.error(
                    holding_subject(holding, "area_claimed"),
                    "the share and the claimed area do not describe the same ground",
                    {
                        "share": str(holding.share),
                        "parcel_area": _text(stated, ladder_id, view.registry),
                        "share_implies": _text(implied, ladder_id, view.registry),
                        "claimed": _text(claimed, ladder_id, view.registry),
                        "difference": _text(implied - claimed, ladder_id, view.registry),
                    },
                )
    if reconciled == 0:
        yield report.abstain(
            mouza_subject(view.records.mouza),
            "no holding records both a share and a claimed area, so the two cannot "
            "be cross-examined",
            missing_witness="holding.share with holding.area_claimed",
        )


@conservation_rule("C2.area_conserved_across_versions", RuleScope.ACROSS_VERSION)
def area_conserved_across_versions(view, report):
    """The mouza's parcels sum to the same ground before and after a mutation.

    HANDOFF_BUILD.md 4: "Parent area at T == Σ child areas at T+1". This is the only
    ACROSS_VERSION rule in Phase 1, and it is the check that catches area appearing
    or disappearing during a mutation rather than within a single register.

    Sub-division is legitimate and must not fire: parcels split, the total does not
    move. What fires is the total moving.
    """
    earlier, later = view.earlier, view.later
    early_index, late_index = earlier.index, later.index

    for label, index in (("earlier", early_index), ("later", late_index)):
        undetermined = index.undetermined_leaves()
        if undetermined:
            yield report.abstain(
                mouza_subject(index.records.mouza),
                f"{len(undetermined)} parcels in the {label} version have "
                "undetermined leaf status",
                missing_witness="khesra validity dates",
            )
            return

    early_leaves, late_leaves = early_index.leaves(), late_index.leaves()
    missing = [k for k in early_leaves + late_leaves if k.area_stated is None]
    if missing:
        yield report.abstain(
            mouza_subject(later.records.mouza),
            f"{len(missing)} parcels state no area, so the two versions cannot be "
            "compared",
            missing_witness="khesra.area_stated",
            evidence={"parcels": ", ".join(sorted(k.id for k in missing)[:10])},
        )
        return

    ladder_id = later.records.mouza.ladder_id
    before = sum((units_of(k.area_stated) for k in early_leaves), Fraction(0))
    after = sum((units_of(k.area_stated) for k in late_leaves), Fraction(0))
    if before != after:
        yield report.error(
            mouza_subject(later.records.mouza, "area_stated"),
            "the mouza's parcels do not sum to the same ground in both versions",
            {
                "earlier_total": _text(before, ladder_id, view.registry),
                "later_total": _text(after, ladder_id, view.registry),
                "difference": _text(after - before, ladder_id, view.registry),
                "earlier_parcels": str(len(early_leaves)),
                "later_parcels": str(len(late_leaves)),
            },
        )

    # A parcel that gained children must equal them exactly.
    for parcel in early_leaves:
        children = late_index.children.get(parcel.id, ())
        if not children:
            continue
        if any(c.area_stated is None for c in children):
            continue  # already abstained above
        child_total = sum((units_of(c.area_stated) for c in children), Fraction(0))
        parent_units = units_of(parcel.area_stated)
        if child_total != parent_units:
            yield report.error(
                khesra_subject(parcel, late_index, "area_stated"),
                "a parcel's sub-divisions do not account for it after the mutation",
                {
                    "parent_at_earlier": _text(parent_units, ladder_id, view.registry),
                    "children_at_later": _text(child_total, ladder_id, view.registry),
                    "difference": _text(child_total - parent_units, ladder_id, view.registry),
                },
            )
