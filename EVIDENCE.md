# EVIDENCE.md — sourced facts, separated from decisions

Facts with citations. Decisions live in `SCHEMA.md`. Nothing here is a project
measurement; these are other people's findings, cited so they can be checked.

**Primary source (S1):** *Evaluation of Quality of Land Records — Bihar*, Department
of Land Resources (Draft for Discussion), 57pp, hosted on the Government of India
S3WaaS CDN.
`https://cdnbbsr.s3waas.gov.in/s3d69116f8b0140cdeb1f99a4d5096ffe4/uploads/2025/07/202507301204050224.pdf`

---

## E1 — One survey number, many jamabandis. `[Certain]` S1 p.15, p.4(F)

> "The land record maintenance system in Bihar does not require spatial division of
> land parcels. Instead, when a parcel of land is being subdivided amongst multiple
> heirs, each of them would get a separate jamabandi with exact extent (area in
> acre/decimal) mentioned, but the survey number in each of these jamabandis would
> continue to be the same. **Thus, several jamabandis can/do exist in one survey
> number.**"

**Settles Ruling 1.** Holding is many-to-many. This was `[Likely]` and is now sourced.

## E2 — Shares are not recorded. `[Certain]` S1 p.15

> "There are a few instances of multiple ownership of land, but the ratio is less.
> **In these cases with multiple owners, no shares are mentioned against the names.**"

**Corrects SCHEMA.md.** `Membership.share` and `Holding.share` cannot be required
`Fraction`. They are normally absent. Class 2's "co-owner shares sum to exactly 1"
is therefore `UNVERIFIABLE` on Bihar jamabandi input — not a pass. Per AGENTS.md 3.3
that abstention is the correct output, and it is probably the single most common
finding the engine will emit on real data.

## E3 — Partition records an area, not a share. `[Certain]` S1 p.15

Each heir gets "a separate jamabandi with exact extent (area in acre/decimal)
mentioned". So on real input `Holding.area_claimed` is the populated field and
`Holding.share` is the empty one — the inverse of what SCHEMA.md assumed. Both are
optional; **neither is required**, because a blank-area jamabandi is a documented
real state (see E5).

## E4 — The audit ladder for Bihar is acre/decimal, not bigha/katha/dhur. `[Certain]` S1 p.12

The jamabandi RoR field list gives:

> "vi. Rakba (Area of land parcel in acres, decimal and hectares)"
> footnote 2: "One decimal of land is equal to 435.6 square feet or 0.01 acres."

`bigha / katha / dhur` (HANDOFF_BUILD.md 3.5) is the colloquial and khatian ladder.
The **digitised jamabandi — the thing Phase 1 audits — uses acre/decimal**, base 100,
and decimal is exactly anchorable (1 acre = 43560 sq ft; international foot = 0.3048 m
exactly). Added as ladder `bihar.jamabandi`. The bigha ladders stay, unanchored.

## E5 — Zero and blank identifiers are a measured, real error class. `[Certain]` S1 p.4(C), p.16, p.47

> "the digitised jamabandis have multiple errors in them. These include instances
> where the **khata number, khesra number, or area is mentioned as zero/blank**."

Village survey: "Around 6 percent of RoRs had missing Khata and Khesra no. or had
**'0' as an entry**; another 5 percent weren't even available online."

Grounds Class 1's zero/blank checks in something other than inference. Note the
documented violation is on **khata and khesra numbers**, which is broader than
HANDOFF_BUILD.md 4's "sub-division numbering starts at 1, never 0".

## E6 — The jamabandi has no land-classification column. `[Likely]` S1 p.12

The eleven RoR fields listed are: raiyat name · jamabandi sankhya · district, circle
and village · khata no. · khesra/plot no. · rakba · chauhaddi · mutation details ·
lagaan · previous lagaan · mortgage and revenue case details.

