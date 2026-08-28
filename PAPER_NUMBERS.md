# PAPER_NUMBERS.md — current figures for Results & Discussion

Compiled 2026-08-23 against the repo at `main` @ `acc2ee8`. Every number below carries the
file, table, or query it came from. Items with no implementation are marked
**NOT IMPLEMENTED** rather than estimated.

---

## 0. Read this first — three things that change how you cite everything else

### 0.1 The live Postgres database is a stale snapshot. Do not cite it.

`docker compose up -d db` brings up `capstone-db` (port 5433) off the existing
`capstone-nu_pgdata` volume, created 2026-07-05. It contains **42 tables and 3 views**, all
from pipeline stages 1–2 only.

```sql
SELECT count(*) FROM information_schema.tables
WHERE table_name IN ('modeling_dataset','rigor_classification','clustering',
                     'benchmarking','schools_org_enriched','schools_org_all');
-- returns 0
```

None of the master, modeling-layer, rigor, clustering, or benchmarking tables exist in it.
Rebuilding them requires `data/updated-sheng/` (~2.6 GB, gitignored, **not present on this
machine**), so stages 3–5 cannot be re-run here.

**The authoritative current state of the project is `csv_exports/`,** which is what the README
itself says. Every figure below is computed from those CSVs unless a SQL query is shown.

The DB is still useful for one thing — it preserves the *pre-2026-08-01* CEEB crosswalk
generation, which is what §2.1 uses to date the adjudication drift.

### 0.2 There are two live rigor indices, and the frozen one is v4

| | v4 | v5 |
|---|---|---|
| Code | `etl/build_rigor_classification.py` | `etl/build_rigor_v5.py` |
| Universe | 34,392 (modeling freeze) | 45,250 (extended org export) |
| Status | **the pinned freeze** — `FREEZE_TAG = "v4_2026-08-01"` (`etl/load_modeling_layer.py:78`) | a parallel build, *not* in the freeze, not loaded into Postgres |
| Doc | `docs/RIGOR_CLASSIFICATION.md` | `docs/RIGOR_FORMULA_V5.md` |
| Attribution | team | Qifan (per `dashboard/README.md`) |

Clustering, benchmarking, predictive validation and the dashboard all sit on **v4**. v5 exists
as a full formal spec with its own audit trail but nothing downstream consumes it. **The paper
has to pick one and say which**, because they disagree substantially (§5).

### 0.3 The CEEB adjudication is one generation stale

The raw NCES↔CEEB crosswalk was regenerated on 2026-08-01; the LLM-adjudicated file on top of
it was last built 2026-07-20 and **was never re-run**. Details and both sets of counts in §2.1.

---

## 1. Master database

### 1.1 Total linked school records; public vs private split

Three different tables are all defensibly "the master". Pick deliberately and name it.

| Table | Rows | Public | Private | What it is |
|---|---:|---:|---:|---|
| `csv_exports/schools_org_enriched.csv` | **25,577** | 24,223 | 1,354 | Left join from the schools side; every row is a real federal school record |
| `csv_exports/schools_org_all.csv` | 53,970 | — | — | Full outer join (schools ∪ org records) |
| `csv_exports/modeling_dataset_v4_2026-08-01.csv` | **34,392** | **20,620** | **13,772** | **The frozen deliverable** — HS universe, grades 9–12, enrollment ≥ 30 |
| `csv_exports/rigor_classification_v5_2026-07-31.csv` | 45,250 | 32,021 | 13,229 | v5 universe (org export minus colleges) |

Source: row counts and `sector.value_counts()` on each file.

**The private counts are not comparable across these tables.** `schools_org_enriched` carries
only 1,354 private schools (the PSS-merged subset); the modeling dataset carries 13,772 because
~12,560 private rows enter as **org-only records with no school-side counterpart at all**
(`docs/MATCH_RATE_RECONCILIATION.md`). Those rows are structurally incapable of ever matching,
which is why `is_school_match` is True for only 16,111 of 34,392.

### 1.2 Match rate — quote 64.5%, and say what it is

| Rate | Arithmetic | Use it for |
|---|---|---|
| **64.5%** | 16,507 / 25,577 | The CEEB joining work itself |
| 73.8% | 16,111 / 21,832 | Modeling-dataset match quality |
| 46.8% | 16,111 / 34,392 | *Coverage only* — never call this "the match rate" |

⚠️ **`docs/MATCH_RATE_RECONCILIATION.md`, `docs/BOB_BRIEFING.md`, `docs/DATA_DICTIONARY.md`
and `docs/TEST_PLAN.md` all say 16,508.** The current file says **16,507**
(`schools_org_enriched.csv`, `nu_guid.notna().sum()`; confirmed against
`schools_features.csv`, `is_school_match == True`). Off by one since the 2026-08-01 rebuild.
Use 16,507.

### 1.3 States / territories covered

**55** — the 50 states plus DC, PR, GU, VI, MP.

Identical in `schools_org_enriched.csv` and `modeling_dataset_v4_2026-08-01.csv`
(`state.nunique()`). Note these are *territories*, not just states; phrase it as
"55 states and territories".

### 1.4 Sources actually joined into the master today, with coverage

Computed on `schools_org_enriched.csv` (N = 25,577; public 24,223 / private 1,354). "Covered"
= at least one of that source's fields is non-null on the row.

| Source | n | % of 25,577 | % public | % private |
|---|---:|---:|---:|---:|
| NCES CCD public (`nces_id_7`) | 24,223 | 94.7 | 100.0 | 0.0 |
| NCES 12-digit ELSI (`nces_id_12`) | 22,946 | 89.7 | 94.7 | 0.0 |
| NCES PSS private (`pss_id`) | 1,354 | 5.3 | 0.0 | 100.0 |
| Census SAIPE child poverty | 24,070 | 94.1 | 93.8 | 100.0 |
| Census ACS county context | 24,070 | 94.1 | 93.8 | 100.0 |
| CRDC (any `crdc_*`) | 20,325 | 79.5 | 83.9 | 0.0 |
| EDFacts assessment participation | 18,628 | 72.8 | 76.9 | 0.0 |
| FRL / lunch counts | 18,220 | 71.2 | 75.2 | 0.0 |
| EDFacts graduation rate | 17,874 | 69.9 | 73.8 | 0.0 |
| **CEEB code** | **16,865** | **65.9** | 67.0 | 47.3 |
| NU org export (`nu_guid`) | 16,507 | 64.5 | 65.6 | 46.1 |
| ISBE (`rcdts`, IL only) | 751 | 2.9 | 2.8 | 5.7 |
| ISBE per-pupil expenditure | 672 | 2.6 | 2.8 | 0.1 |
| ISBE ACT section scores | 659 | 2.6 | 2.7 | 0.1 |
| ISBE IAR proficiency | 75 | 0.3 | 0.3 | 0.1 |
| IB directory (candidate match attempted) | 1,354 | 5.3 | 0.0 | 100.0 |

**Two sources load but never reach the master.** `naep_assessments_clean` (state-level, grade-8
math/reading) and the three College Board AP state aggregates are merged into
`public_schools_enriched` / `private_schools_enriched` as `naep_grade8_*`,
`ap_pct_participation`, `ap_pct_offers_5plus_courses`
(`etl/combine_schools.py:149,245,339`) — but **those columns are dropped before
`schools_org_enriched`** and appear in neither the master nor the modeling dataset. If the
paper lists NAEP or College Board as a joined source, that is currently wrong at school level.

