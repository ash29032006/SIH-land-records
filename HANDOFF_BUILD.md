# Kavach — Build Handoff (Claude Code)

**SIH26018 · Intelligent Land Record Digitization and Validation System · DoLR**
**Phase 1: the validation harness and rules engine. Written 27 Aug 2026.**

> This is a **build** document. Pitch material, deck geometry, competition strategy and
> evidence citations live in separate files and are deliberately not repeated here —
> they change what you write in a slide, not what you write in a module.
> Read `AGENTS.md` first; it governs how you work and contains the invariants.

---

## 1. What this system is, in one paragraph

India's land records are **single-entry bookkeeping**: every mutation touches one book
and nothing has to balance. 95% of villages are computerised, but computerisation
measured how much was *typed*, never whether it was typed *right* — and the national
auditor found large-scale divergence between paper and digital registers as a result.
Kavach adds the second entry. It cross-examines each field against other independent
records of the same land, and because **land is conserved** — a village's total area
has not changed since the settlement survey — records that violate that conservation
are **provably wrong with no ground truth, no annotator and no model**.

That last sentence is the entire reason the harness comes first. The rules generate
their own labels. You do not need data to start.

---

## 2. Why the harness is phase 1

`[Certain]` Classes 1–3 and 8 of the validation engine need **no OCR, no GPU, no
portal access, and no annotator**. They are arithmetic and set operations over tabular
records. Every other part of the system depends on external facts that are currently
unverified (see §8).

So the build order runs by dependency, not by the pipeline's reading order:

```
schema + units  →  harness  →  C1 C2 C3 C8  →  [demoable artifact]
                                                    ↓
                              everything model-shaped, later
```

Everything that can go wrong — OCR quality, VLM behaviour, GPU availability,
annotator agreement, portal access — lives **downstream** of that artifact.

---

## 3. The data model (write this first — it does not exist yet)

No prior document specifies this. Pin it now; every rule depends on it.

### 3.1 Hierarchy
```
Mouza (village)          — has a total area from the settlement survey
 └─ Khata (holding)      — has a stated total area; belongs to owner(s)
     └─ Khesra / Plot    — the atomic parcel; has area + classification
         └─ Sub-division — 217/1, 217/2 …  numbering starts at 1, never 0
```

### 3.2 Fields (the PS-mandated set)
The problem statement names these. **Count them yourself before printing a number
anywhere** — an earlier draft printed a field count that did not match the list.

`landowner details` · `survey number` · `khasra number` · `khata number` ·
`plot area` · `village` · `tehsil` · `district` · `land classification` ·
`mutation records` · `registration info`

Note: naming is regional. *khasra / khesra / survey number* overlap; *khata / patta*
overlap. Model the concept, alias the names — do not create parallel fields.

### 3.3 Required properties on every value
Every extracted field carries, from the start:
- `value`
- `provenance` — which document, which page, which cell
- `confidence` — `None` until a real model produces one. **Never a placeholder float.**
- `witnesses` — which other records were available to check it against

`witnesses` is what makes Class 8 computable and must exist before any rule is written.

### 3.4 Land classification
At minimum: `raiyati` (private) vs `gairmazrua` (government), plus land-use categories.
Class 2 requires that `raiyati_total + gairmazrua_total == mouza_total`. This is the
check that would have caught 3.22 lakh misclassified parcels arithmetically.

### 3.5 Units — get this right or everything downstream is noise
```
Bihar:   1 bigha = 20 katha,  1 katha = 20 dhur
Punjab:  1 acre  = 8 kanal,   1 kanal = 20 marla
Deccan:  1 acre  = 40 guntha
```
- Unit ladders are **data**, loaded per region. Not hardcoded.
- Internally, area is an **integer count of the smallest unit**, or a `Fraction`.
- **Never float.** Conservation is exact equality; floats manufacture violations.
- Un-normalised values are themselves a finding: "27 katha" in a base-20 ladder is a
  transcription artefact — it should have carried to 1 bigha 7 katha. `[Certain]` This
  check exists in no incumbent system and is nearly free to implement.

---

## 4. The rules to build now

### Class 1 — Grammar (`free · certain · needs nothing`)
The field is its own witness. A violation is certain.

| Rule | Catches |
|---|---|
| Sub-division numbering starts at 1, never 0 | a real audit found 910 such violations |
| Charset: khasra is digits + separator only | `2l7` misread for `217` |
| Unit carry: no component ≥ its ladder base | "27 katha" un-normalised |
| Date ordering: mutation date ≥ survey date | impossible chronology |
| Field-type conformance per column | text value in a numeric column |

### Class 2 — Conservation (`the double-entry core`)
Exact integer equality. This is the heart of the system.

- Sub-plot areas sum to parent plot area
- Co-owner shares sum to exactly 1 (use `Fraction`, never float)
- Σ khesra areas in a khata == stated khata total
- **Σ all khata areas in a mouza == mouza total** ← the trial balance
- `raiyati_total + gairmazrua_total == mouza_total`
- Parent area at T == Σ child areas at T+1

**Tolerance policy — decide explicitly and document it.** Exact equality is correct for
integer dhur. If a real corpus later forces a tolerance, it must be a declared
parameter with a stated justification, never a magic epsilon buried in a comparison.

### Class 3 — Completeness
- Khesra uniqueness within a mouza
- Sub-division sequence gaps (217/1 and 217/3 exist — where is 217/2?)
- No orphan khesra (belongs to no khata); no empty khata
- One plot, one classification
- Duplicate khata per owner

