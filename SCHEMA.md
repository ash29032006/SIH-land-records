# SCHEMA.md — the settled Phase 1 data model

**Status: ruled on, 27 Aug 2026.** Supersedes `HANDOFF_BUILD.md` §3.1 where they differ.
This is a decision record, not code. `records.py` does not exist yet and must not be
written until `units.py` is green.

---

## 1. What changed from HANDOFF_BUILD.md §3.1

§3.1 described a strict tree:

```
Mouza → Khata → Khesra → Sub-division
```

Two things were wrong with it and two entities were missing. The corrected shape is
**two spines joined by an edge**:

```
spatial (area lives here)          tenurial (rights live here)
  Mouza                              Mouza
   └─ Khesra                          └─ Khata
       └─ Khesra (recursive)              └─ Membership → Owner
            └─ …                                (share: Fraction)
              \                            /
               \___ Holding (m:n) ________/
                    share + claimed area
```

**Ruling 1 — Holding is many-to-many, built now.** `[Certain]` — **sourced since the
ruling**, see EVIDENCE.md E1. The DoLR evaluation of Bihar land records states it
outright: *"several jamabandis can/do exist in one survey number."* Partition in Bihar
is textual, not spatial; each heir gets a separate jamabandi with its own stated area
and the same survey number. The asymmetric-cost argument turned out not to be needed.

**Ruling 2 — the time axis is in Phase 1.** Every entity carries validity. Every rule
declares its scope: `WITHIN_VERSION` or `ACROSS_VERSION`. This is what makes
"duplicate khata per owner" implementable now rather than deferred — the rule is
`WITHIN_VERSION`, so superseded rows in a bulk dump are out of scope by construction
instead of by luck.

---

## 2. Entities

```
Mouza
  id, name, tehsil, district, ladder_id
  area_stated            Area       — from the settlement survey document
  area_provenance        Provenance — required; see §4
  as_of                  date
  valid_from, valid_to

Khesra                                    # the spatial spine; area lives here
  id, mouza_id
  parent_khesra_id   : id | None          # recursion, unbounded depth (217/1/2 is legal)
  local_number       : str                # "217", "1", "2" — the segment, not the path
  path               : tuple[str, ...]    # ("217","1","2") — derived, for display + sequence rules
  area_stated        : Area
  tenure             : TenureClass        # raiyati / gairmazrua-aam / gairmazrua-khas / bakasht
  land_use           : LandUseClass       # separate axis — see §5
  classification_scheme : str             # regional codebook id, loaded as data
  valid_from, valid_to

Khata                                     # the tenurial spine; no area of its own except stated
  id, mouza_id, number
  area_stated        : Area | None
  valid_from, valid_to

Owner
  id, name_raw, qualifiers               # father's name, address fragments
  # identity is FUZZY BY CONSTRUCTION. There is no reliable key. Any rule that
  # depends on owner identity emits CONFLICT or ANOMALY, never CERTAIN_ERROR.

Membership                                # owner's stake in a khata
  khata_id, owner_id
  share              : Fraction | None    # NORMALLY NONE on real input — EVIDENCE.md E2
  valid_from, valid_to

Holding                                   # THE JOIN — the thing that was missing
  khata_id, khesra_id
  share              : Fraction | None    # normally None in Bihar
  area_claimed       : AreaStatement|None # normally the populated one — EVIDENCE.md E3
  valid_from, valid_to
  # NEITHER is required. A jamabandi with a blank area is a documented real state
  # (~6% of RoRs, EVIDENCE.md E5), and it makes conservation UNVERIFIABLE, not wrong.

Mutation
  id, subject_id (khesra|khata), date, from_state, to_state, order_ref

Registration
  id, khesra_id, external_system, reference, date
```

### Correction 1 — Holding carries *both* a share and a claimed area
Two separate stored values, never one derived from the other. `share × khesra.area_stated`
is the *computed* area; `area_claimed` is what the register actually says. The
disagreement between them is a finding. Collapsing them into one `area_held` destroys it
before any rule runs.

**Revised after research (EVIDENCE.md E2, E3):** both are optional and *neither* is
required. Bihar jamabandi records an exact area per heir and **no share at all**, so the
field this schema treated as primary is the one that is normally empty. `None` is not
zero and not an error — it makes that holding's conservation check `UNVERIFIABLE`.
Consequence: Class 2's "co-owner shares sum to exactly 1" abstains on real Bihar input,
and that abstention is probably the highest-volume output the engine will produce.

### Correction 2 — `is_leaf` is derived from an as-of date, never stored
A stored `is_leaf` flag is a cached answer that goes stale the moment a mutation lands,
and a stale one silently double-counts a parcel in the mouza trial balance.