`cps_opportunity_index` (594 Chicago schools) likewise exists only as its own crosswalk table,
not as columns on the master.

**Feature coverage in the frozen modeling dataset**, by sector (N = 34,392; recomputed today
on `modeling_dataset_v4_2026-08-01.csv` — identical to the v3 table in
`docs/COVERAGE_BY_SECTOR.md`, so that doc is still current):

| Feature | Public % | Private % | Overall % |
|---|---:|---:|---:|
| SAT/ACT testtaker rate (CRDC) | 91.2 | 0.0 | 54.7 |
| County child poverty (SAIPE) | 95.6 | 8.8 | 60.8 |
| Graduation rate (EDFacts) | 84.5 | 0.0 | 50.7 |
| FRL rate | 83.6 | 0.0 | 50.1 |
| IB flag v2 | 74.1 | 4.5 | 46.3 |
| Dual enrollment (CRDC) | 71.3 | 0.0 | 42.8 |
| Funding (F-33 proxy) | 69.5 | 0.0 | 41.7 |
| % going to college (NU band) | 60.7 | 26.7 | 47.1 |
| AP participation (CRDC) | 59.5 | 0.0 | 35.6 |
| Avg SAT (NU) | 41.3 | 18.7 | 32.3 |
| AP qualifying density | 39.9 | 16.6 | 30.5 |
| SAT participation (NU) | 38.1 | 16.8 | 29.5 |
| # AP classes offered (NU) | 18.0 | 9.6 | 14.7 |
| ACT composite (ISBE, IL only) | 3.2 | 0.0 | 1.9 |

Every CRDC- and EDFacts-derived field is **0.0% for private schools by federal statute**. This
is the single most important coverage fact in the project and it is structural, not a matching
failure.

### 1.5 Census F-33 — **joined at national scale, not ISBE-only**

This one is worth correcting explicitly if the paper still says otherwise.

- `csv_exports/census_school_finances_clean.csv` — **14,075 districts across 51 FIPS states**
  (50 + DC), FY2024.
- Joined on `leaid` = `nces_id_12[:7]` (`etl/build_features.py:56–105`), ~87% match rate on
  rows carrying a 12-digit ID.
- **13,692 public schools** in the freeze carry the national F-33 figure
  (`funding_source == 'census_f33_per_resident_child_proxy'`).
- ISBE true per-pupil covers only **662** schools (`isbe_il_true_per_pupil`), Illinois only.
- 20,038 rows have `funding_source == 'none'` — including **all 13,770 private schools**.

**Mandatory caveat, from the docstring at `etl/build_features.py:73–82`:** F-33 has no
enrollment field, so this is **not true per-pupil spending**. It is district total revenue
divided by SAIPE's resident child population aged 5–17 — a *per-resident-child proxy*. Only the
662 ISBE Illinois rows are a true per-pupil number. Do not present the two as equivalent.

---

## 2. NCES–CEEB linkage

### 2.1 Auto-accept / review / reject — public and private

**⚠️ Two generations exist. Report the current one and note the adjudication gap.**

**Current raw crosswalk** (`csv_exports/nces_public_ceeb_crosswalk.csv`,
`nces_private_ceeb_crosswalk.csv`, both regenerated 2026-08-01, commit `8bc9bf4`):

| Tier | Public | % | Private | % |
|---|---:|---:|---:|---:|
| auto_accept | **16,187** | 66.9 | **613** | 45.3 |
| review | 2,076 | 8.6 | 208 | 15.4 |
| reject | 5,926 | 24.5 | 533 | 39.4 |
| **Total** | **24,189** | | **1,354** | |

Match method on the current build: public 15,079 `id` / 9,110 `name`; private 544 `id` /
810 `name`. The exact-ID path (12-digit ELSI bridge for public, PSS ID for private) is what
lifted auto-accept from 48.1% to 66.9%.

**Superseded generation** (still what `*_adjudicated.csv` and `docs/LLM_ADJUDICATION.md`
describe — built 2026-07-20 on the pre-`8bc9bf4` crosswalk):

| Tier | Public | Private |
|---|---:|---:|
| auto_accept | 11,636 | 510 |
| review | 5,416 | 290 |
| reject | 7,131 | 554 |
| **Total** | **24,183** | **1,354** |

After adjudication of *that* generation: public **14,096 accept / 10,087 reject**; private
**550 accept / 803 reject / 1 review**. Decision provenance
(`decision_source`, public): 11,636 original auto-accept, 7,131 original reject, 1,904
`rule_diff_city_no_subset`, 1,759 `rule_same_city_superset`, 847 `rule_diff_city_weak_name`,
450 `rule_symmetric_tokens_same_city`, **443 `llm_claude_fable_5`**, 13 `rule_city_subset`.
Private: 192 LLM-judged.

Verified by:
```
git show 5646bfc:csv_exports/nces_public_ceeb_crosswalk.csv  # 11,636 / 5,416 / 7,131
git show 8bc9bf4:csv_exports/nces_public_ceeb_crosswalk.csv  # 16,187 / 2,076 / 5,926
```
and cross-checked against the Postgres snapshot:
```sql
SELECT tier, count(*) FROM nces_public_ceeb_crosswalk GROUP BY 1;
-- auto_accept 11636 | review 5416 | reject 7131
```

**The gap:** the 2,076 public + 208 private review rows in the *current* crosswalk have never
been adjudicated. The adjudicated CSVs resolve a review set that no longer exists. Either
re-run `etl/llm_adjudicate_matches.py` before publication, or state plainly that the
adjudication figures describe a superseded build.

### 2.2 % of schools carrying a CEEB code

In the frozen modeling dataset (`modeling_dataset_v4_2026-08-01.csv`):

| Sector | n | With CEEB | % |
|---|---:|---:|---:|
| Public | 20,620 | 15,808 | **76.7** |
| Private | 13,772 | 13,183 | **95.7** |
| **Overall** | 34,392 | 28,991 | **84.3** |

⚠️ **The 95.7% private figure is an artifact, not an achievement.** Private rows overwhelmingly
enter the modeling dataset *from* the CEEB-keyed NU org export, so they carry a CEEB by
construction. The honest private CEEB match rate is the one against the federal PSS roster:
**47.3%** (640 / 1,354, `schools_org_enriched.csv`). Public in that same table: 67.0%.

### 2.3 Current thresholds

`etl/crosswalk_matcher.py:39` — `_tier(row, accept=(90, 85), accept_city=(88, 80), review=(80, 65))`:

- **auto_accept** — `token_set_ratio ≥ 90 AND token_sort_ratio ≥ 85`
  **OR** (`city_match AND token_set ≥ 88 AND token_sort ≥ 80`)
- **review** — `token_set ≥ 80 AND token_sort ≥ 65`
- **reject** — anything below
- **no_candidate** — no CEEB on the best candidate

Blocking is exact state (`src_state`), except IB which is unblocked nationwide. The two-signal
design is deliberate: `token_set_ratio` gives recall, `token_sort_ratio` guards against the
subset/generic-token inflation that lets "Academy High" score 100 against a much longer name
(`literature_review.md:127`).