### Class 8 — Witness census (not a check)
For each parcel, count how many classes *could* run given the records present. Produces
`verifiability_rate` — the fraction of records that can be independently checked at
all. **This is the output the department does not have.** It is a rate, not an error
rate, and it is computable over public records with no OCR.

### Classes 4–7 — interfaces only, no bodies
`4 chain continuity` (needs two versions of a record) · `5 text-vs-geometry` (needs
cadastral polygons) · `6 cross-system` (needs registration/revenue data) ·
`7 statistical` (Benford, clustering — needs corpus scale).

Each must return `UNVERIFIABLE` cleanly when its inputs are absent. Do not stub them
as passing — a rule that cannot run has not passed.

---

## 5. The harness

### 5.1 Synthetic mouza generator
Produce a mouza where **every invariant holds by construction**: areas partition
exactly, sequences are gapless, classifications sum, no duplicates. Parameterise size,
unit system, and sub-division depth.

**First assertion of the whole project:** engine over clean input returns zero
`CERTAIN_ERROR`. Any finding here is a false positive, and the pitch commits publicly
to the cost of false flags. This test protects that commitment.

### 5.2 Mutation engine
Apply exactly one known corruption to a clean mouza. Each mutation is a named,
reproducible transformation with a recorded expected finding:

| Mutation | Expected |
|---|---|
| set a sub-division number to 0 | Class 1 · CERTAIN_ERROR · that parcel |
| add 1 dhur to one plot | Class 2 · CERTAIN_ERROR · that khata |
| delete a sequence member | Class 3 · CERTAIN_ERROR · that sequence |
| duplicate a khata for one owner | Class 3 · CERTAIN_ERROR · that owner |
| flip one parcel raiyati→gairmazrua | Class 2 · CERTAIN_ERROR · mouza totals |
| write "27 katha" un-normalised | Class 1 · CERTAIN_ERROR · that field |
| remove a witness record | Class 8 · UNVERIFIABLE · not an error |

Then measure: **precision, recall, and localisation accuracy** (did it name the right
parcel, not merely the right village). Print the real numbers. Whatever they are.

`[Likely]` This is also the strongest demo asset available before any data exists: it
shows the engine catching errors and, more importantly, *not* firing on clean records.

### 5.3 Golden files
Serialise clean and mutated mouzas as fixtures under version control so results are
reproducible across sessions and machines.

---

## 6. Design decisions that must not be undone

1. **Area never float.** §3.5.
2. **Rules pure.** No I/O inside a rule.
3. **UNVERIFIABLE is not a pass.** Missing witness must be visible in output.
4. **Flag, never verdict.** No function asserts fraud or wrongness of title.
5. **D1 and D5 are one rule engine in two roles** — features and gates. One
   implementation, two call sites, both named.
6. **Queue order is consequence × uncertainty**, never ascending confidence. Relevant
   when Layer E is built; recorded here so it is not re-derived wrongly.
7. **Later, in Layer B: the evidence path must never see OCR text.** Reader B given the
   OCR output will agree with itself, and cross-reader agreement silently degenerates
   into self-agreement while still computing a plausible number. Value path = image +
   OCR text. Evidence path = image only, K views. Not this phase — but wiring it wrong
   later destroys the confidence layer invisibly.
8. **Rules mint only negatives.** A violation is a certain wrong answer; passing all
   rules means "no witness disagreed," not "correct." Positive labels come from human
   review decisions (Layer E) fed back to the model (Layer G). Do not train anything on
   rule output alone — it is one-class.

---

## 7. What the pipeline looks like overall

Seven layers. Only C (and the harness under it) is in scope now.

| Layer | What | Phase |
|---|---|---|
| **A Ingest** | restore · type · route · script ID · abstain-router | later |
| **B Read** | table detect · Reader A (OCR) · value path · evidence path | later |
| **C Validate** | 7 rule classes + witness census · runs forward AND backward | **NOW** |
| **D Score** | rules-as-features → model → calibration → rules-as-gates | later |
| **E Review** | queue by consequence × uncertainty · capture decisions | later |
| **F Platform** | repository · audit · dashboards · APIs · RBAC | slideware |
| **G Learn** | corrections → labels → retrain | later |

**Forward vs backward:** the identical rule engine runs forward as an extraction gate on
new scans, and backward as an audit of records already digitised. The backward run is
how you demonstrate the engine works *before the forward pipeline processes anything* —
which is exactly why phase 1 is worth building alone.

See `kavach_pipeline_v6.svg` for the graph.

---

## 8. Open questions that gate later phases

None of these block phase 1. All of them block something later.

| # | Question | Blocks |
|---|---|---|
| 1 | Does the state cadastral portal serve historical + current survey layers for a real non-pilot village? | Class 5 entirely |
| 2 | Is registration-system data accessible for cross-checks? | Class 6 |
| 3 | Legal, rate-limited path to bulk public records | real-data phase |
| 4 | Two annotators available, or one? | any human-labelled measurement |
| 5 | Which state/district for the first corpus? | unit ladder, field aliases |

`[Guessing]` Items 1 and 4 have been open for some time. If phase 1 finishes before
they resolve, build breadth in the harness (more mutation types, more unit systems)
rather than starting a blocked class.

---

## 9. First session

1. Read `AGENTS.md`.
2. Propose the schema in §3 as code and **argue with it** — if the hierarchy is wrong
   for real records, say so before writing 40 rules on top of it.
3. `units.py` with exact arithmetic + property tests. Nothing else until this passes.
4. Synthetic mouza generator + the zero-findings-on-clean assertion.
5. Class 1. Three fixtures per rule.
6. Then Class 2.

Do not scaffold the whole repo first. Schema and units, tested, before any rule exists.
