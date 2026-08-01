# Predictive validation of the rigor construct — v1 (2026-07-24)

Code: `etl/build_predictive_validation.py`. Run against `modeling_dataset_v4_2026-07-24.csv`
(the predictor blocks are unchanged between v3 and v4 — neither v4 feature is a predictor here —
so every figure below is identical on both).

Outputs:
- `csv_exports/predictive_validation_v4_2026-07-24.csv` — test-set predictions
- `csv_exports/predictive_validation_metrics_v4_2026-07-24.csv` — R²/RMSE per spec × block × model
- `csv_exports/predictive_validation_importance_v4_2026-07-24.csv` — permutation importance

The CRDC-only specification was documented here before it existed in code; it is now
`OPPORTUNITY_CRDC` in the script and runs on every invocation. All numbers below were
reproduced from that run on 2026-07-26.

## What this is (and is not)

This is **not** a model that replaces the rigor index — it is the literature's validation step
for it. Adelman (1999, 2006) constructed a curriculum-intensity index and then regressed degree
completion on it; Geiser & Santelices and Bastedo apply the same predictive-validity test; the
Reardon/SEDA line adds the guardrail that any such validation must check socioeconomic
confounding. This run does exactly that at the school level: do the rigor index's
**opportunity-structure ingredients** predict the four-year graduation rate *beyond what SES
alone explains*?

Design safeguards:

1. **Opportunity features only as predictors** (AP offerings/engagement, CRDC coursework,
   test participation, `ib_flag_v2`). The index's exam-performance components are excluded —
   predicting an outcome from other outcomes would be circular.
2. **SES-incremental design**: SES-only baseline (school FRL rate, county child poverty,
   funding) → opportunity-only → SES + opportunity. The claim rests on the incremental R².
3. **Target caveats stated**: grad_rate_2021 is a COVID cohort, privacy-blurred (range
   midpoints), ceiling-compressed (median 91) — R² ceilings are structural, not model failure.
4. **Ecological level**: school-level regression, public schools only (EDFacts has no private
   schools). Findings are about schools, not students.

## Results

Main spec (all 8 opportunity features; complete case n=1,691 — NU-feature coverage binds):

| Model | Linear R² | GBM R² | GBM RMSE |
|---|---|---|---|
| SES only | 0.370 | 0.373 | 5.17 |
| Opportunity only | 0.212 | 0.228 | 5.74 |
| SES + Opportunity | 0.419 | 0.419 | 4.98 |
| **Incremental (opportunity over SES)** | **+0.049** | **+0.046** | |

CRDC-only spec (4 public-universe features; complete case n=6,158 — no NU selection bias):

| Model | Linear R² | GBM R² |
|---|---|---|
| SES only | 0.200 | 0.272 |
| Opportunity only | 0.104 | 0.128 |
| SES + Opportunity | 0.235 | 0.325 |
| **Incremental** | **+0.035** | **+0.053** |

Robustness: GBM with native NaN handling on all 17,420 public schools with a target: R² = 0.515.

Permutation importance (main spec, test set): `frl_rate` dominates (0.53), followed by
`ap_participation` (0.066) and `testtaker_rate` (0.059) — the two strongest opportunity signals.

## Interpretation for the paper

- **The opportunity structure carries real incremental signal**: +0.04–0.05 R² beyond SES,
  stable across two very different specifications and both model families. In Adelman's terms,
  the ingredients of our rigor construct predict a real outcome — the index is measuring
  something, not merely re-describing demographics.
- **But SES (school-level FRL) remains the dominant predictor of graduation.** This is the
  honest companion to the paper's headline finding: the *outcome* (graduation) is heavily
  SES-driven, while our *index* correlates with poverty at only −0.07 — precisely the argument
  for measuring opportunity structure rather than outcomes when comparing schools.
- Linear ≈ GBM on the same rows (0.419 vs 0.419): relationships are mostly linear; the GBM's
  advantage appears only when exploiting the larger missing-data universe.

## Caveats

- Complete-case populations are non-random (NU-feature spec skews to the recruiting universe;
  CRDC spec to schools answering CRDC). Both specs shown for that reason.
- `child_poverty_saipe` flips sign in the combined linear model (+0.51 standardized) — a
  classic suppression effect from collinearity with FRL; do not interpret it causally.
- `ib_flag_v2` and `dual_enrollment_rate` contribute little here — rare/binary signals have
  limited leverage on a ceiling-compressed target; this does not contradict their role in the
  index (measuring offerings, not predicting graduation).
- COVID-cohort target: rerun against a post-COVID ACGR vintage when EDFacts publishes one.