### 2.4 TF-IDF token down-weighting — **NOT IMPLEMENTED**

```
grep -rin "tfidf\|tf_idf\|idf" --include=*.py etl/ tests/ dashboard/
# only matches are the substring "idf" inside "rapidfuzz"
```

It appears **only as a recommendation** in `literature_review.md:129` and again in the
future-work list at `literature_review.md:168`, motivated by Cohen, Ravikumar & Fienberg
(2003). Matching uses unweighted `rapidfuzz` token ratios throughout. There is therefore **no
before/after auto-accept rate to report.**

If the paper wants a "what we did instead" sentence: the exact-ID join (12-digit ELSI bridge)
was the change that actually widened auto-accept, from 48.1% to 66.9% — a structural fix rather
than a scoring one.

### 2.5 Agreement against the CU Boulder `ceeb_nces_crosswalk` — **NOT TESTED, and it would be circular as currently wired**

The CU Boulder crosswalk *is* the master the pipeline matches against — it is loaded as
`nces_ceeb_crosswalk_source` (21,391 rows, `data/CEEB-Crosswalk/oda_nces_ceeb_crosswalk.csv`,
CC BY-SA 4.0, upstream 2025-01-06) and consumed by `build_nces_junction()` as the source of
CEEB truth. Measuring agreement against it would be measuring the input against itself.

There **is** a genuine second, independent CEEB assignment that could be compared and has not
been: `data/updated-sheng/schools_combined_enriched_ceeb.csv`, which Sheng enriched with CEEB
via the same UC Boulder crosswalk but through a separate path (`etl/config.py:22–29`
explicitly notes the two are distinct). No comparison of the two exists in the repo. That is a
real, cheap validation the paper could either run or list as future work.

Attribution note: CC BY-SA 4.0 requires citing UC Boulder's Office of Data Analytics if this
crosswalk is used in the paper (`data/CEEB-Crosswalk/README.md`).

---

## 3. IB directory match

### 3.1 Tier counts

`csv_exports/ib_ceeb_crosswalk.csv` (IB directory → NU master CEEB), 1,893 rows:

| Tier | n |
|---|---:|
| auto_accept | **0** |
| review | 1,352 |
| reject | 541 |

The zero is deliberate, not a failure. The IBO export carries no state or city field, so the
match runs **unblocked against the entire master**; `etl/build_ceeb_crosswalk.py` therefore
forces every auto-accept down to review:

```python
ib_cw["tier"] = ib_cw["tier"].replace("auto_accept", "review")
```

`needs_review` is set *before* that demotion and equals 793 — so **559 of the 1,352 review rows
originally cleared the auto-accept thresholds** and were demoted on principle.

Against the private roster, `schools_org_enriched.csv` `ib_match_tier`: **588 review, 766
reject, 0 auto_accept** (1,354 private rows; public rows are not name-matched at all).

Related: `csv_exports/ib_nces_crosswalk.csv` (a view) has 3,042 rows for 1,893 distinct IBO
IDs — i.e. it fans out — of which 1,961 carry an `ncessch`.

### 3.2 Manually confirmed since — **yes, 73 pairs hand-adjudicated**

`docs/IB_RESCUE.md` + `csv_exports/ib_rescue_private_matches.csv` (73 rows):

| Decision | n |
|---|---:|
| accept | **18** |
| review | 9 |
| reject | 46 |

All 73 candidates (IBO DP/CP schools fuzzy-matched at `token_sort ≥ 87` against the 1,354-school
private roster) were reviewed by hand against name, city, religious affiliation and known IB
lists.

⚠️ Internal inconsistency to fix before citing: `docs/IB_RESCUE.md` says "9 review" in the
Method section but "The 7 `review`-tier private pairs are excluded" in Caveats. The file says
**9**.

**The public sector needed no matching at all.** `ib_flag_v2` takes public IB status directly
from CRDC 2021-22 (`SCH_IBENR_IND`), joined exactly on 12-digit NCESSCH — 933 public IB=yes.
In the frozen dataset:

| `ib_flag_v2_source` | IB=0 | IB=1 | total |
|---|---:|---:|---:|
| `crdc_2122` | 14,322 | **873** | 15,195 |
| `ibo_name_match_adjudicated` | 691 | **24** | 715 |
| (none — unanswered) | | | 18,482 |

897 schools flagged IB in total; 15,910 have a definitive 0/1.

---

## 4. OPE ID linkage — **implemented, and it is a stronger result than the paper probably reflects**

Careful: there are **two** OPE artifacts and they have opposite statuses.

**(a) `etl/build_ope_ceeb_junction.py` — source-gated, nothing materialized.** It degrades
cleanly (exit 0 with guidance) until an external OPE↔CEEB source is supplied. No junction file
exists. `docs/OPE_CEEB_JUNCTION.md` is the sourcing plan.

**(b) `csv_exports/ope_ceeb_crosswalk_2026-07-31.csv` — built, complete, 4,004 rows.** This is
the real deliverable. NU org export `Category = College` rows (4,004 institutions, all with
CEEB, 99.7% geocoded) matched against IPEDS HD2023 (`data/IPEDS/HD2023.csv`, 6,126 Title-IV
institutions).

Tier counts (`tier.value_counts()`):

| Tier | n |
|---|---:|
| `exact_normalized_name` | 1,900 |
| `likely_not_in_ipeds_2023` | 1,208 |
| `subset_city_or_geo` | 404 |
| `fuzzy65_geo3km` | 277 |
| `llm_adjudicated_accept` | 105 |
| `fuzzy90_city_or_geo` | 90 |
| `fuzzy55_geo1km` | 18 |
| `unmatched` | 1 |
| `review` | 1 |

**Matched = 2,794 (69.8%). Distinct OPEIDs mapped = 2,630. Residual review queue = 1.**

All 209 original review rows were adjudicated case-by-case on 2026-07-31: 105 accepted, 103
reclassified as not in IPEDS 2023, 1 left in review.

The method differs from the high-school funnel in one important way worth a sentence in the
paper: **both sides carry coordinates**, so weak name evidence is only accepted when campuses
are physically co-located (≥65 within 3 km; ≥55 within 1 km). Geography is a first-class
matching signal here, which it never is on the K-12 side.

The 1,208 "not in IPEDS 2023" rows are a **finding, not a failure** — ITT Tech, DeVry/Kaplan/
Rasmussen sites, hospital nursing schools, closed trade schools. It mirrors the high-school
result: the NU master list carries a historical tail that no longer maps to the live
institutional landscape.

Bonus for the platform argument: `UNITID` ships alongside `OPEID` in every matched row, which
keys the entire IPEDS universe.

---

## 5. Rigor classification

**Decide v4 vs v5 before writing this section.** Both are complete; they disagree at
ρ = 0.723 with **63.1% of schools changing tier** between them (`rigor_v5_audit`,
17,882 schools compared).

### 5.1 Features and weights

**v4 — the frozen index** (`etl/build_rigor_classification.py:81–120`), 6 components, 5 with
weight:

