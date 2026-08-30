# SIH26018 — Complete Handoff Context (v6)

**Team Kavach · Smart India Hackathon 2026 · Problem Statement 26018**
**Compiled 25 August 2026. Supersedes the v4 architecture doc and the 25-Aug handoff file.**

> **Purpose.** Give a fresh LLM full end-to-end context with zero prior conversation.
> Read §0 first — it changes how you should respond. Read §2 before proposing anything;
> it records decisions already settled, so you do not re-litigate them.

---

## 0. READ THIS FIRST — how to work with this user

Undergraduate CSE student, PES University Bengaluru. Builds and ships. **Wants an advisor, not an assistant.**

**Non-negotiable working style:**

- **Never open with agreement.** The first sentence challenges the assumption or names what is missing.
- **Tag every claim:** `[Certain]` (hard sourced evidence) · `[Likely]` (strong inference) · `[Guessing]` (filling gaps). If mostly guessing, say so upfront.
- **Lead with the uncomfortable truth.** First line, not paragraph three.
- No warm-up paragraphs. No "great question." No "you're absolutely right."
- **Disagree with structure:** *"I disagree because [reason]. Here's what I'd do instead [alternative]. The risk in your approach is [specific downside]."*
- **Hold position unless given genuinely new information.** He pushes back hard and fast; that is the process working, not a signal to fold.
- Explain simply when he is learning something new. Bullets, plain language, no derivations unless asked.
- **End every substantive response with a summary.** Do it without being asked.

**Calibration notes learned the hard way:**

1. He will say *"stop this shit"* if you over-apply prototype-caution to an **idea-stage** deck. Distinguish **claims about the world** (must be true) from **claims about intent** (can be ambitious). Pitching what you will build in three months is legitimate.
2. He has asked for fabricated validation results ("say we built and validated it"). **This was declined and the decline held.** The reasoning that worked: the entire pitch is *"stop shipping systems that assert things they cannot back up"* — a deck that fabricates validation for that pitch has no recovery path, and it gets tested at national screening where DoLR reviewers ask to see the validation set. **Present tense, ambitious framing, full 13/13 system language is fine. Fake measurements are not.** Do not reverse this.
3. He oscillates on density. He asked to cut hard (citing HBR design principles), then said slide 2 had "nooo info." The resolution: **the template's mandated sub-headings must always be present and labelled.** Cutting those was the actual error, not cutting words.

---

## 1. THE SITUATION

### Competition
- **Smart India Hackathon 2026**, Problem Statement **26018**
- Ministry of Rural Development, **Department of Land Resources (DoLR)**
- Category: **Software** · Team name: **Kavach** (registered)
- Title: *Intelligent Land Record Digitization and Validation System*

### Funnel
1. **Idea submission** — 6-slide PDF on the mandatory SIH template. **This decides everything right now.**
2. Top-5 college selection → college commits full support
3. **National screening (Sep–Oct)** — document-only review by DoLR domain reviewers
4. Build window ~3 months

### Current state
- Six teammates. **Nothing has been built.** No code, no data, no measurements.
- Deck **is built** and template-exact (see §7). Two support documents exist (§10).
- ⚠ **The PPT deadline is days away; the build schedule is 8 weeks. Different deadlines. The PPT comes first.**

### ⚠ Template constraints
Six slides max including title. **Fixed section headings that cannot be changed:**
1. Title Page (PS ID, PS Title, Theme, PS Category, Team ID, Team Name)
2. **Proposed Solution** — detailed explanation / how it addresses the problem / innovation and uniqueness
3. **Technical Approach** — technologies to be used / methodology and process (flowcharts, images, working prototype)
4. **Feasibility and Viability** — feasibility analysis / challenges and risks / strategies
5. **Impact and Benefits** — impact on target audience / benefits (social, economic, environmental)
6. **Research and References** — details and links

Rules: avoid paragraphs, use points/diagrams/infographics; template must not be modified; **submit as PDF only.** The template's slide 7 (Important Instructions) must be deleted before submission — this is already done.

---

## 2. SETTLED DECISIONS — do not re-open without new evidence

| Decision | Status | Why |
|---|---|---|
| **Thesis is validation, not digitisation** | SETTLED | 95.09% of villages already computerised. DoLR does not need help typing. |
| **The eureka is the Platinum vs 61% contradiction** | SETTLED | National, uses only government numbers, needs no portal verification. See §3.1. |
| **Bihar / Kaithi cross-register is ONE capability bullet, not the flagship** | SETTLED | It covers ~5 states, rests on an unverified portal fact, and is a research project inside a platform commission. |
| **No fabricated measurements on the deck** | SETTLED, HELD | See §0 note 2. |
| **12 requirements, not 13** | SETTLED | PS numbering is corrupted (runs 7→15, drops to a bullet, restarts at 7). Deduplicated: 12. v4 double-counted the learning mechanism. **Never print "13/13".** |
| **Theme field reads "MedTech / BioTech / HealthTech"** | SETTLED | Portal data-entry error for PS 26018. **Copy verbatim.** A mismatch against the portal record is the cheapest possible disqualification. Note the discrepancy in a comment field if one exists, never on the slide. |
| **Build extraction, never pitch it** | SETTLED | Commodity with three incumbents. Scored, so build it. Pitching it invites comparison you lose. |
| **One rule engine, two directions** | SETTLED | Forward = extraction gate. Backward = audit of already-digitised records. Resolves the forward/backward ambiguity in §5.2. |
| **Flag, never verdict** | SETTLED | Legal and ethical. See §4.4. |
| **Queue order = consequence × uncertainty** | SETTLED | NOT ascending confidence. v4 stage 12 said ascending confidence; that was stale and is corrected. |

