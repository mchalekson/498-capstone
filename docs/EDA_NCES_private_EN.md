# Initial EDA — NCES_private_merged (PSS Private School Universe Survey)

## Dataset Overview

- **1,354 private high schools × 72 columns** (71 PSS variables + `source_file`)
- 49 source files = one per state (each file covers exactly one state). **AK and MS are missing**
- All high schools: `LoGrade=14` (grade 9), `HiGrade=17` (grade 12), `PSS_LEVEL=2` (1 exception)
- `PSS_SCHOOL_ID` is always 8 characters (letter + 7 digits) with no duplicates → reliable primary key
- 89 duplicate school names (same name in different states) → name alone cannot serve as a join key

## State Distribution (Top 5)

CA 166 · NY 144 · NJ 85 · PA 82 · IL 77

## Numeric Variables

| Variable | n | Median | Mean | Range |
|---|---|---|---|---|
| Total enrollment (ENROLL_TK12) | 1,328 | 222 | 334 | 2 – 6,353 |
| Enrollment per grade 9–12 | ~1,320 | 54–58 | ~80–86 | 1 – 1,800 |
| FTE teachers | 1,261 | 21.9 | 28.6 | 0.5 – 305 |
| Student/teacher ratio (STDTCH_RT) | 1,242 | 10.6 | 11.4 | 0.9 – **409.9** ⚠️ outlier |
| School days per year | 1,238 | 180 | 179.6 | 110 – 260 |
| Hours per school day | 1,264 | 7.0 | 7.2 | 1.4 – 11 |
| White students (count, not %) | 1,029 | 68.5 | 61.5 | 0 – 2,360 |
| Black / Hispanic / Asian (count, not %) | ~1,040 | 4.1 / 7.0 / 1.8 | 11.7 / 15.5 / 4.8 | 0 – 1,401 / 2,049 / 647 |

**Correction:** the `PSS_RACE_*` fields are raw student headcounts, not
percentages — verified against the data (they sum exactly to
`PSS_ENROLL_TK12` for every row) while wiring up the ELSI backfill below.
The "0–100" range and "%" labeling in earlier versions of this doc were
wrong; medians/means above are counts, not percentages.

Right-skewed: 10% of schools have ≤28 students; 90th percentile 776; 99th percentile 1,575.

## Categorical Variables

- **Religious affiliation (PSS_RELIG)**: 1=Catholic 640 (47%), 2=other religious 441 (33%), 3=nonsectarian 273 (20%)
- **Coed status (PSS_COED)**: coed 927 (68%), all-girls 224, all-boys 173, missing 30
- **School type (PSS_TYPE)**: regular 1,113 (82%); Montessori/special-ed/vocational etc. ~190; missing 48
- **Locale (PSS_LOCALE)**: city (11–13) 647 · suburb (21–22) 427 · town/rural (31–43) 254
- **Library**: yes 896, no 405, missing 53

(Code meanings should be verified against the PSS codebook.)

## Missingness

- **Structurally empty (safe to drop)**: `PSS_ENROLL_PK` through `PSS_ENROLL_8`, `PSS_ENROLL_K` (10 columns — high schools only); `PSS_ASSOC_13–15`
- **Near-empty (>90%)**: `PSS_ASSOC_4–12`, `PSS_ENROLL_UG`; `PSS_ASSOC_2` 76% missing, `ASSOC_3` 92%
- **Sentinel `-1` = missing**: PSS_TYPE (48), PSS_COED (30), PSS_ORIENT (23) — replace with NaN during cleaning
- Race percentage columns ~23% missing; student/teacher ratio 8% missing

## Merge Strategy with Other Datasets

| Dataset | Granularity | Available key | Merge approach |
|---|---|---|---|
| **NCES ELSI private** (`nces-private-schools.csv`) | School | NCES School ID (same PSS ID system) | **Direct inner join.** Tested: 977/1,354 (72%) match; ELSI is 2019-20, so non-matches are mostly new/closed schools |
| **NCES ELSI public** (`nces-public-schools.csv`) | School | 7-digit NCES public ID | Different ID system — no direct join; use as public-school comparison group aligned by state/county FIPS |
| **IB** (`ib_us.csv`) | School | No NCES ID, only IBO ID | **Fuzzy matching**: normalize school names (uppercase, strip THE/SCHOOL/ACADEMY, etc.) + state/city as tiebreaker; suggest rapidfuzz with manual review of low-confidence matches |
| **ISBE report card** | School (IL only) | RCDTS; no NCES ID | Mostly covers public schools; for private schools use the same name+city fuzzy match (only 77 IL private schools) |
| **CPS Opportunity Index** | School (Chicago only) | CPS School ID | First CPS↔ISBE (CPS ID is embedded in RCDTS), then name-match to NCES |
| **CollegeBoard AP** | National/state aggregates | State | Not school-level; attach state AP participation rates via `PSS_STABB` as context variables |
| **NAEP** | National/state aggregates | State | Same — join by state |
| **Census school finance / SAIPE poverty** | School district | LEAID / district FIPS | Private schools have no district; aggregate to **county FIPS** (`PSS_FIPS` + `PSS_COUNTY_FIPS`) or ZIP, then join as community economic context |

**Recommended backbone**: use `PSS_SCHOOL_ID` as the private-school primary key → join ELSI private for extra variables → attach IB flag via fuzzy matching → left-join state-level (AP/NAEP) and county-level (Census/SAIPE) context variables via `PSS_STABB` and county FIPS respectively.

**Cleaning to-dos**: ~~drop 13 fully empty columns~~ done (`clean_nces.py`) · ~~`-1` → NaN~~ done · ~~cast numeric columns~~ done · ~~investigate student/teacher ratios >50~~ done — only 10/1,242 non-null rows exceed 50, and they're legitimate: online/virtual programs (Career Online HS at 409.9, BYU Online HS at 79.4) plus a few small alternative schools with skeletal FTE counts, not data errors. Worth flagging to any rigor model as a different school type, not filtering out. · ~~decide whether to backfill race counts from ELSI~~ done — partial backfill implemented in `combine_schools.py`: ELSI only carries hispanic and two-or-more-races counts (not the full 7-category PSS breakdown), so those 2 of 7 race columns get backfilled (count-for-count, not percentage) where PSS's own value is null; the rest would need a re-pulled ELSI export with the other race count columns selected.