| Component | Sub-features | Nominal | Effective |
|---|---|---:|---:|
| AP opportunity | `ap_tests_taken`, `number_of_ap_classes_offered_mid`, `ap_take_rate` | 0.25 | 0.206 |
| **AP performance** | `ap_qualifying_density` | 0.20 | **0.310** |
| CRDC coursework | `ap_participation`, `dual_enrollment_rate`, `ib_intensity_v2` | 0.20 | 0.174 |
| Test participation | `testtaker_rate`, `sat_participation_nu` | 0.15 | **0.080** |
| **Test performance** | `sat_score_nu`, `act_composite_il` | 0.20 | 0.230 |
| IB | `ib_flag_candidate` | **0.00** | — (sensitivity only) |

Effective weights from the standard variance decomposition
(`effective_weights()`, `build_rigor_classification.py:193`), computed on the 8,124-school
full-coverage subset, composite variance 0.2630. Source: `docs/RIGOR_CLASSIFICATION.md:114–132`.

**v5** (`etl/build_rigor_v5.py`), 9 components — `csv_exports/rigor_v5_weights_2026-07-31.csv`:

| Component | Nominal | Effective |
|---|---:|---:|
| AP opportunity | 0.15 | 0.129 |
| **AP performance** | 0.20 | **0.364** |
| Advanced access | 0.10 | 0.096 |
| IB | 0.05 | 0.017 |
| STEM depth | 0.10 | 0.031 |
| **Test performance** | 0.20 | 0.247 |
| Test participation | 0.05 | 0.015 |
| College placement | 0.10 | 0.079 |
| Faculty investment | 0.05 | 0.022 |

Grouped by client factor: advanced curriculum 0.60, test scores 0.25, college placement 0.10,
faculty 0.05. Client factors 5 (extracurricular breadth) and 6 (GPA, competitions) carry **no
component** — no national dataset exists for either.

**The headline methodological finding reproduces in both versions and strengthens in v5:** AP
performance is assigned 0.20 and contributes **0.310 (v4) / 0.364 (v5)** of index variance,
while test *participation* is assigned 0.15/0.05 and contributes **0.080 / 0.015**. v5's
re-weighting of participation 0.15 → 0.05 was correctly directed but, by its own diagnostic,
could go further.

### 5.2 Tier distribution

**v4** — `rigor_classification_v4_2026-08-01.csv`, 21,951 of 34,392 scored (19,137 public /
2,814 private):

| Tier | n |
|---|---:|
| Below Average | 4,042 |
| Average | 8,832 |
| Demanding | 6,329 |
| Very Demanding | 2,403 |
| **Most Demanding** | **345** |
| *(unscored)* | *12,441* |

**v5** — `rigor_classification_v5_2026-07-31.csv`, 22,869 of 45,250 scored (17,015 public /
3,250 private), Jenks cut-points −0.704 / −0.207 / +0.286 / +0.977:

| Tier | n |
|---|---:|
| Below Average | 2,868 |
| Average | 7,299 |
| Demanding | 7,211 |
| Very Demanding | 4,050 |
| **Most Demanding** | **1,441** |
| *(unscored)* | *22,381* |

v5 also ships a **within-sector** track (`rigor_tier_label_v5_sector`): 2,036 / 5,990 / 6,771 /
4,193 / 1,275, with 24,985 unscored. Under within-sector standardization the top tier is
**1,270 private and 1,179 public** — against a pooled split that strongly favours public
schools with full CRDC coverage. `docs/RIGOR_FORMULA_V5.md:§11` calls this a **client
decision, not a modelling one**, and ships both without setting a default. That is a good
Discussion paragraph.

Equal-frequency quintiles are emitted alongside as a cut-point sensitivity check; the two
schemes agree for **58.4%** of scored schools (v5) — down from v3's 49%… i.e. *up*; either way
the cut method is consequential, not cosmetic.

### 5.3 Sensitivity analysis

**v4** — `csv_exports/rigor_sensitivity_v4_2026-08-01.csv`:

| Scheme | n compared | Spearman ρ | Schools changed tier | % changed |
|---|---:|---:|---:|---:|
| `equal` | 21,951 | 0.9945 | 1,549 | 7.1 |
| `performance_heavy` | 21,951 | 0.9763 | 3,987 | 18.2 |
| `availability_only` | 21,802 | 0.8935 | 6,990 | **32.1** |
| `ib_included` | 21,951 | 0.9714 | 9,799 | **44.6** |

**v5** — `csv_exports/rigor_v5_sensitivity_2026-07-31.csv`, reported two ways because refitting
Jenks conflates score movement with cut-point movement:

| Scheme | n | Spearman ρ | % changed (Jenks refit) | % changed (frozen cuts) |
|---|---:|---:|---:|---:|
| `v4_equivalent` | 21,312 | **0.879** | 43.1 | **32.3** |
| `equal` | 22,186 | 0.950 | 23.2 | 26.1 |
| `performance_heavy` | 20,380 | 0.959 | 26.0 | 24.3 |
| `no_new_factors` | 21,294 | 0.922 | 43.9 | 24.9 |

The frozen-cut-point column is the more honest one — it isolates score movement from cut-point
movement. **Roughly a quarter of schools move tier under *any* re-weighting.** State that; it
is the correct characterisation of specification uncertainty in a designed composite.

Additional v5 scenario — **CRDC loss** (zeroing the three CRDC-dependent components among the
11,290 schools with CRDC signal): ρ = **0.958**, **40.5% change tier**. CRDC remains the single
largest external dependency.

### 5.4 Correlation with the funding / poverty overlay

Computed today on `clustering_v4_2026-08-01.csv` (pairwise complete, `scipy.stats`):

| Overlay | n | Spearman | Pearson |
|---|---:|---:|---:|
| NU socio-need index | 11,095 | **−0.541** | −0.466 |
| Free/reduced lunch rate | 16,146 | **−0.347** | −0.269 |
| District child poverty (SAIPE) | 19,426 | −0.119 | −0.064 |
| F-33 per-resident-child funding (state+local) | 14,068 | +0.057 | +0.068 |
| F-33 per-resident-child funding (total) | 14,068 | +0.028 | +0.044 |
| ISBE true per-pupil (IL only) | 659 | −0.054 | −0.035 |

⚠️ **The −0.11 figure the docs quote is the weakest of these.** `docs/RIGOR_CLASSIFICATION.md`
and `docs/BENCHMARKING.md` both cite ρ(rigor, child poverty) = −0.110 as evidence the index is
only lightly SES-entangled. That is true for SAIPE *county* poverty, but the index correlates
at **−0.347 with school-level FRL** and **−0.541 with NU's own socio-need index**. County-level
poverty is the most attenuated available measure of school poverty. If the paper leans on
−0.11, it is picking the friendliest of six numbers — cite FRL alongside it.

Funding correlation is essentially **zero** (+0.06). The rigor index is not a funding proxy.

**v5 entanglement is materially higher and openly reported**
(`rigor_v5_ses_entanglement_2026-07-31.csv`): ρ(R, child poverty) moves from **−0.168 (v4) to
−0.323 (v5)** on the v5 universe. Per component: test performance −0.392, AP performance
−0.391, AP opportunity −0.230, STEM depth −0.213, faculty investment −0.192, advanced access
−0.188, college placement −0.166, IB −0.047, test participation **+0.044**. This is the
predicted cost of shifting toward exam performance.