---

## 3. THE EVIDENCE BASE

Confidence tags: `[Certain]` = checked against a real source in-session · `[Dossier]` = from team documents, **not independently verified** · `[Likely]` = strong inference · ⚠ = must verify before slide use.

### 3.1 THE HEADLINE — the contradiction

`[Certain]` **Tamil Nadu holds Platinum Grading.** DoLR set saturation targets for computerisation of Records of Rights, digitisation of cadastral maps and text–map integration. As on 20.12.2023, **168 districts across 16 States — Tamil Nadu among them — achieved Platinum Grading** by completing 99% and above in the six core components.

`[Certain]` **The grading is self-reported.** DoLR's own wording: the grading system is *largely based on reports and inputs of the States/UTs* in the core components of computerisation and digitisation.

`[Dossier]` ⚠ **CAG, same state, same period:** area mismatch in **61% of sampled villages**; **3.22 lakh** private parcels wrongly classified as government land.

> **The pitch sentence:** India's only national measure of land-record quality is a self-reported completion percentage. It measures how much was typed, never whether it was typed right. No instrument to measure the second thing has ever existed.

**Why nobody built it (the mechanism, not a guess):** digitisation was scoped, funded and graded as a *transcription* programme — measured on villages covered, never on records correct. Nobody was paid to find errors, so the software was never built to look for them. Coverage and correctness are orthogonal and only one was measured.

### 3.2 CAG findings — the rule-by-rule map

All `[Dossier]` `⚠ VERIFY AGAINST PRIMARY REPORT` — see §9 item 1. Source: CAG Performance Audit on Land Records Management, Tamil Nadu, year ended March 2021.

| Finding | Validation rule it proves |
|---|---|
| Area differences, manual vs computerised, **61% of sampled villages** | Area reconciliation (Class 5) |
| **3.22 lakh** private parcels misclassified as government land | Classification balance (Class 2) |
| **"Lack of validation controls in the application software"** | The core thesis, in the auditor's words |
| **910** survey numbers with sub-division numbered '0' | Grammar (Class 1) |
| Survey number 102 should carry 5 records; only 3 existed | Completeness (Class 3) |
| Multiple/redundant patta numbers per owner | Duplicate detection (Class 3) |
| **6.25 lakh of 23.25 lakh** sub-divisions (27%) had no FMS entry | Why area drift went uncaught — no measurement to check against |

**Registration-side audit — the strongest single argument:** `[Dossier]` **18,378** "invalid survey number" responses still linked to registered documents. In one village, of 10,811 documents, **832** had invalid survey numbers and **308** carried numbers classified as government land. Of **16,00,145** transfer requests, **1,24,304** returned Null/Failed **with no corrective action taken.**

> That last figure is the argument for the *workflow*, not the detection. The failure was already detected. Nothing happened.

**Mechanism (Andhra Pradesh CAG):** `[Dossier]` A Tahsildar explained on record that the software automatically sub-divides existing survey numbers and allots a new sub-division number whenever a division occurs — **without changing the manual record.** The digital system was generating records the paper register never had. The books diverge *structurally*, not through typos.

### 3.3 Verified in-session

`[Certain]` **Bhu-Naksha serves both survey layers.** Selecting a map requires District → Sub Division → Circle → Mouza → **Survey Type (RS – Revisional Survey or CS – Cadastral Survey)** → Map Instance → Sheet No. Selecting a plot returns rakba (area), khesra number **and chauhaddi**, downloadable as PDF via LPM Reports.
→ Consequence: the CS↔RS join can be **geometric**, not textual. And chauhaddi-vs-map-adjacency becomes a checkable rule (§4.3).

`[Certain]` **Patna High Court:** a khatiyan — CS or RS — is a **Record of Rights, not a deed of ownership**; it establishes possession and rights as recorded during the survey and **does not create or extinguish title**, a position the court has repeatedly held.
→ Use on slide 4. Triple duty: answers the hostile question, restates the presumptive-title thesis, and justifies flag-never-verdict.

`[Certain]` **Bhu-Abhilekh, not Jamabandi Panji.** Older/original CS/RS-era khatiyan scans live in the **Bhu-Abhilekh** section (`bhuabhilekh.bihar.gov.in`). Jamabandi Panji returns the *current computerised* record. ⚠ One source claims Jamabandi Panji also exposes a CS/RS type selector — check both, do not assume the redirect is total. Also flagged: some older RS khatiyans are not fully digitised, with the Anchal office as fallback.

`[Certain]` **Benford's Law is established, and areas are canonical.** First-digit distribution log₁₀(1+1/d) holds for natural datasets including **areas**, addresses and populations. Varian proposed in 1972 that it could detect fraud in socio-economic data submitted for public planning decisions. It has been admitted as evidence in criminal proceedings.
⚠ **Guardrail to state yourself:** deviation from Benford is *not* proof of fraud; a conformity test without an error term is too imprecise. It directs sampling. It never accuses. No published application to Indian land records was found — so **"we adapt"**, never **"novel"**.

