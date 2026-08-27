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