**v5's remedy (Layer 5, opportunity-adjusted rigor)** is a genuinely good Discussion result:
regress rigor on child poverty + FRL and keep the residual. Context explains R² = 0.209 across
19,150 schools; the residual's poverty correlation is **−0.028**, effectively zero. The raw
tier puts 69 high-poverty schools in the top tier; the residual surfaces **343** high-need
overperformers — a **5×** increase. Named examples pass inspection (Bronx Science, Brooklyn
Tech, J. R. Masterman, Metro High St. Louis, Eleanor Roosevelt). 1,915 overperformers total.

⚠️ **Tier means on poverty are NOT monotone in v4.** Mean county child poverty by tier:
Below Average 16.51, Average 15.56, Demanding 14.44, Very Demanding 14.80, **Most Demanding
16.72**. The v5 validation table *is* monotone (18.2 → 17.3 → 14.2 → 12.6 → 12.0). Another
point in v5's favour if you are choosing.

### 5.5 Per-school logging of available features — **implemented, in both versions**

- **v4**: `rigor_components_available` (e.g. `['ap_opportunity','test_participation']`),
  `rigor_n_components_used`, `rigor_weighting_scheme` (`designed`), `rigor_tier_method`
  (`natural`), `rigor_component_spec` (`v4`) — every row, `rigor_classification_v4_2026-08-01.csv`.

  Distribution of `rigor_n_components_used`: 0 → 12,441 · 1 → 1,784 · 2 → 8,703 · 3 → 1,187 ·
  4 → 2,153 · 5 → 8,124.

- **v5**: `components_available`, `n_components`, `weight_covered` (ω, the share of index weight
  present), `below_coverage_floor`, plus all nine raw component scores `C_*`.

v5's `weight_covered` is the better instrument — it records *how much index weight* a school
had, not just how many components.

### 5.6 ⚠️ A documented, unresolved defect in the frozen v4 index

`docs/COVERAGE_BIAS.md` Part 2 is labelled **"a blocking finding for model sign-off"** and it
is still unresolved in the frozen v4 layer. It belongs in the Discussion.

**Finding: 74% of the "Most Demanding" tier (217 of 295 at the time) is scored on ≤2 of 5
components.** 55 of 295 on a single component. Breakdown: `crdc_coursework` + `test_participation`
154 · `test_participation` **alone** 48 · four components 40 · all five 26.

**Root cause: proportional weight reallocation.** A school with one available component gets a
composite equal to that single z-score with weight reallocated to 1.0; a school with five gets
an *average*, which regresses to the middle. Coverage therefore determines variance:

| Components used | SD of `rigor_score` | % reaching top tier |
|---|---:|---:|
| 1 | 1.052 | **3.08%** |
| 5 | 0.513 | **0.32%** |

**A one-component school is ~10× more likely to reach "Most Demanding" than a five-component
school**, purely as an artifact of how many numbers were averaged.

The concrete failure: **New Trier — 4 components, real AP and test data — scores 1.329, below
the 1.924 cut, and sits in Very Demanding**, outranked by 200-student early-college programs
carrying no AP data at all. Top-tier median enrollment is 200 vs 447 overall.

**v5 fixes exactly this** with the coverage floor ω ≥ 0.25 (`RIGOR_FORMULA_V5.md:§6`): maximum
score drops from 7.66 to 3.33, and 6,167 schools become unscored (2,644 private, 804 public).
`docs/COVERAGE_BIAS.md` independently proposed the ≥4-component rule (top-tier median
enrollment 1,246; New Trier lands in Most Demanding; tiered population halves to 10,277).

**Either adopt v5 as the headline index, or report the v4 top tier with this caveat attached.**
Citing "345 schools, about one percent — a genuine national elite set" without it would not
survive scrutiny.

### 5.7 Coverage bias — who has data (Part 1 of the same doc)

Also Discussion material, and it is a clean result:

- Of 44,899 org records, only **3,630 (8.1%) have ever been visited** by NU.
- NU-sourced fields populate at **~89% where NU has visited, ~21% where it has not** — a
  consistent ~68 pp gap across every gated field.
- Gets a rigor score at all: **98.5% visited vs 60.3% never-visited.**
- Mean rigor score: **+0.445 visited vs −0.118 never-visited.**
- Holding data availability constant (full-coverage subset, n = 2,845), **~79% of the score gap
  survives** — so it is mostly NU visiting genuinely stronger schools, not the index
  manufacturing a gap. (Caveat: that subset is not random.)
- "Visited" is only modestly a proxy for affluence: mean county child poverty 12.67% visited
  vs 15.92% never-visited.

The tension worth naming explicitly: **the 4,218 schools missing from the NU list are by
construction never-visited, and therefore the population the index can least reliably score.**
The discovery story and the rigor story pull against each other.

---

## 6. Clustering

**⚠️ `docs/CLUSTERING.md` documents v3 (k=4) and is stale.** The current artifacts are v4
(k=8). Numbers below are recomputed from `clustering_v4_2026-08-01.csv`; I verified the
reconstruction reproduces the stored PCA scores to 4.4e-16 and the stored labels at ARI = 1.0000.

### 6.1 Algorithms run

**K-means** and **agglomerative hierarchical**, both at the selected k, on the retained PCA
components (`etl/build_clustering.py:241–243`). No other algorithm (no DBSCAN, no GMM).

Adjusted Rand Index between the two partitions at k=8: **0.353** (v3 was 0.39 at k=4).
Moderate — consistent with weak separation.

**Complete-case coverage: 5,837 of 34,392 schools (17.0%).** No imputation. The clustering
result describes a specific, non-random subset — schools with region, funding, *and* academic
signal simultaneously. This must be stated alongside any clustering claim.

Features (`clustering_features_used`): 4 region one-hots + `ap_opportunity`,
`crdc_coursework`, `test_participation`, `grad_rate`, `funding`, `poverty`.
`region_Illinois` is dropped automatically as constant-zero in the subset.
**`rigor_score` is deliberately NOT an input** — otherwise the "do clusters just reproduce the
rigor tier?" check would be circular.

### 6.2 Gap statistic — selected k = 8, **but by fallback, not by an optimum**

`csv_exports/gap_statistic_v4_2026-08-01.csv`:

| k | gap | s_k |
|---:|---:|---:|
| 2 | 2.4268 | 0.0041 |
| 3 | 2.4806 | 0.0026 |
| 4 | 2.5017 | 0.0048 |
| 5 | 2.5149 | 0.0051 |
| 6 | 2.5336 | 0.0048 |
| 7 | 2.5530 | 0.0040 |
| 8 | **2.5641** | 0.0062 |

**The gap is monotonically increasing across the entire search range.** The Tibshirani
one-standard-error rule (`Gap(k) ≥ Gap(k+1) − s_{k+1}`) never fires, so the implementation
falls through to `chosen_k = k_range[-1]` (`build_clustering.py:146`) — i.e. **k=8 is the
maximum of the grid searched (k=2..8), not an interior optimum.**

I verified this by re-running the selection rule over all three gap files:

| Version | Rule outcome | Clusters in file |
|---|---|---:|
| v1 | 1-SE rule fired at k=4 | 4 |
| v3 | 1-SE rule fired at k=4 | 4 |
| **v4** | **fallback = max(k); rule never fired** | **8** |

**This is a real methodological caveat and the paper should not report "the gap statistic
selected k=8" without it.** Either widen the grid until the gap turns over, or report k=8 as a
boundary solution. That v3 found an interior k=4 on nearly the same data makes the v4 boundary
result more suspicious, not less.

