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
