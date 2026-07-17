# Data dictionary — `schools_org_enriched` / `schools_org_all`

## Update 2026-07-17 — CEEB fan-out fixed, match numbers below corrected

~1,415 CEEB codes on the schools side previously covered more than one school
row — not a real 1-CEEB-many-schools relationship, but a fuzzy-matching
artifact in the upstream CEEB crosswalk: e.g. CEEB `050222` ("Vista High
Continuation") matched 55 distinct, unrelated California "___ Continuation
High" schools purely on the shared generic phrase "Continuation High" (same
pattern for "___ Area Learning Center" schools in Minnesota, etc.) — some
pairs were even both marked `auto_accept` for the same CEEB, which can't
happen for a real CEEB (it identifies one physical school). Every colliding
school independently inherited the same NU org record downstream, which is
where the 2,072 "duplicate org rows" in `EDA_features_joined.md` §3b came
from. Fixed in `combine_schools.py` via `resolve_ceeb_ties()`: keeps one
canonical school per CEEB (best match tier, then exact name match, then
lowest school_id) and nulls the CEEB on the rest. **The match numbers below
are the corrected, post-fix ones** — they're lower than before (fewer false
matches), not worse.

---

Full field-by-field detail is in
[`data_dictionary_schools_org_enriched.csv`](data_dictionary_schools_org_enriched.csv)
(variable, data type, source dataset, grain, vintage, confidence, description,
notes) — the column set is identical between the two tables below, so this
one CSV covers both. This doc is the short version — scope, match rate, and
the open questions worth sending to Bob/Sheng before trusting specific fields.

**Scope:** this covers the two `schools_org_*` tables only — both combine
Sheng's nationwide schools export
(`data/updated-sheng/schools_combined_enriched_ceeb.csv`) with Bob's NU
Admissions org export (`data/NU-Master/nu_master.xlsx`) on CEEB, differing
only in join type (see below). It does not yet cover the other ~30 tables in
the pipeline (`public_schools_enriched`, ISBE raw sheets, CRDC raw, etc.) —
extend the same CSV format to those next if useful.

## Two tables, two join types

- **`schools_org_enriched`** (`etl/combine_schools.py:build_schools_org_enriched`)
  — **left join**, anchored on Sheng's 25,577 schools. One row per school;
  NU columns are null where no CEEB match exists. Bob's orgs that never
  matched a school row (see below) don't appear here at all.
- **`schools_org_all`** (`etl/combine_schools.py:build_schools_org_all`) —
  **full outer join**, everything from both files. 53,966 rows total:
  16,508 matched both sides (identical to the match count below), 9,069
  school-only rows (Sheng schools with no CEEB match in Bob's file, NU
  columns null), and 28,389 NU-org-only rows (Bob orgs with no matching
  school row, school-side columns null). `nu_master_org_data.ceeb` is
  unique, so it can't fan out rows on its own — but the schools side needed
  a dedup step first (`resolve_ceeb_ties()`, see update above) before this
  held true for the schools side too.

Use `schools_org_enriched` for school-level analysis (one row per school is
usually what you want); use `schools_org_all` if you need to see or count
every org in Bob's file, including the ones with no matching school record.

## Match rate

25,577 schools total; **16,508 (64.5%) matched to an NU org record via CEEB**
(post CEEB-dedup fix — see update above; was 18,580/73% before, but ~2,072 of
those were false-positive fuzzy matches on the crosswalk, not real matches).
The remaining schools either have no CEEB at all, a CEEB that isn't in Bob's
list, or lost their CEEB in the dedup because a different school was the
better-confidence match for that code. This is an exact-match join on CEEB
itself (no fuzzy matching in this specific combination) — the fuzzy matching
that caused the original inflation happened one step upstream, in the CEEB
crosswalk that assigned `ceeb` to the schools table in the first place.

Symmetrically, of Bob's 44,897 CEEB-bearing orgs, **16,508 (36.8%) matched a
school row**; the rest have a CEEB that isn't in Sheng's schools export (or
lost its school-side match in the dedup). A low match rate on this side is
expected, not a data-quality problem: Bob's org export is broader than "high
schools with a CEEB Sheng's source recognizes" — it likely includes colleges
and other org types out of scope for this join.

