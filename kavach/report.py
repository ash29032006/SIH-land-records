"""Harness report — prints what is actually true right now.

`python -m kavach.report`

AGENTS.md 7 asks for precision and recall to be **measured and printed, whatever
they are**. They are measured here against the mutation set, and printed unrounded.
Nothing in this file hardcodes a result; every figure comes from running the engine.

`None` still appears wherever nothing was measured, and it means exactly that.
"""

from __future__ import annotations

import sys
from fractions import Fraction

from kavach.classifications import default_schemes
from kavach.findings import Engine
from kavach.mutations import MUTATIONS, all_mutation_cases, score_case, summarise
from kavach.records import RecordSet
from kavach.synthetic import (
    DocumentProfile,
    MouzaSpec,
    synthetic_mouza,
    verify_synthetic_invariants,
)
from kavach.units import default_registry

from kavach.rules import (
    ALL_RULES,
    BLOCKED_RULES,
    CENSUS_RULES,
    COMPLETENESS_RULES,
    CONSERVATION_RULES,
    GRAMMAR_RULES,
)
from kavach.rules.census import witness_census

SHIPPED_RULES: tuple = ALL_RULES

REPORT_SEED = 11
MUTATION_SEED = 3


def _rule(text: str) -> str:
    return "-" * len(text)


def _heading(text: str) -> None:
    print()
    print(text)
    print(_rule(text))


def _witnesses(records: RecordSet) -> dict[str, str]:
    """Which checks *could* run on this record set. Not a rule; a count of witnesses."""
    index = records.index(records.as_of)
    holdings = records.holdings
    memberships = records.memberships
    khesras = records.khesras

    def ratio(hits: int, total: int) -> str:
        if total == 0:
            return "n/a"
        percent = (100 * hits) // total
        return f"{hits}/{total} ({percent}%)"

    return {
        "mouza total stated": "yes" if records.mouza.area_stated else "NO",
        "tenure subtotals stated": (
            f"{len(records.mouza.tenure_totals)} classes"
            if records.mouza.tenure_totals
            else "NO"
        ),
        "parcels with a stated area": ratio(
            sum(1 for k in khesras if k.area_stated), len(khesras)
        ),
        "parcels with a written form": ratio(
            sum(1 for k in khesras if k.area_stated and k.area_stated.as_written),
            len(khesras),
        ),
        "parcels with a cross-unit restatement": ratio(
            sum(1 for k in khesras if k.area_restatements), len(khesras)
        ),
        "parcels classified": ratio(sum(1 for k in khesras if k.tenure), len(khesras)),
        "holdings with a claimed area": ratio(
            sum(1 for h in holdings if h.area_claimed), len(holdings)
        ),
        "holdings with a share": ratio(
            sum(1 for h in holdings if h.share is not None), len(holdings)
        ),
        "co-owner shares recorded": ratio(
            sum(1 for m in memberships if m.share is not None), len(memberships)
        ),
        "records of undetermined validity": str(
            len(index.unknown_khesras)
            + len(index.unknown_khatas)
            + len(index.unknown_holdings)
            + len(index.unknown_memberships)
        ),
    }