### 6.3 Silhouette scores — **not persisted; recomputed here**

`silhouette_sweep()` prints to stdout only and writes to no CSV, so no v4 silhouette figure
exists in the repo. I recomputed the exact sweep on the stored PCA space (re-fit KMeans matches
the stored labels at ARI = 1.0000, so these are the real values):

| k | silhouette |
|---:|---:|
| 2 | **0.2738** ← maximum |
| 3 | 0.1995 |
| 4 | 0.1970 |
| 5 | 0.1923 |
| 6 | 0.1732 |
| 7 | 0.1809 |
| **8** | **0.1820** ← selected |
| 9 | 0.1846 |
| 10 | 0.1819 |

**Silhouette at the selected k=8 is 0.182; neighbours are 0.181 (k=7) and 0.185 (k=9).** The
best score anywhere is **0.274 at k=2**, only just above the conventional 0.25 threshold, and
the selected k sits well below it.

Gap (k=8) and silhouette (k=2) **disagree**, and the script says so in its own output rather
than picking the convenient one. Per `build_clustering.py:237`, weak silhouette is reported as
**a finding about the data**: the complete-case population has weak natural cluster separation;
groups blur rather than forming tight regions. Hold that line in the paper.

### 6.4 PCA

Recomputed exactly (`PCA()` on the 10-feature complete-case matrix):

| Component | Explained | Cumulative |
|---|---:|---:|
| PC1 | **33.83%** | 33.83% |
| PC2 | **16.49%** | 50.32% |
| PC3 | 15.72% | 66.04% |
| PC4 | 9.42% | 75.46% |
| PC5 | 8.31% | 83.78% |
| PC6 | 7.44% | **91.21%** |
| PC7–PC10 | 3.85 / 3.14 / 1.80 / 0.00 | 100% |

**6 components retained** (the first count reaching ≥90% cumulative), 91.21% variance — a
modest reduction from 10 features.

Loadings on the first two (`pca_loadings_v4_2026-08-01.csv`):

| Feature | PC1 | PC2 |
|---|---:|---:|
| funding | **0.787** | 0.443 |
| poverty | **−0.480** | **0.758** |
| region_Northeast | 0.250 | 0.168 |
| region_South | −0.219 | −0.033 |
| crdc_coursework | 0.139 | −0.211 |
| ap_opportunity | 0.117 | −0.120 |
| grad_rate | 0.066 | −0.165 |
| test_participation | −0.053 | −0.316 |
| region_Midwest | −0.027 | −0.114 |
| region_West | −0.003 | −0.020 |

**PC1 is a "regional wealth" axis** — funding against poverty, Northeast positive, South
negative. Same interpretation as v3.

⚠️ **PC2 changed meaning between v3 and v4.** In v3, PC2 (17.6%) was an "academic intensity"
axis loading on test participation, CRDC coursework and AP opportunity. In v4, PC2 loads
primarily on **poverty (0.758) and funding (0.443)** — a second socioeconomic axis, with the
academic features entering only weakly and *negatively*. If the paper carries forward v3's
"PC2 = academic intensity, separate from PC1" reading, that no longer holds.

Collinearity (v3 figures, unchanged in kind): funding ↔ region_Northeast **0.68**,
funding ↔ region_South −0.41, poverty ↔ funding −0.29, ap_opportunity ↔ crdc_coursework 0.35.

### 6.5 Do clusters reproduce socioeconomic ordering? — **yes, visibly**

Recomputed on `clustering_v4_2026-08-01.csv` (raw means, k=8):

| Cluster | n | Mean rigor tier | Mean rigor score | Mean funding | Mean poverty % | Mean grad rate | Mean socio-need |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 724 | 2.00 | +0.38 | $12,632 | 13.5 | 94.6 | 43.9 |
| 1 | 1,044 | 0.89 | −0.36 | $12,469 | 13.1 | 89.4 | 50.4 |
| 2 | 1,029 | 1.43 | −0.02 | $21,369 | 11.6 | 91.2 | 33.1 |
| 3 | 438 | 1.98 | +0.35 | **$32,518** | **9.4** | 92.6 | **27.4** |
| 4 | 741 | 1.53 | +0.04 | $15,027 | 12.0 | 92.4 | 39.0 |
| 5 | 839 | 0.90 | −0.34 | $13,172 | **24.6** | 87.4 | **65.1** |
| 6 | 25 | 2.40 | +0.73 | $16,209 | 12.9 | 89.4 | 48.6 |
| 7 | 997 | 1.10 | −0.23 | $14,064 | 11.4 | 89.2 | 41.7 |

**Between-cluster variance in mean rigor tier: 0.167 against overall 0.638 — 26.3% of
rigor-tier variation sits between clusters** (v3 was ~45% at k=4; the drop is expected with
more, smaller clusters).

The socioeconomic ordering is unmistakable at the extremes: **cluster 3** is the
well-funded/low-poverty/high-rigor group ($32.5k, 9.4% poverty, tier 1.98) and **cluster 5** is
its mirror image (24.6% poverty, socio-need 65.1, tier 0.90, lowest grad rate 87.4). That is
exactly the pattern the composite-indicator literature warns to watch for.

But it is **not** a pure SES re-description, and the counterexamples matter: **cluster 0**
reaches tier 2.00 — statistically tied with cluster 3 — on **$12,632** funding, less than
40% of cluster 3's, with the highest graduation rate in the table (94.6). Clusters 0 and 3
have near-identical rigor and wildly different resources. `cluster_profiles_v4` labels them
"high rigor, high testtaker rate" and "high funding, high rigor" respectively.

Cluster 6 (n=25) is too small to generalise from.

Interpretable auto-labels and z-scored profiles: `csv_exports/cluster_profiles_v4_2026-08-01.csv`
(`etl/build_cluster_profiles.py`).

---

## 7. Benchmarking

### 7.1 SAT/ACT coverage at school level

`csv_exports/benchmarking_v4_2026-08-01.csv` (34,392 rows):

| Measure | n | % overall | % public | % private |
|---|---:|---:|---:|---:|
| `sat_score_nu` (mean SAT) | **11,098** | **32.3** | 41.3 | 18.7 |
| `sat_participation_nu` | 10,155 | 29.5 | 38.1 | 16.8 |
| `testtaker_rate` (CRDC SAT/ACT) | 18,804 | 54.7 | 91.2 | **0.0** |
| `act_composite_il` | **657** | **1.9** | 3.2 | 0.0 |

**ACT is not benchmarked.** At 1.9% national coverage (Illinois only) it is too sparse for a
national pass; `docs/BENCHMARKING.md` leaves it for a future IL-specific comparison.

Selection-bias caveat that must travel with every SAT figure: `sat_score_nu` is NU's average
**freshman** SAT among students who reported it during college search — skewed toward
college-going, NU-engaged families, not a random sample of each school's students.

Rigor-tier validation (the strongest external check in the project — SAT is not a v4 input in
the tier being validated here):

| Rigor tier | n | Mean SAT |
|---|---:|---:|
| Most Demanding | 89 | 1,288 |
| Very Demanding | 1,335 | 1,234 |
| Demanding | 3,785 | 1,168 |
| Average | 4,831 | 1,126 |
| Below Average | 1,058 | 1,066 |

