# Kavach — Phase 1: the validation harness and rules engine

Validation layer for Indian land records (SIH26018). This repository contains
**Phase 1 only**: the schema, exact area arithmetic, the synthetic generator, the
mutation engine, and the finding contract. No OCR, no model, no GPU, no UI, no API.

Everything here runs on a laptop in about a second.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/      # 240 tests
.venv/bin/python -m kavach.report      # what is actually true right now
```

## What is built

| Module | What it is |
|---|---|
| `kavach/units.py` | Exact area arithmetic. Areas are `Fraction` counts of a ladder's smallest unit and carry their ladder's identity. Cross-ladder conversion needs a declared exact rational or it refuses. |
| `kavach/ladders.json` | Seven unit ladders as data. Anchored ones are exactly inter-convertible; the bigha ladders are not, and say so. |
| `kavach/records.py` | The canonical model. Two spines joined by a many-to-many `Holding`; validity intervals on everything; `is_leaf` derived from an as-of date. |
| `kavach/classifications.json` | Tenure taxonomy as data, each class tagged `sourced` / `disputed` / `unsourced`. |
| `kavach/findings.py` | `Finding`, the four finding classes, the pure-rule contract, and the engine. |
| `kavach/synthetic.py` | Mouza generator where every invariant holds by construction, plus an independent invariant checker. |
| `kavach/mutations.py` | Twelve named corruptions with their expected findings, and precision / recall / localisation scoring. |
| `kavach/report.py` | Prints the harness state. Prints `None` where nothing has been measured. |

## What is not built

Classes 1, 2, 3 and 8 — the actual rules. That is the next step, and the harness
exists so they can be measured the moment they land. Classes 4–7 are blocked on
external data and have no interfaces yet.

## The four invariants everything else rests on

1. **No inexact numbers on any area or share path.** Enforced by an AST scan over
   every module in the package, which bans float literals, the `float` name, the `/`
   operator, and inexact imports. Mutation-tested.
2. **Rules are pure.** `rule(view) -> findings`. No I/O, no globals, no config reads.
3. **`UNVERIFIABLE` is not a pass.** A rule with no witness, no supplied view, or an
   uncaught exception abstains and names what it lacked.
4. **Flag, never verdict.** Nothing decides a record is wrong or that title is
   defective. A finding says which rule fired, on which record, with what evidence.

## Documents

* `AGENTS.md` — how to work on this. Authoritative.
* `HANDOFF_BUILD.md` — what the system is. Authoritative.
* `SCHEMA.md` — the settled data model and the rulings behind it.
* `EVIDENCE.md` — sourced facts with citations, kept separate from decisions.

Where `SCHEMA.md` and `EVIDENCE.md` disagree with an older pitch document, these win.
No count, threshold, or measurement may be copied out of a pitch document into code.
