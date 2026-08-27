"""The rule classes.

Each rule is a pure function of a view. Registries here are the single source of
truth for what ships — `kavach.report` reads `ALL_RULES` and nothing else, so a
rule that is written but not registered is visibly absent rather than silently so.
"""

from __future__ import annotations

from kavach.rules.blocked import RULES as _BLOCKED
from kavach.rules.census import RULES as _CENSUS
from kavach.rules.completeness import RULES as _COMPLETENESS
from kavach.rules.conservation import RULES as _CONSERVATION
from kavach.rules.grammar import RULES as _GRAMMAR

GRAMMAR_RULES: tuple = tuple(_GRAMMAR)
CONSERVATION_RULES: tuple = tuple(_CONSERVATION)
COMPLETENESS_RULES: tuple = tuple(_COMPLETENESS)
CENSUS_RULES: tuple = tuple(_CENSUS)
BLOCKED_RULES: tuple = tuple(_BLOCKED)

ALL_RULES: tuple = (
    GRAMMAR_RULES
    + CONSERVATION_RULES
    + COMPLETENESS_RULES
    + CENSUS_RULES
    + BLOCKED_RULES
)

__all__ = [
    "ALL_RULES",
    "BLOCKED_RULES",
    "CENSUS_RULES",
    "COMPLETENESS_RULES",
    "CONSERVATION_RULES",
    "GRAMMAR_RULES",
]