def main() -> int:
    registry = default_registry()
    schemes = default_schemes()

    print("KAVACH — Phase 1 harness report")
    print("=" * 34)
    print("Everything below is generated from synthetic fixtures and labelled as such.")
    print("No figure here is a measurement of any real corpus.")

    # -- reference data -----------------------------------------------------

    _heading("Unit ladders (data, not code)")
    for ladder_id in registry.ids():
        ladder = registry.get(ladder_id)
        anchor = "anchored" if ladder.is_anchored else "UNANCHORED — refuses conversion"
        print(f"  {ladder_id:22} {' / '.join(ladder.units):28} {anchor}")

    _heading("Classification schemes")
    for scheme_id in schemes.ids():
        scheme = schemes.get(scheme_id)
        disputed = ", ".join(scheme.disputed_codes) or "none"
        print(f"  {scheme_id:22} {len(scheme.tenure_codes)} tenure classes")
        print(f"  {'':22} disputed (do not cite): {disputed}")
        print(f"  {'':22} land-use classes: {len(scheme.land_use)}")

    # -- the generator ------------------------------------------------------

    _heading("Synthetic generator — invariants hold by construction")
    cleans: dict[DocumentProfile, RecordSet] = {}
    for profile in DocumentProfile:
        records = synthetic_mouza(MouzaSpec(seed=REPORT_SEED, profile=profile))
        cleans[profile] = records
        index = records.index(records.as_of)
        violations = verify_synthetic_invariants(records, registry, schemes)
        status = "CLEAN" if not violations else f"{len(violations)} VIOLATIONS"
        print(
            f"  {profile:10} khesras={len(records.khesras):3} "
            f"leaves={len(index.leaves()):3} khatas={len(records.khatas):3} "
            f"holdings={len(records.holdings):3} owners={len(records.owners):3}  {status}"
        )
        for violation in violations:
            print(f"      ! {violation}")

    # -- witness availability ------------------------------------------------

    _heading("Witness availability by document profile")
    print("  What each profile makes checkable at all. This is the shape Class 8's")
    print("  verifiability rate will take; it is not yet that rate.")
    print()
    labels = list(_witnesses(cleans[DocumentProfile.COMBINED]))
    header = f"  {'witness':38}" + "".join(f"{p:>15}" for p in DocumentProfile)
    print(header)
    print("  " + "-" * (len(header) - 2))
    per_profile = {p: _witnesses(r) for p, r in cleans.items()}
    for label in labels:
        row = f"  {label:38}" + "".join(
            f"{per_profile[p][label]:>15}" for p in DocumentProfile
        )
        print(row)

    # -- mutation catalogue --------------------------------------------------

    _heading("Mutation catalogue")
    clean = cleans[DocumentProfile.COMBINED]
    cases = all_mutation_cases(clean, registry, seed=MUTATION_SEED)
    print(f"  {len(cases)} of {len(MUTATIONS)} mutations apply to this mouza.")
    print()
    print(f"  {'mutation':30}{'breaks':>8}  expected finding")
    print("  " + "-" * 76)
    for case in cases:
        expected = ", ".join(
            f"C{e.validation_class}/{e.finding_class}" for e in case.expected
        )
        broken = len(case.broken_invariants)
        marker = " " if bool(broken) is case.breaks_invariants else "!"
        print(f" {marker}{case.name:30}{broken:>8}  {expected}")
    print()
    print("  'witness_removed' breaking zero invariants is correct: the absence of a")
    print("  witness is not an error, and only a witness census can see it.")

    # -- what is measured, and what is not -----------------------------------

    _heading("Rules registered")
    for label, group in (
        ("Class 1 grammar", GRAMMAR_RULES),
        ("Class 2 conservation", CONSERVATION_RULES),
        ("Class 3 completeness", COMPLETENESS_RULES),
        ("Class 8 census", CENSUS_RULES),
        ("Classes 4-7 blocked", BLOCKED_RULES),
    ):
        print(f"  {label:24} {len(group):>3}")
    print(f"  {'TOTAL':24} {len(SHIPPED_RULES):>3}")

    # -- the false-positive guard -------------------------------------------

    _heading("Clean input — every finding here would be a false positive")
    engine = Engine(SHIPPED_RULES)
    clean_results = {}
    for profile, record_set in cleans.items():
        result = engine.run(
            record_set, registry, as_of=record_set.as_of, schemes=schemes
        )
        clean_results[profile] = result
        print(
            f"  {profile:10} findings={len(result):3}  "
            f"CERTAIN_ERROR={len(result.certain_errors):3}  "
            f"abstentions={len(result.abstentions):3}"
        )
        for finding in result.certain_errors[:5]:
            print(f"      FALSE POSITIVE: {finding}")

    # -- the witness census --------------------------------------------------

    _heading("Class 8 — verifiability rate")
    for profile, record_set in cleans.items():
        result = witness_census(record_set, registry, record_set.as_of)
        rate = result.verifiability_rate
        shown = "None"
        if rate is not None:
            percent = (100 * rate.numerator) // rate.denominator
            shown = f"{rate} (~{percent}%)"
        print(
            f"  {profile:10} parcels={len(result.parcels):3}  "
            f"unexaminable={len(result.unexaminable):3}  rate={shown}"
        )
    print()
    print("  A rate, not an error rate. It says how much of the register can be")
    print("  independently checked at all — the number the department does not have.")

    # -- measured precision and recall ---------------------------------------

    _heading("Mutation harness — measured")
    clean_result = clean_results[DocumentProfile.COMBINED]
    results = [
        engine.run(case.mutated, registry, as_of=case.mutated.as_of, schemes=schemes)
        for case in cases
    ]
    for case, result in zip(cases, results):
        marker = "hit " if score_case(case, result).localised else "MISS"
        print(
            f"  {marker} {case.name:30} "
            f"certain_errors={len(result.certain_errors):3}"
        )
    print()
    print(summarise(cases, results, clean_result).report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
