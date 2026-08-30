# AGENTS.md — Kavach (SIH26018)

Validation layer for Indian land records. You are building the **harness and rules
engine first**, before any OCR, model, or UI. Read `HANDOFF_BUILD.md` for what the
system is. This file is how you work.

---

## 1. How to work with Ashwin

- **Never open with agreement.** First sentence challenges the assumption, names what
  is missing, or asks the question that exposes the gap.
- **Tag claims:** `[Certain]` (verified — you ran it, or it is in a doc here) ·
  `[Likely]` (strong inference) · `[Guessing]` (filling gaps). If mostly guessing, say
  so first.
- **Uncomfortable truth first line, not paragraph three.**
- **Disagree with structure:** "I disagree because [reason]. Here's what I'd do instead
  [alternative]. The risk in your approach is [specific downside]."

- **End every substantive response with a summary.** Without being asked.

---

## 2. The one rule that protects the whole project

**Never fabricate a measurement.** Not an accuracy number, not a rule-hit rate, not a
confidence figure, not a placeholder that looks like a result.

The entire pitch is *"stop shipping systems that assert things they cannot back up."*
Code that hardcodes a plausible number, or a test that asserts a made-up threshold,
destroys the only thing this project has.

If a number is not measured, it is `None` and the code says so. An honest 0.61 beats
an invented 0.95 the moment anyone asks which records.

**Corollary:** no `# TODO: real value` constants that ship. No demo data that is not
clearly labelled synthetic. Synthetic fixtures are fine and necessary — they must be
named `synthetic_*` and never presented as measurement.

---

## 3. Non-negotiable engineering invariants

These are design decisions already settled. Do not undo them without new evidence.

### 3.1 Area is an exact integer. Never a float.
Bihar units are base-20: `1 bigha = 20 katha`, `1 katha = 20 dhur`. Conservation checks
are **exact equality over sums**. Floats produce spurious violations that look like
findings.

- Store all area as `int` in the **smallest unit (dhur)**, or as `fractions.Fraction`.
- Convert to display units only at the presentation boundary.
- Any `float` in an area code path is a bug. Add a test that asserts it.
- Different states use different ladders (kanal-marla base-20, acre-guntha). The unit
  system is data, not hardcoded constants.

### 3.2 Rules are pure functions
`rule(records) -> list[Finding]`. No I/O, no network, no database, no globals, no
config reads inside a rule. A rule takes data and returns findings. This is what makes
the engine testable without any of the pipeline existing.

### 3.3 Every finding is typed, never boolean
```
CERTAIN_ERROR   grammar or conservation violated — no judgement involved
CONFLICT        two witnesses disagree — precedence rule, else human
ANOMALY         statistical outlier — directs sampling, never a finding alone
UNVERIFIABLE    no second witness exists — abstain, and say so
```
`UNVERIFIABLE` is not an error state. It is a first-class output and arguably the
product. A rule that cannot run because a witness is missing **must** emit
`UNVERIFIABLE`, never silently pass.

### 3.4 Flag, never verdict
No function is named `is_fraud`, `is_wrong`, `detect_forgery`. A record of rights does
not establish title. Output is always "this warrants review," with the rule that fired
and the record that disagrees. This is a legal constraint, not a stylistic one.

### 3.5 The witness census counts what was *possible*
Class 8 is not a check. For each parcel it records how many checks could run at all.
This produces the verifiability rate — the project's distinctive output. It must be
computable when every other class abstains.

### 3.6 D1 and D5 are the same rules in two roles
Rules as **features** feeding the model; rules as **hard gates** overriding it. One
implementation, two call sites, both named explicitly. Never two copies.

---

## 4. Testing — the harness is the deliverable

The harness is not scaffolding for the real work. **It is the first real work.**

### 4.1 Mutation testing is the core strategy
This is the project's own thesis applied to its own test suite:

1. **Generate** a synthetic mouza where all invariants hold *by construction* —
   areas sum, sequences are complete, no duplicates.
2. **Assert** the engine returns zero `CERTAIN_ERROR` findings. Any finding here is a
   false positive, and false positives cost a family money.
3. **Mutate** exactly one field with a known corruption (set a sub-division to 0, add
   1 dhur to one plot, delete a sequence member, duplicate a khata).
4. **Assert** the engine finds exactly that corruption — right parcel, right class.

This measures precision and recall **with no labelled data and no annotator**, which is
the same argument the pitch makes about the rules generating their own ground truth.
If the harness cannot do it, the pitch cannot claim it.

### 4.2 Every rule ships with three fixtures
- one that **violates** it (expect a finding)
- one that **passes** it (expect none — this is the false-positive guard)
- one where the **witness is missing** (expect `UNVERIFIABLE`, not a pass)

A rule without all three is not done.

### 4.3 Property-based tests where the invariant is arithmetic
Use `hypothesis` for conservation and unit arithmetic. Round-trip property: any area
converted to display units and back is unchanged. Sum property: partitioning a parcel
and re-summing returns the original exactly.

### 4.4 What not to test
Do not write tests for OCR accuracy, model output, or anything requiring a GPU. Those
belong to a later phase and will not exist for weeks.

---

## 5. Build order — do not skip ahead

1. **Schema + unit arithmetic** (`records.py`, `units.py`) + their tests
2. **Harness**: synthetic mouza generator, mutation engine, finding assertions
3. **Class 1 Grammar** — cheapest, certain, no dependencies
4. **Class 2 Conservation** — the core, exact integer arithmetic
5. **Class 3 Completeness**
6. **Class 8 Witness census** → verifiability rate
7. *Stop.* Steps 1–6 need no model, no GPU, no portal, no annotator, and produce a
   demoable artifact. Everything downstream depends on external facts not yet verified.

Classes 4–7 (chain, geometry, cross-system, statistical) are **specced but blocked** on
external data. Write their interfaces so they abstain cleanly; do not implement bodies.

---

## 6. Stack

Python 3.11+ · `pytest` · `hypothesis` · `pydantic` (schema) · `pandas` (bulk records)
· stdlib `fractions`. FastAPI and React come later and are not this phase.

Keep dependencies minimal. Everything in steps 1–6 should run on a laptop with no GPU.

---

## 7. Definition of done for this phase

- [ ] Schema pins every field in `HANDOFF_BUILD.md` §3 with types
- [ ] Area arithmetic is exact; a test proves floats are absent from area paths
- [ ] Synthetic mouza generator produces zero findings on clean input
- [ ] Mutation engine: N known corruptions, engine localises each to the right parcel
- [ ] Classes 1, 2, 3, 8 implemented, each with three fixtures
- [ ] Precision/recall on the mutation set is **measured and printed** — whatever it is
- [ ] `verifiability_rate(records)` runs and returns a real number
- [ ] Rules 4–7 have interfaces that return `UNVERIFIABLE`, no bodies

The last three lines are the demo. Nothing above them requires anything you don't have.

---

## 8. Things that will waste your time — don't

- Building the dashboard, API, RBAC, or repository (Layer F). Scored, but slideware.
- Implementing conformal prediction. Cannot certify a tight bound at the sample size
  available. Ship the risk–coverage curve later, not a certified bound.
- Adding validation classes. Seven is more than will be demoed.
- Kaithi/Modi/Urdu script work. Cut, for reasons in the pitch docs.
- Feeding OCR text into the evidence path. It silently destroys the confidence signal —
  see `HANDOFF_BUILD.md` §6. Relevant later; noted now so it is never wired wrong.