## Vintage — the real gap

Two sources have **confirmed, specific vintages**, traced back to the raw
files that ship alongside Sheng's CSV:
- `grad_rate_2021` / `grad_cohort_n` / `grad_rate_is_range` — EDFacts
  **SY2020-21** Four-Year Adjusted Cohort Graduation Rate (FS150/151,
  DG695/696).
- `assess_part_math_2021` / `assess_part_rla_2021` — EDFacts **SY2020-21**
  assessment participation (FS185/FS188).
- `crdc_*` (8 fields: AP courses/enrollment, dual enrollment, SAT/ACT
  takers, counselors, teacher certification) — CRDC **School Year 2021-22**.

Everything else — the NCES/PSS backbone fields, ISBE fields, county ACS
fields, the CEEB crosswalk, and **all 56 `nu_*` fields from Bob's export** —
has **no confirmed vintage in this repo**. Bob's file is only dated by its
own export filename (`Capstone Org Data 20260624-093658.xlsx` → pulled
2026-06-24); nothing inside the file states when each underlying stat (mean
SAT, AP participation, etc.) was actually measured. This is exactly the
"old section vs. new section" problem raised in the 2026-07-14 meeting —
until Sheng/Bob confirm per-source vintage, don't assume any two fields in
this table are from the same year.

## Known overlaps — same concept, two sources, no way to reconcile yet

- **AP data exists twice**: `crdc_ap_courses`/`crdc_ap_enrollment` (CRDC,
  confirmed SY2021-22) vs. `nu_number_of_ap_classes_offered`/
  `nu_avg_num_ap_tests_offered`/`nu_avg_ap_score` (Bob's export, undated).
  These can disagree for the same school and there's currently no rule for
  which to prefer.
- **Poverty rate exists twice**: `county_pct_poverty` (inferred ACS,
  undated) vs. `county_pct_child_poverty_saipe` (Census SAIPE, undated,
  child-only, model-based rather than direct-survey — a methodologically
  different number, not just a different vintage of the same one).

## Data-quality notes worth flagging to Bob

- **`nu_custom_id`**: populated for only 34,348/44,899 org rows and **not
  unique** — some values repeat across different orgs. Likely an internal
  NU system ID of some kind; not usable as a key until Bob confirms what it
  is. (He already flagged he'd check on this.)
- **`nu_ccid`**: numeric, unclear meaning — same "ask Bob" status.
- **Several `nu_*` percentage/count fields are categorical range buckets,
  not raw numbers** — e.g. `nu_percent_going_to_4yr_college` holds values
  like `"90% or more"` / `"80-89%"`, and `nu_number_of_ap_classes_offered`
  holds `"11-15"` / `"greater than 20"`. These came through as `text`
  columns, not numeric — verified by sampling actual values, not assumed
  from the column name. Any modeling use needs an explicit bucket-midpoint
  or ordinal-encoding decision, not a numeric cast.
- **CRDC sentinel codes**: CRDC raw files use `-9`/`-6` etc. for
  suppressed/not-applicable. Confirm these were converted to NULL before
  Sheng's export was built — a `crdc_ap_courses` of `-9` would silently
  look like real data if not cleaned.

## How this was built

Source attribution came from three places, in order of trust: (1) direct
inspection of the raw files sitting next to Sheng's CSV in
`data/updated-sheng/` — this is how EDFacts/CRDC vintages got confirmed;
(2) this repo's own EDA docs (`docs/EDA.md`,
`docs/EDA_NCES_private_EN.md`) for sources this repo's own pipeline shares
column-naming conventions with, used as a naming-convention reference only,
**not** as proof those exact columns in Sheng's file came from the same
pull; (3) inference from column name alone where neither of the above gave
direct evidence — those rows are marked `vintage_confidence: inferred` and
say explicitly what needs asking. Nothing in the CSV states a source or
date that wasn't either verified against a file in this repo or clearly
flagged as unverified.
