# Kavach — validation layer for Indian land records

India's land records are single-entry bookkeeping: every mutation touches one book and
nothing has to balance. Kavach adds the second entry. It cross-examines each field
against other independent records of the same land, and because **land is conserved**,
records that violate that conservation are provably wrong with **no ground truth, no
annotator and no model**.

This repository is **Phase 1**: the schema, exact area arithmetic, the rules engine,
the synthetic generator and the mutation harness. No OCR, no VLM, no GPU, no API, no
UI. The whole suite runs on a laptop in about two seconds.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/      # 595 tests
.venv/bin/python -m kavach.report      # the measured figures
```

## Measured, not asserted

Every figure below comes from `python -m kavach.report`. Nothing in the codebase
hardcodes a result, and `None` appears wherever nothing was measured.

| | |
|---|---|
| rules implemented | **37** — 9 grammar, 11 conservation, 12 completeness, 1 census, 4 blocked interfaces |
| corruptions in the harness | **24**, each grounded in a cited document |
| detected | **24 / 24** |
| localised to the right record | **24 / 24** |
| **false positives on clean input** | **0** |
| precision | 1 |
| propagation | ~2 findings per corruption (reviewer load, not error) |
| tests | 595 |

The false-positive figure is the one that matters. A rule that fires on a correct
record costs a family money, so `test_no_rule_ever_fires_on_a_record_set_that_is_correct_by_construction`
runs the whole engine over sixty randomly shaped mouzas — different sizes, depths,
document profiles and four unit ladders — and requires silence from all of them.

### Verifiability rate — the output nobody has

Class 8 is not a check. It counts, per parcel, how many checks *could* run at all
against a fixed list of twelve named witnesses. It is **a rate, not an error rate**,
and it is computable when every other class abstains.

| document profile | verifiability rate |
|---|---|
| khatian (classification and shares, no per-holding areas) | 35/43 (~81%) |
| jamabandi (per-holding areas, no shares, no classification) | 193/433 (~44%) |
| combined (both lineages reconciled) | 1 (~100%) |

The jamabandi figure is the one that matters: it is the *de facto* record of rights in
Bihar, and **less than half** of what the engine could check has a witness in it.
Reconciling it against the khatian — the older lineage — is what takes coverage from
44% to complete. That gap is the argument for the whole system.

A witness that cannot structurally exist for a parcel (a root has no parent; a leaf has
no sub-plots) is excluded from its denominator rather than counted as missing, so a
parcel is never penalised for its own shape.

## What research changed

Three schema decisions were corrected by reading the Department of Land Resources' own
*Evaluation of Quality of Land Records — Bihar*. All citations are in
[`EVIDENCE.md`](EVIDENCE.md).

- **One survey number, many jamabandis.** Partition in Bihar is textual, not spatial.
  `Holding` is many-to-many, and that is sourced rather than inferred (E1).
- **Shares are not recorded.** Jamabandis with multiple owners state no shares at all,
  so Class 2's co-owner check *abstains* on real input rather than passing (E2).
- **The audit ladder is acre/decimal, not bigha/katha/dhur.** The digitised RoR records
  rakba in acres, decimal and hectares (E4).
- **One free check neither build document names.** Rakba is written three times in three
  unit systems on the same row — a second witness inside a single record, exact because
  a hectare written to four decimals is a whole number of square metres (E10).

One rule in the spec is **deliberately not implemented**: "duplicate khata per owner".
One person legitimately holds several khatas in Bihar, so it would have produced false
positives at scale. See [`RULES.md`](RULES.md).

## Layout

| Path | What |
|---|---|
| `kavach/units.py` | Exact area arithmetic. `Fraction` counts, ladder identity on every area, cross-ladder conversion that refuses without a declared exact rational. |
| `kavach/ladders.json` | Nine unit ladders as data, each stating where its bases come from. |
| `kavach/records.py` | The canonical model. Two spines joined by a m:n `Holding`, validity on everything, `is_leaf` derived from an as-of date. |
| `kavach/findings.py` | The finding contract, the rule decorator, the engine. |
| `kavach/rules/` | Classes 1, 2, 3, 8 implemented, including the one ACROSS_VERSION rule; 4–7 as interfaces that abstain. |
| `kavach/synthetic.py` | Generator where every invariant holds by construction, plus an independent checker. |
| `kavach/mutations.py` | 24 corruptions with expected findings, and the scoring. |
| `kavach/report.py` | Prints what is true. `None` where nothing was measured. |
| `tests/golden/` | 27 fixtures that regenerate byte for byte. |

## The four invariants everything rests on

1. **No inexact numbers on any area or share path.** An AST scan over every module bans
   float literals, the `float` name, the `/` operator, inexact imports and
   float-returning `random` methods. Mutation-tested: seven injected floats, seven caught.
2. **Rules are pure.** `rule(view) -> findings`. No I/O, no globals, no config reads.
3. **`UNVERIFIABLE` is not a pass.** A rule with no witness, no supplied view, or an
   uncaught exception abstains and names what it lacked. A test asserts every rule has
   a fixture proving it.
4. **Flag, never verdict.** Nothing decides a record is wrong or that title is defective.
   A test asserts no rule is even *named* as a verdict.

## What is not built

Classes 4–7 have interfaces and no bodies; each names the external fact it lacks.
Layers A, B, D, E, F and G — ingest, reading, scoring, review, platform and learning —
are later phases and are deliberately absent.

## Documents

- [`AGENTS.md`](AGENTS.md) — how to work on this. Authoritative.
- [`HANDOFF_BUILD.md`](HANDOFF_BUILD.md) — what the system is. Authoritative.
- [`SCHEMA.md`](SCHEMA.md) — the settled model and the rulings behind it.
- [`EVIDENCE.md`](EVIDENCE.md) — sourced facts with citations, separate from decisions.
- [`RULES.md`](RULES.md) — generated from the registry; a test fails if it drifts.