```
is_leaf(khesra, as_of) := no child khesra of `khesra` is valid at `as_of`
```

Conservation sums **leaves as of a date**. `parent.area_stated == Σ children.area_stated`
is a separate rule on internal nodes. Both are `WITHIN_VERSION` at the given `as_of`.

### Correction 3 — `FieldValue` is not in the canonical model
`value / provenance / confidence / witnesses` (HANDOFF_BUILD.md §3.3) belongs to the
**extraction layer** (Layers A–B), which does not exist yet and is weeks away. Wrapping
every canonical scalar in it now would make Phase 1 rules navigate a box that has
`confidence=None` on every single record — noise with no signal, in the phase whose
entire point is that it needs no model.

Phase 1 entities hold plain typed values. The extraction layer will produce
`FieldValue[T]` and *unwrap* into these entities at its boundary, carrying provenance
into a side table keyed by `(entity_id, field_name)`. `witnesses` is computed by Class 8
from the records actually present, not stored per field.

---

## 3. Rule scope is declared, not inferred

Every rule declares one of:

```
WITHIN_VERSION   evaluated against a single as_of date; superseded rows excluded
ACROSS_VERSION   evaluated over ≥2 versions; the version pair is part of the finding
```

A rule that does not declare its scope does not run. Class 2's
`parent area at T == Σ child areas at T+1` is the canonical `ACROSS_VERSION` rule;
everything else in Classes 1–3 is `WITHIN_VERSION`.

---

## 4. `mouza_total` needs provenance and an abstain path

Not an AGENTS.md §2 violation — §2 forbids *inventing* numbers, and a mouza total read
off a settlement document is a real measurement, not an invented one. The requirement is
narrower and purely operational:

- `area_stated` on Mouza requires a non-null `Provenance` (document, page, cell).
- If no sourced total exists for the requested `as_of`, the trial-balance rule emits
  **UNVERIFIABLE**, not `CERTAIN_ERROR`.

This matters because mouza boundaries do move — diara/river action, municipal redraws,
acquisition, mergers. A conservation failure against an undated or unsourced total is
not evidence that the records are wrong.

---

## 5. Classification is two orthogonal axes — and is often simply absent

`tenure` and `land_use` are independent. Class 3's "one plot, one classification" holds
**per axis** and is false across them. Both resolve through a regional
`classification_scheme` loaded as data, exactly like the unit ladders.

**Both fields are optional.** EVIDENCE.md E6: the digitised jamabandi has no
classification column at all — it is in the khatian, a different and older document. So
Class 2's `raiyati_total + gairmazrua_total == mouza_total` **cannot run on jamabandi-only
input** and must abstain rather than pass.

The taxonomy itself is `[Guessing]` and deliberately not pinned — see EVIDENCE.md E9.
An earlier draft of this file wrote `gairmazrua-khas` as settled. Sources disagree
between *malik* and *khas*. Because the scheme is data, that costs a JSON edit.

---

## 6. Identifiers are a list, not fixed columns

```
identifiers : list[Identifier(scheme, value)]
```

*khasra ≈ khesra ≈ survey no. ≈ gat no.* alias cleanly. **khata ≉ patta** — in Bihar a
khata is an account grouping in a register; in TN/AP a patta is a grant document issued
to a person. They are not the same concept and must not share a field. Maharashtra 7/12
has no khata at all; Gujarat carries block **and** survey number on one parcel.

---

## 6a. Administrative levels: one concept, a recorded regional term

The PS says *tehsil*; Bihar's RoR says *Circle*, and corrections happen at *Anchal*
level (EVIDENCE.md E7). Modelled as `subdistrict` plus `subdistrict_term` recording the
word the document used. One concept, aliased — not parallel fields.

## 6b. Area statements: one quantity may be written more than once

```
AreaStatement(area: Area, as_written: str | None, provenance: Provenance | None)
```

`as_written` is the raw document string, kept so the unit-carry check has something to
check. `area_restatements` holds the *same quantity written in another ladder*.

This exists because of EVIDENCE.md E10: the Bihar rakba field states one area in
**three** unit systems — acres, decimal and hectares — on the same row. That is a second
witness inside a single record, and cross-unit agreement is a Class 2 check needing no
other document, no OCR and no portal. It may be the cheapest certain check in the system.

## 7. Areas carry their ladder

Every `Area` is `(ladder_id, exact count of that ladder's smallest unit)`. A bare
integer count of dhur is ambiguous, because bigha/katha are not physically constant
across Bihar districts. Same-ladder arithmetic is exact and needs no registry lookup —
which is what keeps rules pure. Cross-ladder arithmetic requires a **declared exact
rational** on both ladders, or it refuses. See `kavach/units.py`.

