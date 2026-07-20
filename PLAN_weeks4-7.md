# Project Plan — Weeks 4–7

Scope note (updated): Bob's NU Admissions org export arrived and is merged as `csv_exports/schools_org_enriched.csv` (25,577 × 127, 55 `nu_*` columns). It supplies school-level **SAT averages** (`nu_avg_freshman_sat`, ~10,200 schools / 40%; private 50%), SAT participation, **AP exam averages and per-student AP counts** (`nu_avg_ap_score`, `nu_avg_num_ap_tests_taken/offered`, ~9,800 schools), and 4-yr college-going categories. This substantially satisfies Goals 6 and 8. Two caveats govern its use: (1) coverage is biased toward NU's recruiting universe — treat "no NU data" as informative, not missing-at-random; (2) measurement vintage is unstated in the export (flagged as an open question for Bob). The EDFacts SY 2022-23 achievement pull is **dropped** (ED Data Express school-level achievement is unavailable/broken); the SY 2020-21 participation columns remain as-is with COVID caveats.

## Current status (end of Week 3)

Done: master database + Dockerized ETL (Goal 1); NCES↔CEEB junction, exact-ID + fuzzy (Goal 2 — public 75%, private 61% CEEB coverage); grade 9–12 pipeline counts (Goal 5); AP counts via CRDC + IB flags via IBO (Goal 7); current addresses/websites/school type, SY 2023–25 (Goal 9); combined analysis table (25,577 schools × 71 cols) with graduation rate, CRDC, ACS/SAIPE county context.

Open: rigor classification model (Goal 3), per-student funding (Goal 4), SAT/ACT ranges where public (Goal 6), AP/IB per student (Goal 8), OPE↔CEEB crosswalk (Secondary 1), clustering (Secondary 2).

## Week 4 — Close feature gaps, freeze the modeling dataset

- **Per-student funding (Goal 4).** Census F-33 district finances (already loaded) ÷ district enrollment → join to public schools via LEAID. The 12-digit NCESSCH now in hand makes this possible (LEAID = first 7 digits), removing the crosswalk blocker noted in views.sql. Add IL school-level per-pupil spending from ISBE as a finer overlay. Private schools: no public source — document as structural gap.
- **AP/IB intensity per student (Goal 8).** Primary: `nu_avg_num_ap_tests_taken` (direct measure, ~9,800 schools). Fallback for schools without NU data: `crdc_ap_enrollment / grades 9–12 enrollment`. Add IB programme count for IB schools.
- **SAT (Goal 6).** Primary: `nu_avg_freshman_sat` + `nu_pct_seniors_taking_sat`. Validate against IL ISBE ACT (should correlate strongly); document the recruiting-universe selection bias. Ask Bob for the measurement vintage.
- **NU org data cleaning.** Parse categorical text columns (`nu_percent_going_to_4yr_college` etc.) to ordinals; drop the near-empty `nu_mean_sat` (11 values); add an `has_nu_data` indicator for use as a model feature/stratum.
- **Cleaning freeze.** Minimum-size threshold (grades 9–12 ≥ 30), sentinel/suppression symbols → NaN, winsorize ratios, gate IB flag on match tier. Output: versioned `modeling_dataset.csv` + data dictionary. **No new data after Friday.**

## Week 5 — Rigor classification model (Goal 3)

- Features: AP courses & AP enrollment per student, IB programmes, dual enrollment, counselor FTE, pupil/teacher ratio, graduation rate, school size, county education/income context.
- Method: unsupervised first — K-prototypes (mixed types) and Gower + hierarchical as a robustness check; compare k = 4–6; silhouette + interpretability.
- Map clusters → the five tiers (Below Average / Average / Demanding / Very Demanding / Most Demanding) by ordering clusters on AP/IB intensity and outcomes.
- Model public and private separately (feature sets differ structurally), then align tiers across sectors using the shared feature block.
- Midweek checkpoint with advisor/Bob on tier definitions — tier semantics are subjective; get sign-off on a sample (e.g., New Trier must land in Most Demanding) before finalizing.

## Week 6 — Validation + clustering + OPE↔CEEB

- **Validation.** Hold graduation rate (or any late-arriving outcome) out of the model; verify tier monotonicity. Face-validity audit on ~30 known schools across tiers. Sensitivity: re-run with/without county context to show tiers aren't just repackaged demographics.
- **Clustering deliverable (Secondary 2).** Reuse the Week-5 pipeline with the full feature set (location, academic, financial) for descriptive segments; profile each cluster.
- **OPE↔CEEB crosswalk (Secondary 1).** IPEDS HD file (has OPEID) × college CEEB code list; name+state matching with the existing crosswalk_matcher; ~6,000 colleges, reuse tier/review logic. Budget: 2 days.
- Load `school_tiers`, `school_clusters`, `ope_ceeb_crosswalk` into the database; wire into `run_all.py`.

## Week 7 — Integration and delivery

- Re-run full ETL end-to-end in Docker; regenerate `csv_exports/`; tag a release.
- Final report: methodology, tier distributions and profiles, funding analysis, limitations (time-period misalignment 2020–25, private-sector data gaps, SAT/ACT partial coverage, no public school-level AP exam scores).
- Slide deck + README refresh; handoff notes for whoever maintains the database.
- Buffer (~1.5 days) for advisor feedback loop on tiers.

## Risks

1. **Tier definitions are judgment calls** — mitigated by the Week-5 midweek sign-off; don't let this slip to Week 7.
2. **Private schools** lack funding, CRDC, and EDFacts data; their tiers rest on AP/IB, staffing, and size only. State this prominently in the report.
3. **F-33 join quality** — district-level spending assigned to every school in a district blurs within-district differences; the IL overlay quantifies how much this matters.
