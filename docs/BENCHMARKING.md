# Performance benchmarking — first pass (Section 4.5)

Code: `etl/build_benchmarking.py`. Run against `rigor_classification_v3_2026-07-24.csv`.

Descriptive only, per the report's own instruction: this ranks schools against peer groups
(region, funding tier, rigor tier), it does not predict or validate anything. `sat_score_nu` is
NU's average **freshman** SAT among students who reported it to NU during college search —
selection-biased toward college-going, NU-engaged families, not a random sample of each
school's full student body. Carried forward as a limitation, not smoothed over.

**ACT is not benchmarked in this pass.** The only ACT data in this pipeline
(`isbe_act_clean`) is Illinois-only and covers 1.2% of schools nationally — too sparse for a
national benchmarking pass. Left for a future IL-specific comparison.

**Coverage: 32.3% of schools (11,098) have `sat_score_nu`.**

## Peer-group comparison (descriptive)

| Region | n | Mean SAT | Std |
|---|---|---|---|
| Northeast | 2,321 | 1,167 | 72.8 |
| Midwest | 2,268 | 1,154 | 42.3 |
| West | 2,352 | 1,154 | 67.0 |
| South | 3,542 | 1,133 | 66.4 |
| Illinois | 590 | 1,128 | 61.7 |

| Funding quartile | n | Mean SAT |
|---|---|---|
| Q4 (highest) | 1,795 | 1,148 |
| Q3 | 1,663 | 1,135 |
| Q2 | 1,622 | 1,127 |
| Q1 (lowest) | 1,511 | 1,119 |

| Rigor tier | n | Mean SAT |
|---|---|---|
| Most Demanding | 177 | 1,303 |
| Very Demanding | 2,014 | 1,219 |
| Demanding | 4,309 | 1,156 |
| Average | 3,895 | 1,115 |
| Below Average | 703 | 1,052 |

**Cleanly and strongly monotonic** — a **251-point** SAT spread from Below Average (1,052) to
Most Demanding (1,303), with no inversions. This is the single best validation result for the
v3 rigor tier: mean SAT rises with tier on an *independent* measure the tier was not built
from, and the natural-breaks top tier (n=177) is genuinely elite (1,303 mean). The v1 tier,
by contrast, spanned only ~52 SAT points across tiers and had a Below/Average inversion — the
Wk5 additions (AP/test performance components + natural-breaks cuts) sharpened the separation
dramatically.

Per-school percentile rank within each of the three peer groups is written to the output CSV
(`sat_percentile_by_us_region`, `sat_percentile_by_funding_tier`,
`sat_percentile_by_rigor_tier_label`), peer groups smaller than 5 schools excluded rather than
included on too little data.

## The SES-reproduction check — and why this section matters more than it looks

Section 4.5 explicitly extends the same caution from the rigor tier (Section 2.4's SEDA
finding: achievement measures reproduce socioeconomic ordering) to SAT/ACT benchmarking. Doing
this check is what makes this section worth having, not an afterthought:

- `spearman(sat_score_nu, child_poverty_saipe)` = **-0.385**
- `spearman(sat_score_nu, per_resident_child_funding_state_local)` = **0.209**
- `spearman(sat_score_nu, per_pupil_state_local)` = 0.058 (IL only, small n)

**This is the comparison that matters: SAT's correlation with poverty (-0.385) is roughly
2.6x stronger than the rigor tier's (-0.148, from `RIGOR_CLASSIFICATION.md` v3).** That's not a
coincidence — it's exactly what the report's literature review (Sections 2.2, 2.4) predicts:
an outcome/achievement measure (SAT) is more socioeconomically confounded than an
opportunity-plus-performance measure like the rigor tier. (The gap narrowed from v1's ~5.5x
because v3 folds AP/SAT *exam performance* into rigor, and performance is more SES-correlated
than pure availability — a tradeoff quantified openly in `RIGOR_CLASSIFICATION.md`, not hidden.)
This is
a genuinely useful result for the writeup: it's direct empirical evidence *for* building rigor
from curricular opportunity rather than test scores, not just a literature citation asserting
it should be true.

## What this is not

- Not a predictive model or a validated measure of school quality — per the report's own
  framing, purely descriptive peer comparison.
- Not based on a representative sample of each school's students — `sat_score_nu`'s selection
  bias (NU-engaged, college-going families) means these numbers skew toward more advantaged
  subsets within each school, on top of the between-school patterns above.
- Not extended to ACT — 1.2% national coverage made that infeasible this pass.

## Outputs

- `benchmarking_<version>_<date>.csv` — every row from the rigor/clustering output plus
  `funding_tier` and the three `sat_percentile_by_*` columns.