**No tenure or land-use field appears.** So Class 2's
`raiyati_total + gairmazrua_total == mouza_total` (HANDOFF_BUILD.md 3.4) cannot run on
jamabandi-only input and must abstain. Classification lives in the khatian, a
different and older document. `Khesra.tenure` and `.land_use` are therefore optional.

## E7 — "Tehsil" is "Circle" (Anchal) in Bihar. `[Certain]` S1 p.12, p.18

The RoR carries "District, Circle and Village/town name", and error correction
"happens at the Anchal (Circle) level". The PS says *tehsil*. Modelled as one concept
`subdistrict` plus a `subdistrict_term` recording the regional word, per
HANDOFF_BUILD.md 3.2's "model the concept, alias the names".

## E8 — Two RoR lineages, not one. `[Certain]` S1 p.13

Khatian (one-time, no update provision, legally the RoR under the Bihar Tenancy Act
1885) and the Jamabandi Register / Register-II (computerised 2017–18, the de facto
RoR). Both are called "record of rights". They are independent witnesses to the same
land — which is what Class 4 and Class 6 will need, and a reason the time axis models
*lineage* as well as version.

## E9 — Land classification taxonomy `[Guessing]` — deliberately NOT pinned

Secondary sources give: raiyati (private, transferable) · bakasht (ex-landlord direct
cultivation) · sikmi (sub-tenant) · gairmazrua, sub-typed *aam* (public: roads, ponds,
cremation grounds) and — sources disagree — *malik* or *khas*.

SCHEMA.md previously wrote `gairmazrua-khas` as though settled. It is not. Because
classification is loaded as data (`classifications.json`), each class carries a
`confidence` field and disputed entries are marked. Getting this wrong costs a JSON
edit, not a rewrite. **Do not cite a Bihar tenure taxonomy from this project until a
primary source is read.**

## E11 — A jamabandi can carry parcels of another village. `[Certain]` S1 p.19

Among the corrections citizens may apply for through the Parimarjan portal:

> "Segregation of mauja wise khesra from digitized Jamabandi with khesra of
> multiple mauja"

So a record set whose parcels do not all belong to its own mouza is a documented
real state, not a hypothetical. Grounds `C3.records_belong_to_this_mouza` and the
`parcel_moved_to_another_mouza` mutation.

The same list also names correction of "Jamabandi digitized in wrong village", and
correction or addition of name, address, khata number, khesra number, chauhaddi,
area and lagaan details — which is a fair summary of what Classes 1 to 3 check.

---

## E10 — A free check neither build document names `[Certain]` S1 p.12

Rakba is recorded **three times in three unit systems on the same row** — acres,
decimal, and hectares. That is a second witness *inside a single record*, requiring no
other document, no OCR, no portal, and no model. Cross-unit agreement of rakba is a
Class 2 conservation check available on all 4.32 crore digitised RoRs.

Two properties make it exact rather than approximate:

* 1 decimal = 1/100 acre exactly, and 1 acre = 4046.8564224 m² exactly.
* A hectare value written to four decimal places is an exact whole number of square
  metres (0.4047 ha = 4047 m²), so the comparison is integer arithmetic.

The check is *"does the written value equal the exact conversion, rounded to the
precision at which it was written?"* — a declared rounding policy, not an epsilon.
This is the shape the pending sub-dhur tolerance decision should also take.

## Measured figures from S1 (cite as theirs, never as ours)

| Figure | Source |
|---|---|
| 4.32 crore RoRs, 100% digitised | S1 p.4(A) |
| 87% single-owner RoRs; 13% multiple owners | S1 p.45 |
| 39% of single-owner RoRs have un-updated inheritance | S1 p.45 |
| 43% of RoRs have un-updated inheritance overall | S1 p.45 |
| 6% missing khata/khesra no. or "0" entry | S1 p.47 |
| 11% area mismatch | S1 p.47 |
| 5% not available online | S1 p.47 |
| 2% name errors | S1 p.47 |
| ~34% of spatial records georeferenced; 25,060 of 1.35 lakh map sheets | S1 p.4(G), p.6(N) |
