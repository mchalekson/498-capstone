# Data dictionary — `schools_org_enriched`

Full field-by-field detail is in
[`data_dictionary_schools_org_enriched.csv`](data_dictionary_schools_org_enriched.csv)
(variable, data type, source dataset, grain, vintage, confidence, description,
notes). This doc is the short version — scope, match rate, and the open
questions worth sending to Bob/Sheng before trusting specific fields.

**Scope:** this covers `schools_org_enriched` only — the table produced by
combining Sheng's nationwide schools export
(`data/updated-sheng/schools_combined_enriched_ceeb.csv`) with Bob's NU
Admissions org export (`data/NU-Master/nu_master.xlsx`) on CEEB. It does not
yet cover the other ~30 tables in the pipeline (`public_schools_enriched`,
ISBE raw sheets, CRDC raw, etc.) — extend the same CSV format to those next
if useful.

## Match rate

25,577 schools total; **18,580 (73%) matched to an NU org record via CEEB.**
The other 27% either have no CEEB at all (~6,500 rows — mostly non-CEEB or
unmatched schools upstream) or a CEEB that isn't in Bob's list. This is an
exact-match join (both sides carry CEEB directly) — no fuzzy matching in this
specific combination, so the match rate is a ceiling on coverage, not a
matching-confidence question.

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