`[Certain]` **NGDRS** (National Generic Document Registration System) is the registration incumbent; **BISAG** handles map returns; **Bhu-Naksha (NIC)** vectorises. Name all three and decline to rebuild them.

### 3.4 From the team dossier — high value, unverified

`[Dossier]` As on 31 Dec 2023: RoR computerised in **6,25,137 of 6,57,397 villages = 95.09%**. Cadastral maps **68.02%** digitised. Registration 96%. Revenue–registration integration 89%. **The 27-point text-vs-map gap is where the errors hide.**

`[Dossier]` **ULPIN / Bhu-Aadhaar** is a 14-digit ID *derived from latitude and longitude*. You cannot generate a coordinate-derived ID without a geo-referenced map. **Map digitisation at 68% is the bottleneck for the entire ULPIN programme.** Village-level geo-referencing: 3,26,776 of 6,57,397 = 49.10%. (⚠ Parcel-level ULPIN figures conflict: 8.4 crore vs 23 crore. Use the village figure.)

`[Dossier]` **SVAMITVA** (Ministry of Panchayati Raj): drone survey complete in **3.29 lakh of 3.44 lakh** villages; **10.46 crore parcels** digitised; **11,147 loans worth ₹1,713 crore** disbursed against property cards. *A different philosophy: don't repair the century-old map, fly a drone and make a new one.* Absent from v3 — not knowing about it in front of DoLR would be a credibility hole.

`[Dossier]` **DILRMP:** 100% centrally funded from 1 Apr 2016; outlay ₹875 crore for 2021-22 to 2025-26; ₹2,428 crore released 2008-09 to 2024-25. **Quote worth using:** its own aim is *"error-free, transparent and tamper-proof land records by adopting modern technology such as AI, Machine Learning and Blockchain."* Stated architecture goal is **ILIMS** — all information about a piece of land in one place, which is a corroboration architecture described by them first.
⚠ **DILRMP's stated sunset was March 2026 and it is now August 2026. What replaced or extended it is UNCONFIRMED.** Write *"under DILRMP and its successor arrangements"* on any slide until verified.

`[Dossier]` **Kaithi human cost — best single number:** *"Kaithi translators used to charge Rs 200-300 per page. Now it's Rs 1,000-1,500."* Majority of Bihar districts have **fewer than ten** Kaithi readers. ⚠ Not currently in the slide-6 reference table — source it or cut it from slide 5.

`[Dossier]` **Bihar special survey:** 38 districts, 45,000+ villages, deadline extended July → **December 2026**, allocation ₹1,955.98 crore. The survey *"has stirred up a hornet's nest"*; district courts swamped with new disputes. → **Digitising unreadable records without a confidence layer manufactures disputes.**

`[Dossier]` **July 2025: Bihar Revenue & Land Reforms signed an MoU with Digital India BHASHINI** for AI transliteration of Kaithi into Devanagari. → **"Nobody has solved Kaithi" is DEAD as a claim about the world.** Position underneath, not against: transliteration converts glyphs; it does not say when it is wrong. Crores of records feeding a live legal survey **with no confidence layer** is the CAG story repeating one technology generation later.

`[Dossier]` **Daksh survey (9,000+ litigants):** civil litigants spend ~₹497/day on hearings; **90% earn under ₹3,00,000 annually**; 80% did not study beyond school. → the evidence for "a false flag costs a family real money."

### 3.5 Technical literature

| Ref | Finding that matters |
|---|---|
| **arXiv:2606.29213** — Devanagari OCR stress-test | Real scans spread **76 chrF++ points**. **Qwen3-VL-8B = 75.2**, beats GPT-5.5 (58.5). Gemini 2.5 Flash 86.3. **Report median CER + catastrophic rate, NEVER the mean** — DeepSeek-OCR has the best median of any system and a mean destroyed by 2–3% of samples entering degenerate repetition loops. Classical engines fail on *surface* elements, VLMs on *structural* ones — this validates the two-reader design. |
| **arXiv:2606.24420** — ExtractConf (IJCAI-ECAI 2026 Oral) | Logprob mean **0.705 AUC**, verbalized **0.692**, self-consistency ×5 **0.744 at 5× cost** — all collapse to all-positive classifiers. **Errors are document-caused, not model-caused**, so internal model confidence measures the wrong thing. Cross-call agreement = largest single gain (−34% AURC). OCR confidence beats logprobs (0.896 vs 0.880). Isotonic cuts ECE by 83%. **~165 in-domain samples** suffice for recalibration. **Negative sample QUALITY dominates dataset SIZE.** Their two calls are the same model with asymmetric prompts — so "two model families for independence" is stronger than the evidence requires. |
| **arXiv:2608.01792** — ConfBench (AWS) | OCR+image modality uniformly strongest, gap largest for **smaller models** — exactly the 8B regime. ECARB review-budget metric; best config captures **2.43× the errors of random review at 30% budget**. |
| **arXiv:2603.19790** — Geometric Risk Controller | K=5 mildly transformed views, K_min=3, τ=0.5, κ=0.4. Coverage-matched win over logprob thresholds in all six settings. Residual failure they name: **stable-but-wrong consensus**. |
| **Splink** (UK Ministry of Justice) | Fellegi–Sunter probabilistic record linkage, **unsupervised via EM**, calibrated match probability per pair, **handles many-to-many natively**. `github.com/moj-analytical-services/splink`. This is how you match records across registers *without labels* — it dissolves the circularity described in §6.2. |
| **arXiv:2605.23597** (ACL 2026) | Indian name matching: patronymics, caste and village names as integral components, honorifics appearing/vanishing, non-uniform transliteration. **Plain Levenshtein on owner names will both false-merge and miss duplicates.** |
| **arXiv:2404.18706** — Socface | National-scale historical handwritten tabular digitisation (a century of French censuses). Credibility anchor. |

