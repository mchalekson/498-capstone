# Responses to Week-of-8/3 meeting notes

Prepared 2026-08-10. All findings are against the current data: `data/NU-Master/nu_master.xlsx`
(extended-v4 upload dated 2026-07-31, 44,902 rows) and the Aug-1 pipeline outputs
(`modeling_dataset_v4_2026-08-01.csv` and siblings).

Supporting artifacts generated with this memo:
- `csv_exports/review_correctional_facilities_modeling_v4.csv` — the 48 correctional facilities currently in the model.
- `csv_exports/review_generic_ceeb_codes.csv` — the 31 shared "placeholder" CEEB codes behind items 3 & 4.

---

## 1. Latest file upload (17,811 orgs / 59k fields updated with last Landscape)

Confirmed we are building on this upload. `nu_master.xlsx` is the extended-v4 file (2026-07-31,
44,902 rows), and the entire Aug-1 modeling pipeline runs off it. The 17,811 / 59k change counts
are your side's diff against your prior Landscape pull; we can't reproduce them without both of
your versions, but nothing downstream on our end is stale.

## 2. Field-list differences (data dictionary vs. modeling set vs. missing-schools list)

The modeling dataset and its dictionary are aligned; the **missing-schools list uses a different
column vocabulary**, and there is **one real regression** in the Aug-1 rebuild.

| Comparison | Result |
|---|---|
| Modeling v4 columns documented in the dictionary | 66 / 66 |
| Dictionary entries with no column in modeling v4 | 1 — `ib_flag_v2_source` |
| Missing-list columns shared with modeling v4 | 7 of 21 |
| Missing-list columns undocumented in the dictionary | 14 |

- **`ib_flag_v2_source` is a regression, not a doc typo.** It was a column in v2, v3, and
  `v4_2026-07-24`, then **dropped in `v4_2026-08-01`**. The dictionary still documents it.
  Decision needed: restore the column in the modeling build, or retire it from the dictionary.
- **Missing-list schema mismatch.** The missing-schools list was built with its own names
  (`total_enrollment` vs. `enrollment_9_12`, `county_median_hh_income` vs. `median_family_income_*`,
  plus list-only fields `school_id`, `nces_id_12`, `rigor_tier_v4`, `audit_note`). If we want a
  single field vocabulary, that list should be renamed to the modeling dictionary's terms.

## 3 & 4. Duplicate CEEBs (`010554`, `030000`, `050222`) and `030000` in both lists

These are **not errors, and not a leading-zero problem** (item 4's "missing leading 0's?" does not
hold — the raw value is `030000` with the zero intact; no `30000` variant exists anywhere). They are
**generic placeholder CEEB codes** that College Board assigns to whole *categories* of schools that
don't receive their own code:

| CEEB | Category it represents | # distinct schools sharing it (missing list) |
|---|---|---|
| `050222` | California **continuation** high schools | 20 |
| `010554` | Alabama **career/technical** centers | 7 |
| `030000` | Arizona **alternative / JTED** programs | 5 |

- **Item 3 (duplicates):** the code repeats because it legitimately covers many schools — it is not
  school-unique. There are **31 such generic codes** in the missing list, covering **134 school rows**
  (see `review_generic_ceeb_codes.csv`): continuation schools, career/technical centers, district
  alternative-education programs, and JTED/vocational programs.
- **Item 4 (`030000` in both lists):** it appears in the org list (Ajo High School) *and* the missing
  list (5 AZ schools) because it is a shared bucket code, not a dropped zero.

**Implication:** schools carrying a generic CEEB cannot be matched to the NU list by CEEB — the code
does not identify a school. They should be matched by name / NCES ID or set aside as a known
"generic-CEEB" bucket, and excluded from CEEB-based dedup.

## 5. Correctional facilities

They are present and **currently not excluded**. A tightened name filter (correctional / juvenile /
detention / penitentiary / jail / justice center; religious "Reformed" schools deliberately excluded)
finds **48 correctional facilities in the modeling dataset** — e.g. United States Penitentiary,
Monroe Correctional Facility, several juvenile justice / detention centers. Full list in
`review_correctional_facilities_modeling_v4.csv`.

**Recommendation:** flag and exclude these from the modeling universe and the NU-list match, since NU
does not recruit from correctional facilities. Ready to wire into `build_modeling_dataset.py` as a
name/type filter on your sign-off (requires a pipeline re-run to propagate).

---

## High-school clustering — what the clusters comprise

HS clustering already exists (`etl/build_clustering.py`) and was run on the latest Aug-1 v4 data.
Method: z-score → PCA (≥90% variance) → KMeans, on rigor components + funding + poverty + region,
deliberately excluding the rigor score itself to avoid circularity. The latest run produced **8
clusters**.

**Coverage caveat:** clustering is complete-case (no imputation), so it covers **5,837 of 34,392
high schools (~17%)** — those with every feature present. Worth stating in any client-facing use.

| # | Size | Character | Demanding+ | Top region | Signature (z-scores) |
|---|---|---|---|---|---|
| 3 | 438 | High funding, high rigor | 74% | Northeast | funding **+2.6**, low poverty −0.7 |
| 0 | 724 | High rigor, high test-takers | 74% | South | rigor +0.9, test-taker +0.9, funding below avg |
| 6 | 25 | High rigor, low AP density | 92% | West | tiny outlier; rigor +1.6, almost no AP |
| 2 | 1,029 | High funding, low need | 44% | Northeast | funding +0.8, socio-need −0.5 |
| 4 | 741 | High AP take-rate + test-takers | 49% | Midwest | AP take +0.45, dual-enroll +0.33 |
| 7 | 997 | Low test-takers, low poverty | 22% | Midwest | quiet middle, near-average |
| 1 | 1,044 | Low funding, low rigor | 14% | South | rigor −0.6, funding −0.6 |
| 5 | 839 | High poverty, high need | 15% | South | poverty **+1.7**, socio-need +0.9 |

**Read:** clusters 3 and 0 are the high-opportunity schools (Northeast funding-driven; Southern
participation-driven despite lower funding); clusters 5 and 1 are the under-resourced end
(Southern high-poverty; low-funding). Funding and poverty are the strongest separators, region secondary.
Detail: `csv_exports/cluster_profiles_v4_2026-08-01.csv`; membership: `csv_exports/clustering_v4_2026-08-01.csv`.

---

## Open decisions for the team

1. `ib_flag_v2_source` — restore the dropped column or retire it from the dictionary.
2. Correctional facilities — approve exclusion filter (48 schools).
3. Generic-CEEB schools — approve treating as a non-CEEB-matchable bucket (31 codes / 134 rows).
4. Clustering — keep the 8-cluster / 17%-coverage result, or re-run with fewer clusters and/or light
   imputation for a cleaner, higher-coverage client story.
