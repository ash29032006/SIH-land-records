"""Harness report — prints what is actually true right now.

`python -m kavach.report`

AGENTS.md 7 asks for precision and recall to be **measured and printed, whatever
they are**. No rule classes ship yet, so the honest printed value for those is
`None`, and this says so rather than borrowing a number from a test double. The
moment Classes 1-3 land, the same command produces real figures with no edits here.

What it can report today is real: the generator's invariant status, the mutation
catalogue with what each corruption actually breaks, and witness availability across
document profiles — which is the shape Class 8's verifiability rate will take.
"""

from __future__ import annotations

import sys
from fractions import Fraction

from kavach.classifications import default_schemes
from kavach.findings import Engine
from kavach.mutations import MUTATIONS, all_mutation_cases, apply_mutation, summarise
from kavach.records import RecordSet
from kavach.synthetic import (
    DocumentProfile,
    MouzaSpec,
    synthetic_mouza,
    verify_synthetic_invariants,
)
from kavach.units import default_registry

# No rule classes are implemented yet (AGENTS.md 5, steps 3-6).
SHIPPED_RULES: tuple = ()

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

    _heading("Engine")
    engine = Engine(SHIPPED_RULES)
    clean_result = engine.run(clean, registry, as_of=clean.as_of)
    results = [
        engine.run(case.mutated, registry, as_of=case.mutated.as_of) for case in cases
    ]
    score = summarise(cases, results, clean_result)

    print(f"  rule classes implemented   {len(SHIPPED_RULES)}")
    print(f"  findings on clean input    {len(clean_result)}")
    print(f"  false positives on clean   {len(clean_result.certain_errors)}")
    print()
    print(score.report())
    print()
    if not SHIPPED_RULES:
        print("  recall, localisation and precision are None because no rule class is")
        print("  implemented yet — not because they were measured and came out empty.")
        print("  Implement Classes 1, 2, 3 and 8, register them in SHIPPED_RULES, and")
        print("  this command prints real numbers with no other change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
