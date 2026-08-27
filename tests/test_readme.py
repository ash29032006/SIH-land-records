"""The README states measured figures, so it must not be allowed to drift.

The whole project's argument is that a number you cannot back up is worse than no
number. A README quoting a recall the code no longer produces is exactly that
failure, in the most visible file in the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kavach.report import as_json

README = Path(__file__).resolve().parents[1].joinpath("README.md")
TEXT = README.read_text(encoding="utf-8")
FIGURES = as_json()


def test_the_readme_rule_count_is_current():
    assert f'**{FIGURES["rules"]["total"]}**' in TEXT, (
        f'README does not state {FIGURES["rules"]["total"]} rules'
    )


def test_the_readme_mutation_counts_are_current():
    cases = FIGURES["mutations"]["cases"]
    assert f"**{cases}**" in TEXT
    assert f'**{FIGURES["mutations"]["detected"]} / {cases}**' in TEXT
    assert f'**{FIGURES["mutations"]["localised"]} / {cases}**' in TEXT


def test_the_readme_claims_zero_false_positives_only_while_that_is_true():
    assert FIGURES["mutations"]["false_positives_on_clean"] == 0
    assert "**0**" in TEXT


def test_the_readme_verifiability_rates_are_current():
    for profile, figures in FIGURES["profiles"].items():
        rate = figures["verifiability_rate"]
        if rate is not None:
            assert rate in TEXT, f"README is missing the {profile} rate {rate}"


def _declared_test_count() -> int:
    """Count test functions by parsing the suite, including parametrised ones.

    A test function decorated with `@pytest.mark.parametrize` produces more than one
    case, so this counts *cases* where the parameters are literal, and functions
    otherwise. It is the same figure a reader of the README would expect to see.
    """
    import ast

    total = 0
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            cases = 1
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                target = decorator.func
                name = getattr(target, "attr", getattr(target, "id", ""))
                if name != "parametrize" or len(decorator.args) < 2:
                    continue
                values = decorator.args[1]
                if isinstance(values, (ast.List, ast.Tuple)):
                    cases = cases * max(1, len(values.elts))
            total += cases
    return total


def test_the_readme_test_count_is_in_step_with_the_suite():
    """Not an exact match — parametrised cases built at import time cannot be counted
    statically — but the README must not be wildly out of date."""
    stated = re.search(r"\| tests \| (\d+) \|", TEXT)
    assert stated, "README states no test count"
    claimed = int(stated.group(1))
    declared = _declared_test_count()
    assert declared > 0
    assert claimed >= declared, (
        f"README claims {claimed} tests but the suite declares at least {declared}"
    )
    assert claimed <= declared * 4, (
        f"README claims {claimed} tests against {declared} declared — likely stale"
    )
