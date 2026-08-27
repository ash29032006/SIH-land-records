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


# ---- machine-readable report ------------------------------------------------


def test_the_json_report_emits_exact_rationals_not_decimals():
    """Serialising a rate as a decimal would reintroduce the inexactness the whole
    codebase exists to avoid."""
    from kavach.report import as_json

    payload = as_json()
    assert payload["mutations"]["false_positives_on_clean"] == 0
    assert payload["mutations"]["recall"] == "1"
    for profile, figures in payload["profiles"].items():
        assert figures["certain_errors"] == 0, profile
        assert figures["invariant_violations"] == 0, profile
        rate = figures["verifiability_rate"]
        assert rate is None or "." not in rate, f"{profile} rate {rate} is a decimal"


def test_the_json_report_round_trips_through_json():
    import json

    from kavach.report import as_json

    assert json.loads(json.dumps(as_json())) == as_json()
