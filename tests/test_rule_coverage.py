"""AGENTS.md 4.2, enforced mechanically.

    "Every rule ships with three fixtures: one that violates it, one that passes it,
     and one where the witness is missing. A rule without all three is not done."

A checklist nobody checks is a wish. This scans the registered rules against the
test suite and fails when one is short, so the rule that is easiest to skip — the
witness-missing case — cannot be skipped quietly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kavach.rules import ALL_RULES, BLOCKED_RULES

TESTS = Path(__file__).parent
MINIMUM_FIXTURES = 3

# Classes 4-7 are interfaces with no bodies. They are covered collectively in
# test_rules_blocked.py, which asserts none of them can report a pass.
EXEMPT = {r.id for r in BLOCKED_RULES}
TESTED_RULES = tuple(r for r in ALL_RULES if r.id not in EXEMPT)


def _test_function_names() -> tuple[str, ...]:
    names: list[str] = []
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                names.append(node.name)
    return tuple(names)


ALL_TEST_NAMES = _test_function_names()


@pytest.mark.parametrize("declared", TESTED_RULES, ids=lambda r: r.id)
def test_every_rule_has_at_least_three_fixtures(declared):
    stem = declared.fn.__name__
    matching = [name for name in ALL_TEST_NAMES if stem in name]
    assert len(matching) >= MINIMUM_FIXTURES, (
        f"{declared.id} has {len(matching)} fixtures, needs {MINIMUM_FIXTURES}: "
        f"{matching}"
    )


@pytest.mark.parametrize("declared", TESTED_RULES, ids=lambda r: r.id)
def test_every_rule_has_a_witness_missing_fixture(declared):
    """The one that gets skipped. UNVERIFIABLE is not a pass, so it must be tested."""
    stem = declared.fn.__name__
    abstaining = [
        name for name in ALL_TEST_NAMES if stem in name and "abstain" in name
    ]
    assert abstaining, (
        f"{declared.id} has no fixture asserting it abstains when its witness is "
        "missing. A rule that cannot run has not passed (AGENTS.md 3.3)."
    )


def test_every_registered_rule_declares_a_scope_and_a_class():
    for declared in ALL_RULES:
        assert declared.scope is not None, declared.id
        assert 1 <= declared.validation_class <= 8, declared.id
        assert declared.description, f"{declared.id} has no docstring"


def test_rule_ids_are_prefixed_with_their_class():
    for declared in ALL_RULES:
        assert declared.id.startswith(f"C{declared.validation_class}."), declared.id


def test_no_rule_is_named_as_a_verdict():
    """AGENTS.md 3.4 — flag, never verdict. A legal constraint, not a style one."""
    forbidden = ("is_fraud", "detect_fraud", "is_wrong", "forgery", "is_invalid",
                 "is_fake", "verdict", "guilty")
    for declared in ALL_RULES:
        haystack = f"{declared.id} {declared.fn.__name__}".lower()
        for word in forbidden:
            assert word not in haystack, f"{declared.id} is named as a verdict"
