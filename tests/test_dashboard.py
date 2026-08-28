"""The reviewer's view. Real engine output only — nothing on the page is mocked."""

from __future__ import annotations

import json
from fractions import Fraction

import pytest

from kavach.dashboard import build_payload, consequence_of, queue_order
from kavach.findings import Engine, FindingClass
from kavach.mutations import apply_mutation
from kavach.records import EntityType
from kavach.rules import ALL_RULES
from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza
from kavach.units import default_registry

REG = default_registry()
CLEAN = synthetic_mouza(MouzaSpec(seed=11))
FLAGGED = apply_mutation("one_unit_added_to_parcel", CLEAN, REG, seed=3).mutated


def test_a_clean_mouza_shows_no_errors_and_still_shows_abstentions():
    payload = build_payload(CLEAN)
    assert payload["totals"]["certain_errors"] == 0
    assert payload["totals"]["unverifiable"] > 0, "abstentions must be visible"


def test_a_flagged_mouza_surfaces_the_corruption():
    payload = build_payload(FLAGGED)
    assert payload["totals"]["certain_errors"] > 0
    assert payload["queue"][0]["finding_class"] == "certain_error"


def test_the_queue_is_ordered_by_consequence_never_by_ascending_confidence():
    """HANDOFF_BUILD.md 6.6, recorded so it is not re-derived wrongly."""
    payload = build_payload(FLAGGED)
    severities = [row["finding_class"] for row in payload["queue"]]
    assert severities == sorted(
        severities, key=lambda c: {"certain_error": 0, "conflict": 1,
                                   "anomaly": 2, "unverifiable": 3}[c]
    )
    errors = [r for r in payload["queue"] if r["finding_class"] == "certain_error"]
    stakes = [Fraction(r["stake_units"]) for r in errors]
    assert stakes == sorted(stakes, reverse=True), "land at stake must descend"


def test_abstentions_appear_in_the_queue_rather_than_being_filtered_out():
    """A reviewer UI that only listed errors would recreate the failure the project
    exists to attack."""
    payload = build_payload(CLEAN)
    abstentions = [r for r in payload["queue"] if r["finding_class"] == "unverifiable"]
    assert abstentions
    assert all(r["missing_witness"] for r in abstentions)


def test_every_queue_row_names_the_rule_and_the_record():
    payload = build_payload(FLAGGED)
    for row in payload["queue"]:
        assert row["rule_id"]
        assert row["subjects"] and row["subjects"][0]["id"]
        assert row["message"]


def test_nothing_on_the_page_asserts_a_verdict():
    """AGENTS.md 3.4 — a legal constraint, not a stylistic one."""
    payload = build_payload(FLAGGED)
    text = json.dumps(payload).lower()
    for word in ("fraud", "forgery", "guilty", "is_wrong", "invalid title"):
        assert word not in text


def test_consequence_is_land_at_stake_not_a_confidence_score():
    payload = build_payload(FLAGGED)
    index = FLAGGED.index(FLAGGED.as_of)
    result = Engine(ALL_RULES).run(FLAGGED, REG, as_of=FLAGGED.as_of)
    for finding in result.findings:
        stake = consequence_of(finding, FLAGGED, index)
        assert isinstance(stake, Fraction)
        assert stake >= 0


@pytest.mark.parametrize("profile", list(DocumentProfile))
def test_the_verifiability_rate_is_carried_through_for_every_profile(profile):
    payload = build_payload(synthetic_mouza(MouzaSpec(seed=11, profile=profile)))
    percent = payload["verifiability"]["percent"]
    assert percent is not None and 0 <= percent <= 100
    assert len(payload["verifiability"]["witnesses"]) == 12


def test_the_payload_is_json_serialisable_and_holds_no_floats():
    payload = build_payload(FLAGGED)
    text = json.dumps(payload)
    restored = json.loads(text)
    assert restored == payload

    def walk(node, path="payload"):
        if isinstance(node, float):
            raise AssertionError(f"{path} is a float")
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(payload)


def test_synthetic_input_is_flagged_as_synthetic():
    """AGENTS.md 2 — demo data must never be presented as measurement."""
    assert build_payload(CLEAN)["mouza"]["is_synthetic"] is True


def test_parcels_are_ordered_by_attention_needed():
    payload = build_payload(FLAGGED)
    flagged_first = [len(p["finding_rows"]) for p in payload["parcels"]]
    assert flagged_first == sorted(flagged_first, reverse=True)


def test_the_map_rings_errors_not_abstentions():
    """A red ring on a parcel must mean an error was found, never that the parcel
    could not be checked. On a jamabandi register most parcels carry abstentions and
    almost none carry errors; ringing both would read as a village full of mistakes."""
    from kavach.webui import demo_register

    payload = build_payload(demo_register())
    with_errors = [p for p in payload["parcels"] if p["error_rows"]]
    with_any = [p for p in payload["parcels"] if p["finding_rows"]]
    assert with_any, "abstentions should reach parcels"
    assert len(with_errors) < len(with_any), "errors must be rarer than findings"
    for parcel in payload["parcels"]:
        assert set(parcel["error_rows"]) <= set(parcel["finding_rows"])
        for row in parcel["error_rows"]:
            assert payload["queue"][row]["finding_class"] == "certain_error"


def test_witnesses_that_cannot_apply_are_marked_not_zeroed():
    from kavach.webui import demo_register

    rows = build_payload(demo_register())["verifiability"]["witnesses"]
    child = next(r for r in rows if r["name"] == "child_areas")
    assert child["applicable"] == 0
    assert child["percent"] is None, "an inapplicable witness is not a failed check"


def test_the_demo_register_is_the_de_facto_record_not_the_reconciled_one():
    """Demonstrating on the combined profile would show coverage the real register
    does not have."""
    from kavach.webui import demo_register

    payload = build_payload(demo_register())
    assert payload["verifiability"]["percent"] < 60
    assert payload["totals"]["certain_errors"] > 0
    assert payload["totals"]["unverifiable"] > payload["totals"]["certain_errors"]
