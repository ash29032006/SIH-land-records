"""The rule catalogue is generated, so it cannot drift from the registry."""

from __future__ import annotations

from kavach.catalogue import CATALOGUE_PATH, render
from kavach.rules import ALL_RULES


def test_rules_md_is_up_to_date():
    assert CATALOGUE_PATH.exists(), "run: python -m kavach.catalogue"
    assert CATALOGUE_PATH.read_text(encoding="utf-8") == render(), (
        "RULES.md is behind the registry — run: python -m kavach.catalogue"
    )


def test_the_catalogue_lists_every_registered_rule():
    text = render()
    for declared in ALL_RULES:
        assert f"`{declared.id}`" in text, f"{declared.id} missing from the catalogue"


def test_the_catalogue_records_what_was_deliberately_not_built():
    text = render()
    assert "Deliberately not implemented" in text
    assert "Duplicate khata per owner" in text