**The ladder Phase 1 actually audits for Bihar is `bihar.jamabandi` — acre/decimal,
base 100 — not bigha/katha/dhur** (EVIDENCE.md E4). The digitised RoR uses acre/decimal/
hectare; bigha/katha/dhur is the colloquial and khatian ladder. Both ship. The
acre-based ones are anchored and exactly inter-convertible; the bigha ones are not, and
refuse.

## 7a. Validity is declared on the container, not defaulted per record

A record with no `valid_from`/`valid_to` is not silently assumed current. The
`RecordSet` declares its own kind:

```
SNAPSHOT       one extraction of one register at one time; undated records are
               taken as valid at the set's as_of — a stated assumption, in one place
MULTI_VERSION  rows from several versions mixed; undated records are UNKNOWN
```

`UNKNOWN` validity is surfaced to rules, never silently included or excluded. A
`WITHIN_VERSION` rule that would have to guess must emit `UNVERIFIABLE` instead. This is
what actually makes Ruling 2 work rather than merely declared.

---

## 8. Field count — the number that goes in the deck

**11 names as listed in HANDOFF_BUILD.md §3.2. 10 concepts after aliasing
survey no. ≡ khasra no. 4 of them are per-parcel scalars.**

Slide 2's "twelve mandated fields" is wrong under every reading and needs changing.
(v6's "12 requirements" and "11 per-field thresholds" count different things and do not
contradict each other — that was my error. The contradiction you flagged is in the v5
`.docx`, which is not in this folder.)

| Kind | Count | Which |
|---|---|---|
| per-parcel scalars | 4 | khasra/survey no., khata no., plot area, land classification |
| attributes of an ancestor entity | 3 | village, tehsil, district |
| relationships / collections | 3 | landowner details, mutation records, registration info |
| **listed names** | **11** | (survey no. and khasra no. collapse → 10 concepts) |

`plot area` is a compound (quantity + ladder + unit), not a scalar, which is why it gets
`units.py` to itself.

---

## 9. Open, and deliberately not answered here

1. Does a real jamabandi exercise the m:n Holding? — a *data* question; the schema does
   not wait on it.
2. Do katha-per-bigha counts vary across Bihar districts, or only the physical size of
   the bigha? `units.py` encodes the structure from HANDOFF_BUILD.md §3.5 and leaves
   every Bihar physical anchor `null`.
3. Owner identity resolution — deferred. Nothing in Classes 1–3 may depend on it.

---

## 10. Tolerance policy — decided, as HANDOFF_BUILD.md 4 requires

**Every comparison in Class 2 is exact equality over `Fraction` counts of a ladder's
smallest unit. There is no epsilon in the codebase and no parameter to add one.**

This is enforceable rather than aspirational: `tests/test_units.py` bans the `/`
operator and every float across the package, so an epsilon cannot be introduced
without failing the build.

### Why exact equality is correct here

Areas are integer counts of a smallest unit. Shares are rationals. Three one-third
shares of a parcel sum to exactly one; in binary floating point they do not, and the
rule would invent a violation on a correct record. Floats manufacture findings.

### The one place rounding is inherent, and how it is handled

The Bihar rakba field states one area in three unit systems (EVIDENCE.md E10). The
hectare column is written to four decimal places, so it is a *rounded* rendering of an
exact quantity — 1 acre is 0.40468564224 ha, written 0.4047.

The policy for that case is **not** a tolerance. It is:

> Does the written value equal the exact conversion, **rounded to the precision at
> which it was written**?

That is still exact arithmetic, because a hectare written to four decimals is a whole
number of square metres. `metric.hectare` exists with `centiare` as its smallest unit
precisely so this comparison is integer arithmetic rather than an epsilon.

`C2.cross_unit_restatement` currently requires exact agreement, which is right for
generated fixtures where the restatement is stored exactly. When a real corpus is
loaded, the written precision must be carried on the `AreaStatement` and compared at
that precision — a declared parameter with a stated justification, per
HANDOFF_BUILD.md 4, never a magic constant.

### The sub-unit share question, resolved

An undivided one-third share of a parcel of 100 decimal is exactly 100/3 decimal — not
a whole number of the smallest unit. `Area` holds it as a `Fraction`, so the partition
still re-sums to exactly 100 and no tolerance is needed.

What a real register does is write a *rounded* figure for each heir. When that happens,
`C2.share_matches_claimed_area` will disagree with the claimed area by a sub-unit
amount. That disagreement is a **CONFLICT**, not a `CERTAIN_ERROR`: two witnesses
differ, and which is right is a human decision. It is recorded here so the rule is not
later written as certain.

The synthetic generator deliberately produces integral holdings so this case does not
silently inflate the clean-input figures. Real data will exercise it; fixtures do not
pretend to.