**Also:** PaddleOCR PP-OCRv6 (11 Jun 2026), `devanagari_PP-OCRv5_rec`. Table detection: Table Transformer/PubTables-1M, DocLayout-YOLO, TableFormer, PaddleOCR-VL. ArcGIS Parcel Fabric is the commercial incumbent for parcel topology validation — cite it, don't rebuild it.

---

## 4. THE VALIDATION ENGINE — the actual product

### 4.0 The organising frame

> **India's land records are single-entry bookkeeping.** Every mutation touches one book and nothing has to balance. Double-entry was invented in 1494 for exactly this reason: a single-entry system cannot detect its own errors, because there is no second number to disagree with the first.

> **Land is conserved.** A village's total area has not changed since the 1926 settlement. Every record that violates that conservation is provably wrong — with no ground truth, no annotator and no model. **That is the trial balance.**

**Second frame, for the diagram:** every parcel is described by several independent records made by different offices at different times, which have never been compared. **When four witnesses agree and one dissents, you do not merely know something is wrong — you know WHICH record is wrong.** That is error *localisation*, and it is what slide 2 shows.

### 4.1 Class 1 — Grammar `free · certain · needs nothing`

| Rule | Catches |
|---|---|
| Sub-division numbering starts at 1, never 0 | CAG's 910 violations |
| Charset: khasra is digits and separator only | `2l7` for `217` |
| **Unit carry rules** — Bihar bigha-katha-dhur is base-20; kanal-marla base-20 | "27 katha" is un-normalised — a transcription artefact. **Nobody checks this.** |
| Date ordering: mutation ≥ survey | Impossible chronology |
| Field-type conformance per column | Text value in a numeric column |

### 4.2 Class 2 — Conservation `the double-entry core`

- Sub-plot areas sum to parent
- Co-owner shares sum to exactly 1
- Σ khesra areas in a khata = stated khata total
- **Σ all khata areas in a mouza = mouza total area** ← the trial balance
- raiyati total + gairmazrua total = mouza total ← CAG's 3.22 lakh, detectable arithmetically in 2012
- Parent area at T = Σ child areas at T+1

### 4.3 Classes 3–7

**Class 3 — Completeness:** khesra uniqueness in a mouza · sub-division sequence gaps (217/1 and 217/3 exist, where is 217/2?) · no orphan khesra, no empty khata · one plot one classification · duplicate khata per owner.

**Class 4 — Chain continuity (the fraud detector):**
> The owner name changed between two versions of the record and there is no mutation entry explaining it. That is either a transcription error or a forged transfer. **There is no third explanation.**
Also: mutations in red ink recorded but never incorporated · survey-layer precedence (RS beats CS) · mutation without registered deed and vice versa.

**Class 5 — Text vs geometry (the independent physical witness):** stated area vs polygon area · topology overlaps (two owners, one soil) · topology gaps (land nobody claims) · Σ parcel polygons = village polygon · **chauhaddi vs map adjacency** (the record *states* its four neighbours in text; the map *knows* them — nobody has named this check) · subdivision tiling.

**Class 6 — Cross-system:** RoR ↔ registration (NGDRS) · RoR ↔ bhu-lagan revenue collection (land with no taxpayer; taxpayer with no land) · RoR ↔ government land inventory · RoR ↔ SVAMITVA property card · RoR ↔ litigation flags.

**Class 7 — Population statistics (never certain):** Benford on areas · round-number clustering (estimated not measured) · digit-confusion signature by operator or district · temporal batching (4,000 mutations on one date is data entry, not transactions) · neighbour-village outlier detection.

**Class 8 — Witness census:** not a check. Counts how many checks were *possible* per parcel.

### 4.4 Output is typed, never binary

| Verdict | Meaning | Action |
|---|---|---|
| **CERTAIN ERROR** | Grammar or conservation violated | Auto-flag. No judgement involved |
| **CONFLICT** | Two witnesses disagree | Precedence rule, else human |
| **ANOMALY** | Statistical outlier | Directs sampling. Never a finding alone |
| **UNVERIFIABLE** | No second witness exists | **Abstain — and say so.** This row is the product |

### 4.5 The deliverable DoLR lacks

> **A national map of which land records are *checkable* — and which have never been checkable by anything.** Not an error rate: a **verifiability rate**.

Computable **today**, from public data, with **no OCR**. It is the missing second axis to Bhoomi Samman's self-reported completion. ⚠ **Naming discipline:** call it a *record-quality index for the districts sampled*. Never a "National Land Record Trust Map" — overclaiming in a name is what invites the hostile question.

---

## 5. THE PIPELINE — seven layers, 34 stages

Full detail is in `SIH26018_v5_Validation_Pipeline.docx`. Summary:

