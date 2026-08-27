"""Golden files — HANDOFF_BUILD.md 5.3.

Clean and mutated mouzas are serialised under version control so results are
reproducible across sessions and machines. These tests fail if the generator or the
mutation engine changes behaviour, which is the point: a harness whose fixtures drift
silently cannot measure anything.

Regenerating deliberately is fine. Regenerating by accident is what this catches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import assert_exact

from kavach.mutations import all_mutation_cases
from kavach.records import RecordSet
from kavach.synthetic import (
    DocumentProfile,
    MouzaSpec,
    synthetic_mouza,
    verify_synthetic_invariants,
)
from kavach.units import default_registry

GOLDEN = Path(__file__).parent / "golden"
MANIFEST = json.loads((GOLDEN / "MANIFEST.json").read_text(encoding="utf-8"))
GOLDEN_SEED = MANIFEST["golden_seed"]
MUTATION_SEED = 3
REG = default_registry()


def _clean(profile: DocumentProfile) -> RecordSet:
    return synthetic_mouza(MouzaSpec(seed=GOLDEN_SEED, profile=profile))


@pytest.mark.parametrize("profile", list(DocumentProfile))
def test_clean_golden_files_regenerate_byte_for_byte(profile):
    path = GOLDEN / f"clean.{profile}.json"
    assert path.read_text(encoding="utf-8") == _clean(profile).model_dump_json(indent=2)


@pytest.mark.parametrize(
    "name", sorted(k for k, v in MANIFEST["files"].items() if v["kind"] == "mutated")
)
def test_mutated_golden_files_regenerate_byte_for_byte(name):
    entry = MANIFEST["files"][name]
    cases = {
        c.name: c
        for c in all_mutation_cases(
            _clean(DocumentProfile.COMBINED), REG, seed=MUTATION_SEED
        )
    }
    case = cases[entry["mutation"]]
    assert (GOLDEN / name).read_text(encoding="utf-8") == case.mutated.model_dump_json(
        indent=2
    )


@pytest.mark.parametrize("name", sorted(MANIFEST["files"]))
def test_every_golden_file_loads_and_is_exact(name):
    records = RecordSet.model_validate_json(
        (GOLDEN / name).read_text(encoding="utf-8")
    )
    assert_exact(records, name)


@pytest.mark.parametrize(
    "name", sorted(k for k, v in MANIFEST["files"].items() if v["kind"] == "clean")
)
def test_clean_golden_files_hold_every_invariant(name):
    records = RecordSet.model_validate_json(
        (GOLDEN / name).read_text(encoding="utf-8")
    )
    assert verify_synthetic_invariants(records, REG) == ()


@pytest.mark.parametrize(
    "name", sorted(k for k, v in MANIFEST["files"].items() if v["kind"] == "mutated")
)
def test_mutated_golden_files_break_exactly_what_the_manifest_records(name):
    entry = MANIFEST["files"][name]
    records = RecordSet.model_validate_json(
        (GOLDEN / name).read_text(encoding="utf-8")
    )
    broken = verify_synthetic_invariants(records, REG)
    assert bool(broken) is entry["breaks_invariants"]
    assert len(broken) == entry["broken_invariant_count"]


def test_the_manifest_covers_every_file_on_disk():
    on_disk = {p.name for p in GOLDEN.glob("*.json")} - {"MANIFEST.json"}
    assert on_disk == set(MANIFEST["files"])
