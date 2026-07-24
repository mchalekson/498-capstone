# Rigor classification — Section 4.1

A transparent, weighted composite index cut into five ordinal tiers — **not** a supervised
classifier trained against historical ground truth (no such labels exist in this project).

Code: `etl/build_rigor_classification.py`. Run against `modeling_dataset_v3_2026-07-24.csv`.

## What changed in the Week-5 revision (v3)

The first pass built rigor entirely from **availability/participation** signals (AP counts,
CRDC coursework flags, who sat the SAT). The literature review's single most consequential
finding pushes directly against that: Geiser & Santelices (2004), lit review §2.2 — AP
*exam performance*, not course availability, is what predicts college outcomes; availability
is the weakest input. The Week-5 client meeting made the same point independently ("AP scores",
"standardized testing to compare schools", "of 25 offered they took 5").

Two changes address it, both drawing on data (`nu_avg_ap_score`, ACT scores, AP take-rate)
that already existed in the source export but had never been carried into the modeling set:

1. **Added an AP-performance component** (`ap_score_nu`, the avg AP exam score 1–5).
2. **Added a test-performance component** (`sat_score_nu`, `act_composite_il`) — score signal,
   not just participation.
3. Renamed the old `ap` component to **`ap_opportunity`** and folded in the new **`ap_take_rate`**
   (tests taken / tests offered) — naming the opportunity-vs-performance distinction explicitly,
   as the lit review (§2.2, §3.3) asks.

## Component mapping

| Component | Columns used | Source | Note |
|---|---|---|---|
| AP opportunity | `ap_tests_taken`, `number_of_ap_classes_offered_mid`, `ap_take_rate` | NU org export | offering + engagement |
| **AP performance** | `ap_score_nu` | NU org export | **added Wk5** — the literature-critical signal |
| IB | `ib_flag_candidate` | IB scraper, fuzzy | excluded, weight 0 |
| CRDC coursework | `ap_participation`, `dual_enrollment_rate` | CRDC | |
| Test participation | `testtaker_rate`, `sat_participation_nu` | CRDC / NU | who sat the exam |
| **Test performance** | `sat_score_nu`, `act_composite_il` | NU / ISBE | **added Wk5** — score, not participation |

Each sub-feature is z-scored, sub-features within a component are averaged over whichever are
present (no imputation), and components are combined with per-row proportional weight
reallocation over whichever are available for that school. A school with none of the
active-weight components gets no score (logged `none`, not defaulted to a middle tier).

**IB stays excluded from the default weighting** (weight 0) per the report caveat — no IB
match clears `auto_accept`. Included only in the `ib_included` sensitivity scenario. (Note the
separate `ib_flag_v2` rescue in `docs/IB_RESCUE.md` is a candidate to replace `ib_flag_candidate`
here in a later pass — not yet wired into the default weighting.)

### Coverage caveat on the performance components

`ap_score_nu`, `sat_score_nu` are NU-recruiting-universe sourced (~31–33% coverage, skewing
affluent); `act_composite_il` is IL-only and thin (~3%). Proportional reallocation means a
performance-informed tier is only produced where performance data exists — uncovered schools
fall back to the opportunity/participation signals. The `availability_only` sensitivity scheme
(below) quantifies exactly how much the added performance signal moves tiers.

## Coverage

21,857 / 34,392 schools (64%) get a score; 12,535 have none of the five active-weight
components and are correctly left unscored.

| # active components available | schools |
|---|---|
| 0 (unscored) | 12,535 |
| 1 | 2,506 |
| 2 | 7,965 |
| 3 | 1,139 |
| 4 | 2,711 |
| 5 (full coverage) | 7,536 |

Component availability: AP opportunity 31.3%, AP performance 30.5%, CRDC coursework 47.7%,
test participation 62.2%, test performance 32.9%.

## Nominal vs. effective weights

Computed on the 7,536-school full-coverage subset (needed for the covariance terms):

| Component | Nominal weight | Effective weight |
|---|---|---|
| AP opportunity | 0.250 | 0.195 |
| **AP performance** | 0.200 | **0.285** |
| CRDC coursework | 0.200 | 0.206 |
| Test participation | 0.150 | 0.074 |
| **Test performance** | 0.200 | 0.241 |

**The two performance components pull the most effective weight** — AP performance in
particular contributes far more variance (0.285) than its assigned 0.20, while test
*participation* contributes almost nothing effective (0.074). This is empirical confirmation
of the literature: performance carries the signal; participation, being correlated with
everything else, is largely absorbed.

## Sensitivity analysis — alternate weighting schemes vs. the default ("designed")

| Scheme | Spearman rank corr. | Schools changed tier | % changed |
|---|---|---|---|
| `equal` (0.20 each) | 0.995 | 2,134 | 9.8% |
| **`availability_only`** (pre-Wk5 model, no performance) | **0.879** | **6,497** | **29.9%** |
| `performance_heavy` | 0.972 | 4,587 | 21.0% |
| `ib_included` | 0.971 | 9,197 | 42.1% |

**The headline number: adding exam-performance signal moves ~30% of schools across tiers**
(`availability_only` → `designed`, Spearman 0.88). This is the direct answer to "how much did
the literature-motivated change matter?" — a lot. It is *not* a cosmetic change to the index.

## CRDC-available vs. CRDC-unavailable scenario

Restricted to the 18,807 schools with CRDC signal today, recomputing tiers using only
NU-sourced signal (as if CRDC access were lost):

- 8,933 schools comparable both ways
- Spearman rank correlation: **0.88**
- **39.3% changed tier**

Still the key fragility to surface to the client: losing CRDC access reshuffles ~40% of the
CRDC-covered population's tiers. (Adding the NU-sourced performance components softened this
from the first pass's 52.5% — the model now leans less exclusively on CRDC — but the
dependency is still material.)

## Poverty / funding correlation with the rigor tier

The check the composite-indicator literature (§4.1) demands — does the tier just reproduce
socioeconomic ordering?

- `spearman(tier, child_poverty_saipe)` = **-0.148**
- `spearman(tier, per_resident_child_funding_state_local)` = **0.091**
- `spearman(tier, per_pupil_state_local)` = **-0.067**

All still weak. The poverty correlation strengthened from the first pass's -0.070 to -0.148 —
expected, since the added performance signals (AP/SAT scores) are more SES-correlated than raw
availability (lit review §2.3, §4.1 predicts exactly this). But at -0.15 the tier is still far
from being a poverty proxy. Worth stating honestly: the literature-recommended change bought
real predictive signal at the cost of a small, quantified increase in SES entanglement.

## What this is not

- **Tier cut-points are quintiles** (equal buckets: ~4,371 schools each). The Week-5 client
  note flagged that real institution rigor is *"not broken into equal buckets"* — so quintiles
  are a transparent default, not a claim about the true distribution. Natural-breaks (Jenks) or
  fixed score thresholds are a defensible follow-up; this is called out as an open choice, not
  settled.
- Not validated against any external rigor measure (none exists in this project).
- Naming: the tiers keep NU's own counselor vocabulary (Below Average … Most Demanding), but
  the model measures **opportunity + performance structure at the institution level**, not a
  student outcome — state this in Methods (lit review §2.2, §3.3 single-score lesson).

## Outputs

- `rigor_classification_v3_2026-07-24.csv` — every modeling-set row plus `rigor_score`,
  `rigor_tier_num`, `rigor_tier_label`, `rigor_n_components_used`,
  `rigor_components_available`, `rigor_weighting_scheme`.
- `rigor_sensitivity_v3_2026-07-24.csv` — the alternate-scheme comparison table above.
