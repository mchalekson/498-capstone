# OPEID ↔ CEEB Merge Report

**College-side identifier junction and College Scorecard enrichment**
Date: 2026-08-02 · Outputs: `csv_exports/ope_ceeb_scorecard_merged_clean_2026-08-02.csv` (deliverable) · `csv_exports/ope_ceeb_scorecard_enriched_2026-08-02.csv` (full audit trail with matching columns)

## 1. Objective and inputs

The NU org export identifies colleges by **CEEB code** (College Board's institution code); every federal dataset identifies them by **OPEID** (Office of Postsecondary Education ID) or **UNITID** (IPEDS survey key). No official public crosswalk between CEEB and OPEID exists, so we built one, then used it to attach College Scorecard metrics.

| Input | Key | n |
|---|---|---|
| NU org export, `Category = College` (U.S.) | CEEB | 4,004 |
| IPEDS HD2023 directory | OPEID + UNITID | 6,126 |
| College Scorecard `MERGED2023_24_PP.csv` (latest populated year) | OPEID | 6,430 |

## 2. The ID systems and their special handling

### CEEB (6 digits)

- Zero-padded fixed-width string; leading zeros are significant (`002019`) and must never be read as integers.
- The CEEB entity is the *score-recipient*, which can be **finer than an institution**: Northwestern University and its School of Professional Studies carry different CEEB codes but are one federal institution.

### OPEID (8 digits) — the key structural regularity

- Structure: **6-digit institution stem + 2-digit branch suffix**. Suffix `00` denotes the institution-level (main campus) record; `01`, `02`, … denote branch campuses.
- In the raw Scorecard files OPEID arrives as a **float-formatted string** (`"100200.0"`): a naive join matches 0%. Handling: strip the `.0`, trim, left-pad to 8 digits (`zfill(8)`). After normalization, linkage jumps to 98.6%.
- The IPEDS HD2023 CSV ships with a **UTF-8 BOM** on its first column (`ï»¿UNITID`), which silently breaks column selection unless decoded as `utf-8-sig`.

### The many-to-many geometry between the two systems

Neither system is a refinement of the other — the mapping direction differs by case:

- **Many CEEB → one OPEID** (CEEB finer): sub-schools of one institution (Columbia's schools, NU SPS) each hold a CEEB but share the institution's OPEID. Hence 2,794 matched CEEB rows resolve to **2,630 distinct OPEIDs**.
- **One OPEID stem → many campuses** (OPEID finer): multi-campus systems (Troy University's sites, including out-of-state ones; Tarrant/Cuyahoga county college campuses) appear once per campus federally but may hold a single CEEB.

Consequently the merge is defined at the **institution level**: every CEEB row maps to an institution-level OPEID, which is the correct grain for Scorecard (Scorecard reports at the OPEID-institution level).

## 3. Matching method

Reuses the high-school matching funnel, college-tuned; deterministic rules first, LLM adjudication of the residue, geography as a first-class veto.

1. **Name normalization for CEEB/ATP abbreviation style** (~30 expansion rules): `U` → University, `Colg` → College, `CC` → Community College, `Nrsg` → Nursing, `Theol Sem` → Theological Seminary, etc. One rule is context-sensitive: `St` → **State** before Univ/College, otherwise **Saint** — both readings are attempted.
2. **Tiered acceptance, blocked by state**: exact normalized token match → token-subset with same city or geo < 15 km (catches branch-campus naming) → fuzzy ladders backed by geography (score ≥ 90 with same city or < 10 km; ≥ 65 within 3 km; ≥ 55 within 1 km).
3. **Geographic verification**: both sides carry coordinates (haversine distance), so weak name evidence is only accepted when campuses are physically co-located.
4. **Case-by-case adjudication** of the 209-row residue: 105 accepted (dominated by *College → University* renames, system branch campuses mapped to the institution OPEID, and CEEB-abbreviation misses), 103 rejected as not in IPEDS 2023, 1 garbled record left in review.

### Scorecard join rule

Matched OPEIDs join to `MERGED2023_24` by full 8-digit OPEID (2,754 rows). The 15 misses whose branch suffix differs join by the **6-digit stem**, choosing the main-campus Scorecard row (suffix `00` preferred, else largest undergraduate enrollment). 2024-25 and 2025-26 Scorecard files exist but are empty shells; 2023-24 is the latest populated vintage.

## 4. Coverage

| Stage | n | Share of 4,004 |
|---|---|---|
| CEEB → OPEID matched (rules + adjudication) | 2,794 | 69.8% |
| → linked to Scorecard 2023-24 | **2,769** | **69.2%** |
| — via exact 8-digit OPEID | 2,754 | |
| — via 6-digit stem (main campus) | 15 | |
| Not linkable | 1,235 | 30.8% |

Among the 2,769 linked institutions, metric coverage: tuition 95.8%, Pell share 99.2%, 6-year completion 65.8%, admission rate 54.4% (open-admission institutions report none), SAT average 36.7%. Golden check: Northwestern University → admission rate 0.0715, SAT 1526, completion 0.959 — and its School of Professional Studies row correctly inherits the same institution-level values.

**Every college that still operates is effectively covered** — the unmatched share is almost entirely institutions that no longer exist under their listed identity.

## 5. Why 1,235 rows do not match

| Reason | n |
|---|---|
| Closed or renamed independent institutions (no live OPEID) | 875 |
| Closed for-profit chains (ITT 59, Art Institutes 11, Heald/Brown Mackie/other 59) | 129 |
| Closed trade / business schools | 84 |
| Hospital nursing schools (closed or never Title-IV) | 79 |
| Religious institutions (often outside Title-IV) | 42 |
| Has OPEID but closed after 2023 (Bay State College, Alderson-Broaddus, …) | 25 |
| Cosmetology school | 1 |

Sampling the 875 "closed or renamed" bucket shows recurring patterns: pre-rename identities (*Fairmont State College*, *Concord College* — both now Universities), absorptions (*Westark Community College* → UA Fort Smith), campus-level entries of merged systems (*Black Hawk College: East Campus*), heavily abbreviated defunct trade schools, and occasional non-college records in the org data (*Indian Prairie School Dist 204*). The unmatched tail is therefore a **historical artifact of the org list**, not a matching failure — the same finding as on the high-school side. If desired, the renamed subset can be recovered by re-matching against a historical IPEDS/Scorecard year (e.g., 2015).

## 6. Deliverable schema

`ope_ceeb_scorecard_merged_clean_2026-08-02.csv` — 4,004 rows × 20 columns; all matching-process columns (candidate names, tiers, fuzzy scores, geo distances, link flags) removed, keeping only fields native to the two sources:

- **NU org export side**: `ceeb`, `org_name`, `org_city`, `state`
- **Federal side (IPEDS / Scorecard 2023-24)**: `unitid`, `opeid`, `sc_instnm`, `sc_control`, `sc_preddeg`, `sc_ugds`, `sc_adm_rate`, `sc_sat_avg`, `sc_act_mid`, `sc_completion_150_4yr`, `sc_retention_ft4`, `sc_tuition_in`, `sc_tuition_out`, `sc_netprice_pub`, `sc_netprice_priv`, `sc_pct_pell`

Median-earnings and median-debt fields are empty in all recent Scorecard merged files (they ship only in older vintages and the Most-Recent-Cohorts extract) and were dropped. The full audit version, including match tier, fuzzy score, geographic distance, and unmatch reason per row, is retained separately.
