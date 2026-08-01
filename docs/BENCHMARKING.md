# Performance benchmarking — first pass (Section 4.5)

Code: `etl/build_benchmarking.py`. Run against `rigor_classification_v4_2026-07-24.csv`
(regenerated on v4 2026-07-26 → `benchmarking_v4_2026-07-26.csv`).

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
| Most Demanding | 89 | 1,288 |
| Very Demanding | 1,335 | 1,234 |
| Demanding | 3,785 | 1,168 |
| Average | 4,831 | 1,126 |
| Below Average | 1,058 | 1,066 |

**Cleanly and strongly monotonic** — a **222-point** SAT spread from Below Average (1,066) to
Most Demanding (1,288), with no inversions. This is the single best validation result for the
rigor tier: mean SAT rises with tier on an *independent* measure the tier was not built
from, and the natural-breaks top tier (n=89) is genuinely elite (1,288 mean). The v1 tier,
by contrast, spanned only ~52 SAT points across tiers and had a Below/Average inversion — the
Wk5 additions (AP/test performance components + natural-breaks cuts) sharpened the separation
dramatically.

Versus v3 (which spanned 1,052 → 1,303, 251 points, top tier n=177), v4 is marginally less
separated at the extremes but rests on a much tighter top tier (295 schools vs. 700, of which
89 have SAT). The step sizes are also more even across the middle of the distribution
(1,066 → 1,126 → 1,168 → 1,234 → 1,288), rather than v3's flatter middle.

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
3.5x stronger than the rigor tier's (-0.110, from `RIGOR_CLASSIFICATION.md` v4).** That's not a
coincidence — it's exactly what the report's literature review (Sections 2.2, 2.4) predicts:
an outcome/achievement measure (SAT) is more socioeconomically confounded than an
opportunity-plus-performance measure like the rigor tier. (The ratio moved v1 ~5.5x → v3 2.8x →
v4 3.5x: v3 folded AP/SAT *exam performance* into rigor and performance is more SES-correlated
than pure availability, then v4's qualifying-density re-specification bought back about half of
that — a tradeoff quantified openly in `RIGOR_CLASSIFICATION.md`, not hidden.)
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
