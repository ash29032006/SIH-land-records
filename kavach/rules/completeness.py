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
