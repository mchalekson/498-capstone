# EDA — schools_combined_enriched_ceeb.csv (English)

Dataset: 25,577 U.S. high schools × 71 columns (24,223 public / 1,354 private, flagged by `sector`), covering 50 states + DC (public includes some territories; private is missing AK and MS).

## Data Sources and Time Periods

| Variable group | Source | Time period | Granularity | Coverage |
|---|---|---|---|---|
| School basics, grade counts, race, staffing (public) | NCES CCD (ELSI) | **SY 2024-25** | School | All public |
| School basics, religion, coed (private) | NCES PSS | **SY 2023-24** | School | All private |
| Graduation rate `grad_rate_2021` | EDFacts ACGR | **SY 2020-21** ⚠️ COVID year | School | 74% of public |
| Assessment participation `assess_part_*_2021` | EDFacts FS185/FS188 | **SY 2020-21** ⚠️ COVID year; participation, not proficiency | School | 77% of public |
| AP / dual enrollment / SAT-ACT / counselors / certification `crdc_*` | CRDC | **SY 2021-22** | School | Public only (AP 51%, counselors 84%) |
| ISBE report card (ACT/IAR/spending) | ISBE | **SY 2024-25 report card (2025 release)** | School | IL only (~2.6%) |
| IB authorization flag | Scraped from IBO | **Current as of 2025-26** | School | Fuzzy-matched; see caveats |
| CEEB codes | UC Boulder crosswalk | Compiled (~2024) | School | 75% public / 61% private |
| County income/education/poverty `county_*` (ACS) | Census ACS 5-year | **2020-2024** (released Dec 2025) | County | 94% |
| County child poverty `county_pct_child_poverty_saipe` | Census SAIPE | **2024** | County | 94% |
| SAT avg / AP avg / AP per student `nu_*` (see below) | Bob's NU Admissions org export | **Exported 2026-06; per-metric vintage unstated** ⚠️ pending Bob | School | ~40% |

Time alignment: the school roster backbone is 2023-25 while outcome variables fall in 2020-22. Acceptable for cross-sectional clustering, but must be documented; graduation and participation rates were materially affected by COVID and should be interpreted with care.

## Key Distributions (by sector)

| Variable | Public median | Private median | Notes |
|---|---|---|---|
| Total enrollment | 366 | 223 | Right-skewed; public P10=9 (micro/alternative schools), P90=1,735 |
| Pupil/teacher ratio | 14.2 | 10.6 | Smaller classes in private |
| Graduation rate (2021) | 90.0 | — | Public only; P10=62 |
| AP courses offered | 9 | — | CRDC, public only |
| Counselor FTE | 2.0 | — | P10=0: ~10% of high schools have no dedicated counselor |
| County median HH income | $74,467 | $84,488 | Private schools sit in wealthier counties |
| County % bachelor's+ | 31.1 | 36.8 | Same pattern |
| County % child poverty | 14.9 | 13.5 | |

Private schools are located in systematically wealthier, more educated counties — the community-context dimension will naturally separate sectors in clustering; this is expected.

## CEEB Match Quality

| | With CEEB | Exact ID match | auto_accept | Needs review |
|---|---|---|---|---|
| Public | 18,263 (75%) | 15,079 | 16,187 | 2,076 |
| Private | 821 (61%) | 544 | 613 | 208 |

## Missingness Structure

Missingness is structural, not random, in three blocks: ISBE columns are IL-only (97% empty); private-specific columns (religion/coed/PSS ID) exist only for private rows (95% empty); CRDC/EDFacts columns are public-only (AP columns 52% empty — CRDC only collects course counts from schools that offer AP). For modeling, treat the data as public block / private block / shared block rather than dropping rows or mean-imputing globally.

## Correlations with Graduation Rate (public)

Assessment participation +0.35, FRL share **-0.34**, enrollment +0.28, SAT/ACT takers +0.26, AP courses +0.23; **county-level income/education are essentially uncorrelated with graduation (±0.05)** — a school's internal composition (share of low-income students) matters far more than the average wealth of its county. This supports weighting school-level features over county context in clustering.

## Addendum: NU Org Data (schools_org_enriched.csv)

An extended version of the combined table, `csv_exports/schools_org_enriched.csv` (25,577 × 127), appends 55 `nu_*` columns from the NU Admissions org export (Naviance/College Board-style). Key metrics: `nu_avg_freshman_sat` (school SAT average, 10,171 schools / 40%, median 1140), `nu_pct_seniors_taking_sat` (9,432, median 58%), `nu_avg_ap_score` (9,841, median 2.7), and `nu_avg_num_ap_tests_taken/_offered` (AP tests per student — directly satisfies Goal 8). Spot check: New Trier shows SAT 1270 / AP 3.87 / 90%+ four-year college — face-valid; SAT correlates 0.61 with AP average.

Usage constraints: coverage is biased toward NU's recruiting universe (missingness is informative, not random — "no NU data" is itself a signal); text-categorical columns like `nu_percent_going_to_4yr_college` need ordinal encoding; `nu_mean_sat` (11 values) is a dead column; per-metric measurement years are unstated.

## Caveats

1. `ib_school_id` is non-null for every private row — the combine step's fuzzy matcher assigned the nearest candidate to every school. **Always gate on `ib_match_tier`; never treat non-null as "is an IB school."**
2. Public data includes micro/alternative/virtual schools (P10 enrollment = 9). Apply a minimum-size threshold before clustering (e.g., grades 9-12 enrollment ≥ 30) or bin them separately.
3. Pupil/teacher ratios have outliers >50 (data errors or special settings); winsorize.
4. The `charter` column contains 979 "†" (NCES suppression symbol) that must be converted to NaN.
5. EDFacts values are exam *participation* rates, not proficiency, and from the COVID year; recommend adding SY 2022-23 Achievement files (FS175/FS178) later.