| Layer | Stages | What |
|---|---|---|
| **A — Ingest** | A0 ingest · A1 restore (**red channel preserved** — red-ink entries are mutations) · A2 document typing · A3 region routing · A4 **script ID per region, not per document** · A5 router with named abstention | |
| **B — Extract** | B1 table detection · B2 TSR with confidence (below threshold → no-grid fallback, whole page to human) · B3 Reader A (PaddleOCR) · B4 value path (Qwen3-VL-8B + Reader A text, constrained decoding) · B5 evidence path (K=5 views, **image only**) · B6 field classification · B7 normalisation · B8 structural screening | |
| **C — Validate** | C1–C8, the seven classes plus witness census. **The spine.** Runs forward and backward | |
| **D — Score** | D1 feature assembly · D2 CatBoost on human labels + constraint-derived certain negatives · D3 isotonic · D4 conformal gate (hierarchical, **document as group**, 4 field groups, Bonferroni) · D5 rules as gates | |
| **E — Review** | E1 queue by **consequence × uncertainty** · E2 evidence presentation · E3 decision capture incl. **"cannot determine"** · E4 audit record · E5 reviewer quality sampling · E6 throughput | |
| **F — Platform** | F1 upload · F2 repository+metadata · F3 audit trail · F4 dashboards (the six PS names) · F5 APIs · F6 RBAC | |
| **G — Learn** | G1 correction capture · G2 constraint mining · G3 retrain, measure threshold movement at fixed α · G4 error fingerprint by district | |

### 5.1 Three design decisions that must not be undone

1. **D1 and D5 are the same rules in two roles.** D1 = features feeding the model. D5 = gates overriding it. **Say the distinction out loud** — an earlier draft ran them twice with no stated difference and a reviewer would catch it.
2. **Value path vs evidence path.** Feeding OCR text into Reader B *and* using cross-reader agreement as the confidence signal **cancel out** — agreement degenerates into self-agreement, and it degenerates *silently* because the feature still computes. Value path = image + OCR text. Evidence path = K views, image only.
3. **Conformal calibration on augmented variants is invalid.** 17 degraded copies of one document is one document. Effective N≈30 certifies ~11% error, not 1%. **Fix: hierarchical conformal, document as the group.** Augmented variants are training and stress-test material, never calibration samples. Saying this explicitly converts an attack into a demonstration of care.

### 5.2 Commodity vs moat — the honest split

| Commodity (build, never pitch) | Genuinely unbuilt (the moat) |
|---|---|
| A0 ingest, A1 restore, A3 routing | A2/A4 **per-region script ID** — transliteration is procured per-script, so nobody needed a detector |
| B1 table detection, B3 OCR, B4 value path | A5 **router with abstention** — no government system abstains, ever |
| Half of E (states have verification screens) | B8 structural screening, C1–C8, D2–D5, G1–G4 |

**Six commodity, seven unbuilt.** Extraction has three incumbents and 95% of the work is already done. **Build it because it is scored. Never lead with it.**

### 5.3 Cascade

Tier 0 (free): grammar, structural screening, OCR/TSR confidence, Classes 1–3, zero VLM calls. Tier 1 (1 pass): value path. Tier 2 (~4.5×): multi-view, **ambiguous band only**. **Report realised average cost** — if 15% reach Tier 2, effective cost ≈1.5×, not 4.5×.

---

## 6. THE BIHAR / KAITHI CAPABILITY — demoted, not deleted

Now **one bullet on slide 2**: *"It reads 1926 Kaithi without deciphering it — the 1962 survey is the answer key; published maps join the two books. Geometry is the dictionary."*

### 6.1 The idea
Two registers exist for the same mouza: **CS Khatiyan (~1926, Kaithi, unreadable)** and **RS Khatiyan (~1962, Devanagari, readable)**. Both are tables of the same land. Match the rows and every matched cell becomes a training pair — the Kaithi dataset that does not exist.

### 6.2 Three corrections that were applied (do not undo)

1. **The join must be GEOMETRIC, not textual.** `[Certain]` Bhu-Naksha serves CS and RS map layers per mouza. Join CS polygons to RS polygons by spatial overlap. This kills both objections at once: *RS renumbered the plots* (irrelevant — numbering is an output of the join, not an input) and *khatiyan is ordered by khata, not geography* (irrelevant — the map supplies the correspondence). Area conservation then becomes a geometric identity, and §4.3's geometry check and this flagship become **one mechanism**.
2. **It is one-to-many, not one-to-one.** `[Certain]` Bihar HC, *Kamleshwari Pd v. State of Bihar* (`indiankanoon.org/doc/100273071/`): *"The total area of C.S. Plot is 26 decimals whereas R.S. Khata No. 1906, of 14 decimals."* Plots were partitioned across 36 years. **Needleman–Wunsch is sequence alignment and cannot handle one row legitimately corresponding to four.** Use **Splink** (§3.5) instead — unsupervised, calibrated, many-to-many native.
3. **The corpus contamination is solvable, and it is NOT circular.** A critique argued that ownership changes over 36 years poison the name pairs, and that detecting which pairs are bad requires reading Kaithi — circular. **It is not circular; it is EM.** Seed on the columns that are stable by construction (numerals, area units, classification terms, boilerplate) → this yields a weak Kaithi glyph reader → apply it to name cells → agreement confirms continuity, disagreement is either a bad read or a genuine ownership change, routed by confidence. **Round 2 beats round 1.**
   → This also dissolves the supposed Output A / Output B conflict: high-agreement rows are corpus, low-agreement rows are the anomaly shortlist. **One computation, both outputs.**

