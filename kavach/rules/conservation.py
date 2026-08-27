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