**Cleanly monotonic, 222-point spread, no inversions.**

SES-reproduction check: ρ(SAT, child poverty) = **−0.385** vs the rigor tier's −0.110 —
**~3.5× stronger**. This is direct empirical support for building rigor from curricular
opportunity rather than test scores. (But see §5.4 — the −0.110 comparator is the most
attenuated poverty measure available; against FRL the rigor index is at −0.347 and the ratio
is closer to ~1.1×. The qualitative conclusion holds; the 3.5× multiplier does not.)

### 7.2 Section-level scores — **composites only in the modeling layer; ACT sections exist upstream, SAT sections do not exist at all**

- **SAT: composite only.** `sat_score_nu` is a single number from the NU org export. No
  EBRW/Math split exists anywhere in the repo — I grepped every ISBE export for SAT section
  columns and found none.
- **ACT: section-level data exists but is collapsed before use.**
  `csv_exports/isbe_act_clean.csv` carries `act_ela_average_score_grade_11`,
  `act_math_average_score_grade_11`, `act_science_average_score_grade_11` (plus PreACT by grade
  and demographic subgroup). But `etl/build_features.py:185` reduces them to a single field:

  ```python
  out["act_composite_il"] = pd.concat([num(c) for c in act_cols], axis=1).mean(axis=1)
  ```

  ⚠️ So `act_composite_il` is the **arithmetic mean of three section scores**, not a true ACT
  composite (which is a 4-section average including Reading). Do not describe it as an ACT
  composite score without that qualification.

Illinois section-level ACT is therefore available for a future subject-specific pass
(~659 schools), and the paper can say so accurately.

---

## 8. Validation / reproducibility

### 8.1 Train/test split — **implemented; train/test only, no third validation split**

`etl/build_predictive_validation.py:82` —
`train_test_split(cc.index, test_size=0.2, random_state=SEED)` with `SEED = 42`. **80/20, no
separate validation set**, no cross-validation. Say "train/test", not "train/test/validation".

`csv_exports/predictive_validation_metrics_v4_2026-08-01.csv`:

| Spec | Block | Linear R² | GBM R² | n_train | n_test |
|---|---|---:|---:|---:|---:|
| main | SES only | 0.3698 | 0.3733 | 1,352 | 339 |
| main | Opportunity only | 0.2141 | 0.2299 | 1,352 | 339 |
| main | SES + Opportunity | 0.4201 | 0.4284 | 1,352 | 339 |
| main | **Incremental** | **+0.0503** | **+0.0552** | | |
| crdc_only | SES only | 0.1998 | 0.2715 | 4,926 | 1,232 |
| crdc_only | Opportunity only | 0.1035 | 0.1334 | 4,926 | 1,232 |
| crdc_only | SES + Opportunity | 0.2348 | 0.3382 | 4,926 | 1,232 |
| crdc_only | **Incremental** | **+0.0349** | **+0.0667** | | |
| robustness_all_rows | SES + Opportunity (GBM) | | 0.5170 | 13,936 | 3,484 |

⚠️ `docs/PREDICTIVE_VALIDATION.md` quotes the 2026-07-24/26 run (0.419 / +0.049 / +0.046 and
robustness 0.515). The current CSV is the 2026-08-01 rerun and differs slightly (0.4201 /
+0.0503 / +0.0552, robustness 0.517). **Cite the CSV, not the doc.**

Design safeguards worth a sentence: opportunity features only as predictors (exam-performance
components excluded to avoid predicting outcomes from outcomes); SES-incremental design; public
schools only (EDFacts has no private schools); target is a COVID cohort, privacy-blurred and
ceiling-compressed (median 91), so R² ceilings are structural.

Permutation importance: `frl_rate` dominates at **0.506**, then `ap_participation` 0.066,
`testtaker_rate` 0.050, `sat_participation_nu` 0.038.

**Headline:** opportunity structure carries **+0.035 to +0.067 incremental R² beyond SES**,
stable across two very different specifications and both model families — but SES remains the
dominant predictor of graduation.

### 8.2 Row-count and schema assertions — partial

I ran the suite today:

```
python -m pytest tests/ -q
# 77 passed, 2 skipped in 20.12s
```

The 2 skips are both in `tests/test_docker_pipeline.py` — they require a running Docker daemon
**and** `data/updated-sheng/` present locally (absent here).

Coverage by kind:
- **Unit tests (77 passing)** — z-scoring, proportional weight reallocation, tier assignment,
  bucket-midpoint parsing, winsorization, sector flags, LEAID derivation, AP take-rate,
  name normalization, CEEB fan-out resolution, freeze-tag resolution.
- **Row-count assertion — exactly one, and it is loose.**
  `test_schools_org_all_row_count_matches_csv_path` asserts `count > 50_000` against
  `SELECT COUNT(*) FROM schools_org_all` (production scale 53,966). It is a smoke check, not a
  regression guard — a 20% row loss would pass.
- **Schema assertions — none.** No test asserts column presence, dtype, or column count on any
  output table.
- `test_load_modeling_layer.py` does enforce the freeze pin properly: newer files at the same
  version are ignored, higher versions are ignored while pinned, and there is no
  "newest wins" fallback.

### 8.3 Pipeline runtime

**~106 seconds** for stages 1–5 (`docker compose run --rm etl`), verified once on 2026-07-17
(`docs/TEST_PLAN.md:27,124,188,375`). At that run `schools_org_all` = 53,966 rows and the CEEB
match count (16,508) matched the CSV path exactly, cross-validating the DB and CSV paths.

**There is no timing instrumentation in the code** — `etl/run_all.py` has no `time`,
`perf_counter`, or elapsed logging. The 106 s is a single hand-observed measurement on one
machine, not a reproducible benchmark. The modeling layer (`run_modeling_layer.py`) has no
recorded runtime at all.

I could not re-verify it: `data/updated-sheng/` is absent, so stages 1–5 cannot run here.

### 8.4 Cross-machine reproducibility — **NOT IMPLEMENTED**

No cross-machine or cross-platform reproducibility test exists. `docs/TEST_PLAN.md:250` lists
it as **planned**: "UAT round 2 (peer team), before Week 9 presentation prep — the engaged
other team independently reproduces one pipeline run." That has not happened.

What *does* exist:
- Fixed seeds throughout (`random_state=42` in KMeans, gap statistic, train/test split).
- The freeze-tag pin, which prevents silent drift of the modeling layer.
- DB-path vs CSV-path cross-validation on one row count (§8.2).