⚠ **A critique proposed replacing the name corpus with a closed-vocabulary lexicon (~30–50 word forms). This was REJECTED.** A glossary is obtainable by one Kaithi reader in an afternoon; Bihar has ~270 trained ones. Building a geometric matcher to produce 30 words is unjustified engineering and destroys the "dataset at scale" claim.

### 6.3 Change detection — handle with care
`[Dossier]` **Most classification changes 1926→1962 are lawful.** Zamindari abolition ran through the 1950s, exactly in the gap. **Name it yourself, first** — naming it is what makes the remainder credible. And **the legal claim runs backwards**: RS (1962) is MORE authoritative than CS (1926). A 1926 entry does not defeat a 1962 entry.
→ Output is *"this row shows an unexplained classification change and warrants review."* **Never** *"here is proof your land was taken."*

⚠ Also: **do not assume the 1926 record is truthful.** `[Dossier]` Record manipulation is a documented mechanism of tribal land alienation. The CS khatiyan encodes colonial-era exclusions. Sometimes the newer record is the corrected one. Belongs on the limitations slide.

⚠ **Drop "MNIST difficulty."** Say **"ten classes instead of hundreds"** — and note the count is really 15–20 once you include the sub-division separator (217/1) and area-column fractions.

---

## 7. THE DECK — current state

**Files:** `SIH26018_Kavach_IdeaPPT.pptx` and `.pdf` (submit the PDF).

### 7.1 How it was built — reproduce this method
Built with **pptxgenjs**, using **assets extracted from the official SIH 2026 template** at the template's own EMU coordinates. Do not rebuild from scratch by eye.

```
Template: SIH2026-IDEA-Presentation-Format_20260820114449_pdf.pptx
Unzip → ppt/media/  and  ppt/slides/slideN.xml
```

Exact chrome geometry (inches, = EMU ÷ 914400):

| Element | Asset | x | y | w | h |
|---|---|---|---|---|---|
| Footer band | image5.png | 0 | 6.972 | 13.328 | 0.521 |
| Footer bar | image6.png | 0 | 6.949 | 13.333 | 0.550 |
| Team oval | image8.png | 0.277 | 0.194 | 1.536 | 1.049 |
| SIH lockup | image4.png | 10.697 | 0 | 2.460 | 1.163 |
| Hexagon (slide 1) | image1.png | 1.597 | −0.069 | 10.139 | 7.639 |
| SIH brain (slide 1) | image3.png | 7.497 | 1.877 | 3.503 | 3.747 |

