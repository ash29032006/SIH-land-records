"""Classes 4-7 — specced, blocked on external data, and abstaining cleanly.

HANDOFF_BUILD.md 4 and 8. Each of these needs a fact this project does not yet have:

| Class | Needs | Blocked on |
|---|---|---|
| 4 chain continuity | two versions of the same record | a second extraction |
| 5 text vs geometry | cadastral polygons | whether the portal serves them |
| 6 cross-system | registration / revenue data | whether NGDRS is accessible |
| 7 statistical | corpus scale | a legally obtained bulk corpus |

They are here as **interfaces with no bodies**, and each returns UNVERIFIABLE naming
what it lacks. Stubbing them as passing would be the exact failure the whole project
argues against: a check that cannot run reported as a check that ran.

Class 7 in particular must never emit CERTAIN_ERROR when it is implemented. A
statistical outlier is an ANOMALY — it directs sampling and is never a finding alone.
"""

from __future__ import annotations

from kavach.findings import RuleScope, rule
from kavach.rules._support import mouza_subject

RULES: list = []


def _blocked(rule_id: str, validation_class: int, needs: str, blocked_on: str,
             scope: RuleScope = RuleScope.WITHIN_VERSION):
    """Declare a rule that is specified but cannot run, and register it."""

    @rule(rule_id, validation_class, scope)
    def declared(view, report, _needs=needs, _blocked=blocked_on):
        return [
            report.abstain(
                mouza_subject(view.records.mouza)
                if hasattr(view, "records")
                else mouza_subject(view.later.records.mouza),
                f"not implemented: this class needs {_needs}",
                missing_witness=_needs,
                evidence={"blocked_on": _blocked, "status": "specced, no body"},
            )
        ]

    RULES.append(declared)
    return declared


chain_continuity = _blocked(
    "C4.chain_continuity", 4,
    "two versions of the same record",
    "a second extraction of the same mouza at a different date",
    scope=RuleScope.ACROSS_VERSION,
)

text_versus_geometry = _blocked(
    "C5.text_versus_geometry", 5,
    "cadastral polygons for these parcels",
    "whether the state portal serves historical and current survey layers for a real "
    "non-pilot village (HANDOFF_BUILD.md 8, question 1)",
)

cross_system = _blocked(
    "C6.cross_system", 6,
    "registration and revenue records for the same land",
    "whether registration-system data is accessible (HANDOFF_BUILD.md 8, question 2)",
)

statistical = _blocked(
    "C7.statistical", 7,
    "a corpus large enough for distributional tests",
    "a legal, rate-limited path to bulk public records (HANDOFF_BUILD.md 8, question 3). "
    "When implemented this class emits ANOMALY, never CERTAIN_ERROR.",
)