What blocks it, honestly stated: `data/updated-sheng/` is 2.6 GB and gitignored (a single CRDC
file is 794 MB; two EDFacts files are 938 MB and 875 MB, each over GitHub's 100 MB limit). A
fresh clone or CI runner must download it manually from the team Drive folder. `TEST_PLAN.md`
flags a small sanitized fixture as the remaining nice-to-have that would let this path run in CI.

Also explicitly out of scope per the test plan: load/performance testing (batch ETL, re-run at
most annually) and security testing (no external API or auth surface).

---

## 9. Finished in the repo, but the paper probably doesn't know about it

Ordered by how likely each is to earn a place in the write-up.

### Strong candidates — substantial finished work with its own documentation

1. **The v5 rigor index** — `etl/build_rigor_v5.py` + `docs/RIGOR_FORMULA_V5.md` (16 KB formal
   spec) + 8 output artifacts including a full audit CSV. Nine components across four client
   factors, a coverage floor that fixes the §5.6 defect, an opportunity-adjusted residual
   measure, a within-sector track, and validation against five external measures (monotone on
   every column, graduation rate rising 69.8 → 95.5). This is a complete second index that
   nothing downstream consumes.

2. **Coverage bias / visit bias analysis** — `etl/build_visit_bias.py`, `docs/COVERAGE_BIAS.md`,
   `visit_bias_v4_2026-07-28.csv` (34,392 rows). Contains both the recruiting-footprint finding
   (§5.7) and the **blocking top-tier defect** (§5.6). The defect in particular cannot be
   omitted if v4 tiers are reported.

3. **OPE↔CEEB college crosswalk** — 2,794 of 4,004 college codes matched (69.8%), 2,630 distinct
   OPEIDs, geographic verification as a first-class matching signal, full adjudication of all
   209 review rows. Satisfies a stated secondary project goal (§4). Docs:
   `OPE_CEEB_CROSSWALK.md`, `OPE_CEEB_MERGE_REPORT.md` (+ PDF).

4. **College-side clustering** — `etl/build_college_clustering.py`,
   `college_clustering_2026-08-02.csv` (2,381 colleges), coarse k=2 and fine k=6 partitions,
   profiles in `college_cluster_profiles*.csv`, coverage table, and
   `docs/COLLEGE_CLUSTERING_REPORT.pdf`. Built on College Scorecard + IPEDS joined through the
   OPE↔CEEB crosswalk. An entire second clustering study on the postsecondary side.

5. **Federal-roster vs NU-list coverage study** — `docs/COVERAGE_REPORT.md` (+ PDF),
   `nu_list_name_crosswalk_2026-07-27.csv`, `nu_list_missing_schools_2026-07-27.csv` (4,218
   rows). Five-tier match funnel with per-row rule labels (`ceeb_exact` 14,397,
   `exact_normalized_name` 3,988, `subset_same_city` 2,311, `fuzzy90_same_city` 93,
   `subset_multi_token` 570). Bidirectional rates: 70.1% of the NU list enters our universe;
   83.5% of our roster links to a NU record. A **geographic audit** validates it — median
   NU-vs-NCES coordinate discrepancy **1.0 km** across 15,263 matched public schools, 94.3%
   within 10 km, with 364 pairs >50 km as a standing QA list. Includes the **confirmed
   2000s-cohort blind spot**: five mega-schools (2,861–4,291 students, all opened 2001–2003)
   proven absent while their district neighbours are present.

6. **Predictive validation** (§8.1) — if the paper has no predictive-validity section, this is a
   ready-made one grounded in Adelman (1999, 2006).

### Worth a mention or an appendix line

7. **The Streamlit dashboard** — `dashboard/app.py`, five pages including a *live* rigor-formula
   explorer that imports the pipeline's own scoring functions (so it reproduces rather than
   reimplements) and recomputes tiers, Spearman vs the shipped scheme, % changed, and
   nominal-vs-effective weights as you move the weights. Strong "platform, not just a study"
   evidence.

8. **LLM adjudication as a reusable method** — `etl/llm_adjudicate_matches.py`,
   `docs/LLM_ADJUDICATION.md`. Deterministic rules resolve ~88% before any tokens are spent;
   the LLM judges only the residual (635 pairs). Provenance is recorded per row
   (`decision_source = llm_claude_fable_5`) so any decision is filterable and revisitable. A
   defensible hybrid-matching contribution — but see §2.1, it needs a re-run.

9. **AP efficiency analysis** — `etl/build_rigor_analysis.py`, `docs/RIGOR_SCENARIOS.md`,
   `ap_efficiency.png`. `ap_efficiency = z(AP score) − z(AP tests offered)` with a 2×2 quadrant
   on 10,504 schools: 3,687 broad & high-performing, 3,429 limited, 1,791 broad but
   underperforming, and **1,597 "selective & effective"** — the client's "low offering, high
   scores" case, almost all ranked below the top tier by the additive composite. Directly
   answers a named client question.

10. **Data-quality review queues** — `ceeb_padding_shift_flagged.csv` (644 rows, CEEB
    digit-corruption / zero-padding shift), `review_generic_ceeb_codes.csv` (31),
    `review_correctional_facilities_modeling_v4.csv` (48). Concrete evidence of systematic QA.

11. **Two data dictionaries** — `docs/DATA_DICTIONARY.md` + CSV (127 variables on the raw joined
    table) and `csv_exports/data_dictionary_modeling_dataset.csv` (57 variables on the freeze,
    with source, grain, vintage, confidence, range, % non-null). Plus
    `DATA_DICTIONARIES_2026-08-02.xlsx` and `etl/data_provenance.py`, which generates a
    23-row source-provenance table (`docs/data_source_provenance.csv`).

12. **The freeze mechanism itself** — `FREEZE_TAG = "v4_2026-08-01"` pinned on version *and*
    date, resolved by exact filename match with **no "newest wins" fallback**, stray non-freeze
    artifacts reported on every run, promotion a deliberate two-step act, and 11 unit tests
    enforcing it. A genuine reproducibility contribution and a good Methods paragraph.

13. **Reproducible deck/figure generation** — `etl/build_decks.py`, `build_deck_figures.py`,
    `build_rigor_figures.py`, `build_college_report.py`. Slides and figures are regenerated from
    the data rather than committed as binary blobs; `build_rigor_figures.py`'s docstring notes
    it exists specifically so figures cannot disagree with each other.

14. **`docs/MEETING_NOTES_2026-08-03_RESPONSES.md`** — worth a skim for client commitments that
    may need reflecting in the write-up.

### Known gaps to disclose rather than fix
- Client rigor factors **5 (extracurricular breadth)** and **6 (GPA / academic competitions)**
  have no component in any index version and cannot be sourced from public data — they would
  have to come from NU's own application records (`RIGOR_FORMULA_V5.md:§5`).
- The QD formula's within-school score SD ≈ 1.2 is an undocumented approximation; the College
  Board does not publish school-level score distributions.
- No ground-truth rigor labels exist anywhere in the project, so all §10-style validation is
  **convergent, not accuracy**.

---

## Appendix — how to reproduce these numbers

```bash
# DB (stale stage-1/2 snapshot only — see §0.1)
docker compose up -d db
docker exec capstone-db psql -U capstone -d capstone -c "\dt"

# Everything else runs off csv_exports/ with the repo venv (pandas only)
.venv/bin/python -c "import pandas as pd; d=pd.read_csv('csv_exports/modeling_dataset_v4_2026-08-01.csv',low_memory=False); print(len(d), d.sector.value_counts().to_dict())"

# Test suite (needs pytest + scikit-learn, not in .venv)
python -m pytest tests/ -q
```

The clustering recomputations in §6.2–6.5 need `scikit-learn` and `scipy`, which are **not**
in `.venv`. I used a throwaway venv outside the repo; nothing in the repo was modified. The
PCA/silhouette figures were validated by reconstructing the feature matrix with
`build_clustering.build_feature_matrix()` and confirming the result reproduces the stored PCA
scores to 4.4e-16 and the stored cluster labels at ARI = 1.0000.