- **Titles:** Times New Roman, **bold + italic, 36pt**, black, centred in a box x=1.90 w=8.70 y=0.186 (avoids oval and logo).
- **Footer text:** "@SIH Idea submission-Template", Arial 12pt white at x=5.601, y=7.020. Page number at x=12.475.
- **Slide 1 heading:** Garamond, reduced to **32pt** (template's 40pt overflows with real content).
- **Usable content band on slides 2–6: y = 1.28 → 6.90.** The oval ends at y=1.243 and the logo at y=1.163.
- Slide size: 13.333 × 7.5.
- Template's slide 7 (Important Instructions) deleted.

**Palette:** INK `0F2A44` · AMBER `C25A16` · TEAL `10716C` · RED `AE3324` · GREEN `1E7A45` · PANEL `EFF3F7` · WARM `FBF0E7` · MINT `E8F2EE` · LINE `BCCAD6`.

### 7.2 Slide contents

**1 — TITLE PAGE.** Template layout exactly. Six mandated fields. Kavach logo bottom-left. ⚠ **Team ID is still `—————`.**

**2 — IDEA TITLE.** Headline: *"KAVACH — land records are single-entry bookkeeping. We add the second entry."*
- **PROPOSED SOLUTION** (left): four verbs — Reads / Extracts / Cross-examines / Refuses
- **HOW IT ADDRESSES THE PROBLEM** (left): PLATINUM = 61% WRONG, "Both true", then the resolving sentence
- **HOW IT WORKS · CROSS-EXAMINATION** (right, the focal point): five witness cards, four green at 2.5 ha, one red at 2.1 ha, lines converging into KAVACH ENGINE, then the verdict line
- **INNOVATION AND UNIQUENESS** (bottom, three cards): says "I don't know" / its errors train it free / reads 1926 Kaithi without deciphering it

**3 — TECHNICAL APPROACH.** Six-stage pipeline full width (A–F, VALIDATE highlighted). Forward/backward line. Seven validation classes as labelled chips. Technologies (4 rows). **Prototype screenshot slot (right).**

**4 — FEASIBILITY AND VIABILITY.** Three mandated blocks left (feasibility / challenges / strategies), **KILL CRITERIA** right as the hero, coverage chips for the 12 requirements.

**5 — IMPACT AND BENEFITS.** ₹1,500-a-page quote as a full-width band. Target audience = **the tehsildar's queue, not the farmer**. Three benefit cards. Three stats. **Verifiability map screenshot slot.**

**6 — RESEARCH AND REFERENCES.** Seven-row table: source / what it establishes / reference. **Density is correct here** — it is read on paper by a screener, not projected.

### 7.3 Design rules applied (from the user's Harvard course material)
Hierarchy · repetition (identical chrome and card motif on every slide) · limited palette · **negative space**. The failure mode named in that material — *"look at all the data I have and the work I've done"* — is exactly what the first draft did. **But the mandated sub-headings are never cut in the name of whitespace.**

### 7.4 ⚠ THREE EMPTY SCREENSHOT PLACEHOLDERS
Two on slide 3, one on slide 5. **An unfilled "PASTE SCREENSHOT HERE" box reads worse than no box** — it advertises that a prototype was planned and not delivered. Either fill them (a static React mock of the reviewer queue is an afternoon's work) or delete them and rebalance. **This is the single biggest deck risk.**

---

## 8. RED-TEAM Q&A — rehearse aloud

**Isn't this just OCR plus an LLM?**
No — that's the whole project. OCR+LLM produces a value. We produce a value AND a defensible probability it's right, then refuse to commit below a threshold. Every obvious confidence signal fails: logprob 0.705 AUC, verbalized 0.692, both collapsing to all-positive classifiers. Errors are document-caused, not model-caused, so internal model confidence measures the wrong thing.

**Tamil Nadu is Platinum-graded. Are you calling DoLR wrong?**
No. The grade measures what it says it measures — completion, as reported by the State. It was never designed to measure correctness, and no instrument for that has existed. We are proposing the second instrument, not disputing the first.

**Your N is twenty records.**
It is, at document level, and we say so. Three things make it defensible: the conformal guarantee is computed at document level with documents as the exchangeable group; augmented variants are training material, never calibration samples; and the backward audit runs over hundreds of already-digital records independent of our twenty.

**Would this have prevented Tamil Nadu's 61%?**
**Not prevented. Surfaced — in 2012 instead of 2023.** We'd catch the sub-division numbered 0, missing expected records, duplicate pattas, sub-plots failing to sum. Where the paper register was itself inconsistent we flag the conflict rather than resolve it. Eleven years of wrong records propagating into transactions is the cost.

**Your reader is an 8B open model. A frontier lab beats it.**
Yes, comfortably — 86.3 chrF++ vs 75.2. We don't compete on reading. **The gate is the axis where a hackathon team beats a deployed government system, because the deployed system doesn't have one at all.** And open weights is what survives the handover requirement.

**Why not just use BHASHINI?**
We don't compete with it. Transliteration converts glyphs; it doesn't say when it's wrong. Bihar is about to run AI transliteration across crores of Kaithi records feeding a live survey that determines legal ownership, with no confidence layer. That's the CAG story one technology generation later. We supply the missing layer.

**Isn't the 1926→1962 change just Zamindari abolition?**
Mostly yes — **and we say so first.** Which is exactly why the output is a flag for human review, not a verdict. We hand a revenue officer a shortlist instead of a village.

**Revenue records don't establish title anyway.**
Correct, and it strengthens us. Patna HC holds a khatiyan neither creates nor extinguishes title. That is precisely why our output is a flag and never a ruling.

**What happens when it's confidently wrong?**
That's the residual failure mode of every confidence method — stable-but-wrong consensus — and we don't pretend otherwise. Three mitigations: validation rules as hard gates that override the model; a residual audit sample drawn from auto-committed fields; and meltdown rate as a reported metric, not a hidden one.

**Will these thresholds work in my state?**
No, and porting them would be wrong. Recalibration needs ~165 in-domain samples — a day per corpus, not a rebuild. **The method transfers; the numbers don't.**

**Can this run at national scale?**
The expensive path runs only on the ambiguous band. If 15% of fields reach it, effective cost ≈1.5× single-pass. We report realised pages/GPU-hour and extrapolate to a district.

**How did you get this data? Is it legal?**
Publicly published records from state portals, within terms of use, rate-limited, logged. Owner names redacted in every screenshot. Nothing retained beyond the demo.

**Isn't your Kaithi corpus contaminated by 36 years of ownership change?**
Partly, and the contamination is measurable rather than fatal. We seed the reader on columns that are stable by construction — numerals, area units, classification terms, boilerplate — then use that reader to filter name pairs by agreement. Rows that disagree are not discarded; they are the anomaly shortlist.

---

## 9. OPEN QUESTIONS — none resolved

| # | Question | Cost | What breaks |
|---|---|---|---|
| 1 | ⚠ **Verify the CAG Tamil Nadu findings against the primary report** — report number and paragraph | 2 hrs | **The strongest evidence on the deck is second-hand and appears three times.** A DoLR reviewer will know this audit. Cite the primary, never a summary |
| 2 | ⚠ **Does Bhu-Naksha actually populate the CS layer for a real mouza**, or is the dropdown present but empty outside pilot districts? | 30 min | Class 5 loses its independent witness. **More damaging than Q3** |
| 3 | ⚠ Does **Bhu-Abhilekh** serve paired CS+RS khatiyan for the same mouza — and are they **scans or transcriptions**? | 30 min | The Kaithi bullet becomes proposed, not demonstrated. Spine unaffected |
| 4 | Are Bihar's six "khatiyan types" (CS, RS, Raiyati, Sikmi, Bakasht, Gairmazrua) **register types on a dropdown** or **classification values inside a register**? | 1 hr | Reshapes the vocabulary-corpus and change-detection story |
| 5 | ⚠ **Team ID** for slide 1 | portal lookup | **Mandated field, currently blank** |
| 6 | ⚠ **PPT deadline and national screening date**, then re-cut the schedule | — | Everything |
| 7 | **DILRMP status after March 2026 sunset** | 1 portal check | The funding narrative. Use *"and its successor arrangements"* until resolved |
| 8 | **Two Devanagari annotators, or one?** | 1 conversation | The week 2–3 measurement gate fails by construction |
| 9 | ⚠ **Who owns the pitch outright?** | 1 decision | Six people on build tracks, the deck has nobody. Highest-risk item |
| 10 | Source the **₹1,500-a-page Kaithi line** or cut it from slide 5 | 1 hr | It is the emotional centre of slide 5 and has no entry in the reference table |
| 11 | Does **MUSTARD** (Devanagari table-extraction dataset) exist? | 30 min | Could not be confirmed. Do not put it on a deck unverified |

---

## 10. FILE INVENTORY

| File | Status |
|---|---|
| `SIH26018_Kavach_IdeaPPT.pptx` / `.pdf` | **CURRENT.** Template-exact, 6 slides. Submit the PDF |
| `SIH26018_v5_Validation_Pipeline.docx` | **CURRENT.** 18pp. Full pipeline, 7 rule classes, incumbency map, guardrails |
| `SIH26018_v4_Architecture_Guardrails_RedTeam.pdf` | **SUPERSEDED.** Contains stale slide-3 contents and "queue by ascending confidence" |
| `SIH26018_PS_Brief_and_Research_Dossier.docx` | Reference. 19pp evidence base |
| GIS/cadastral context file | Reference. Maps, ULPIN, SVAMITVA, programme landscape |

---

## 11. WHAT WAS TRIED AND REJECTED — saves rework

| Rejected | Why |
|---|---|
| **Fabricated validation results on the deck** | Contradicts the stance that makes the pitch credible; untestable at college level, fatal at national screening |
| **Digitisation as the framing** | 95% already computerised. A DoLR reviewer who administers that programme stops listening |
| **"13 requirements"** | PS numbering is corrupted. There are 12 |
| **Bihar cross-register as the flagship** | ~5 states, rests on unverified portal facts, and it is a research project inside a platform commission |
| **Needleman–Wunsch row alignment** | Sequence alignment cannot express one-to-many. Use Splink |
| **Textual (plot-number) CS↔RS join** | RS renumbered plots. Use the geometric join |
| **Closed-vocabulary Kaithi lexicon as the deliverable** | ~30 words = a glossary an afternoon of human work produces. Guts BEAT 2 |
| **Qwen2.5-VL as second reader** | chrF++ 45.4 vs Qwen3-VL-8B at 75.2 |
| **Routing on raw PaddleOCR confidence** | Softmax measures character shape, not field correctness. 0.705 AUC |
| **Feeding OCR text into Reader B AND using cross-reader agreement** | These cancel, silently |
| **Conformal calibration on augmented variants** | Violates exchangeability. Certifies ~11%, not 1% |
| **11 per-field thresholds** | Overfitting dressed as rigour. Group into 4, apply Bonferroni |
| **Modi → MoScNet branch** | 2,043-image dataset. Undemonstrable. CUT |
| **Nastaliq → Urdu recogniser branch** | No model named, weak support. CUT |
| **Stamp/seal READING** | Keep detection as a confidence feature. Reading CUT |
| **Shajra map vectorisation** | Superseded by Bhu-Naksha vectorised geometry, and ArcGIS Parcel Fabric ships topology validation. CUT |
| **"Nobody has solved Kaithi"** | FALSE — Bihar–BHASHINI MoU, July 2025 |
| **"Kaithi = MNIST difficulty"** | Overclaim. Say "ten classes instead of hundreds", note it is really 15–20 |
| **"We hand them the 1926 page proving the land was theirs"** | Legally backwards and actively harmful |
| **Bare "66% of civil litigation is land"** | Contested by an NIPFP working paper. If used: *"estimates range from ~30% to ~66% depending on court level and methodology"* |
| **"National Land Record Trust Map" as a name** | Overclaiming in a name invites the hostile question. Say *record-quality index for the districts sampled* |
| **Queue ordered by ascending confidence** | Wrong. Consequence × uncertainty |

---

## 12. THE SENTENCES THAT CARRY THE PITCH

1. **Tamil Nadu is Platinum-graded and 61% of its sampled villages have area mismatches. Both are true. The grade counts records typed, self-reported by the State. Nothing counts records that are right.**
2. **Land records are single-entry bookkeeping. Kavach adds the second entry — and land is conserved, so a village's parcels must still sum to the village.**
3. **Four witnesses agree, one dissents — so we do not merely know something is wrong. We know which record is wrong.**
4. **Every violation is a certain wrong answer that no human had to label. Our rules generate the ground truth this field has never had.**
5. **Every other system asks "what does this say?" Ours asks "should this be written down at all?"**
6. **We did not decipher Kaithi. We used the land itself as the dictionary.**

---

## 13. IMMEDIATE NEXT ACTIONS

1. **Fill Team ID** on slide 1.
2. **Resolve the three screenshot placeholders** — build a static reviewer-queue mock, or delete the boxes.
3. **Verify the CAG report** (§9 Q1). Two hours. It is the load-bearing evidence.
4. **Name the pitch owner.**
5. **Confirm the PPT deadline**, then re-cut the schedule.
6. Submit **PDF only**. Leave the Theme field reading "MedTech / BioTech / HealthTech".
