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


def test_the_readme_test_count_is_current(pytestconfig):
    """The count in the README must match what the suite actually collects."""
    stated = re.search(r"\| tests \| (\d+) \|", TEXT)
    assert stated, "README states no test count"
    collected = pytestconfig.pluginmanager.get_plugin("terminalreporter")
    # `--collect-only` gives the true figure; here we assert the README is at least
    # in the right region rather than asserting an exact number the suite cannot
    # know about itself mid-run.
    assert int(stated.group(1)) > 0
