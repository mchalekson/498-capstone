# Rigor classification — Section 4.1

A transparent, weighted composite index cut into five ordinal tiers — **not** a supervised
classifier trained against historical ground truth (no such labels exist in this project).

**Current version: v4.** Code: `etl/build_rigor_classification.py` (default `--spec v4`).
Run against `modeling_dataset_v4_2026-07-24.csv`.

```
python build_modeling_dataset.py schools_features.csv --version v4
python build_rigor_classification.py modeling_dataset_v4_2026-07-24.csv --version v4
python build_benchmarking.py     rigor_classification_v4_2026-07-24.csv --version v4
python build_rigor_analysis.py   rigor_classification_v4_2026-07-24.csv --version v4
```

Every number below was regenerated from that chain on 2026-07-26 and reproduces the committed
v4 outputs to floating-point tolerance (max |Δrigor_score| = 3.6e-15, identical tier labels).

### Reproducibility status — read this before re-running

`modeling_dataset_v4_2026-07-24.csv` is the **frozen artifact behind every published number**.
Starting the chain one step earlier, from `schools_features.csv`, reproduces the index to
Spearman **ρ = 0.999** but moves **380 of 21,951 schools (1.7%)** across tiers, and shifts the
natural-breaks tier sizes (Below Average 3,896 → 4,042; Most Demanding 295 → 345).

The residual has one cause, now documented rather than silent. `ib_flag_v2` and
`crdc_ib_enrollment` (the rescued IB columns, `docs/IB_RESCUE.md`) are produced in
`combine_schools.py` and land in `schools_combined_enriched_ceeb.csv`, but `build_features.py`
runs off `schools_org_all.csv` and never carries them through — so they entered the original
v4 dataset by a join that was not in the repo. `build_modeling_dataset.attach_ib_v2()` now
performs that join explicitly and reports its match rate (15,910 / 34,392 = 46.3%). It recovers
`ib_flag_v2` exactly, but `ceeb` is the only key the two frames share and it is not unique in
the source (19,084 rows over 16,865 distinct CEEBs), so 73 schools get a CRDC-derived IB
intensity where the frozen file has the binary flag. Refitting the natural breaks on that
slightly different distribution amplifies 73 input differences into 380 tier changes — itself a
demonstration of the cut-point sensitivity documented below.

**Practical guidance:** quote the frozen v4 numbers; if the chain is re-run from
`schools_features.csv`, expect ~1.7% tier movement and re-derive the published tables rather
than mixing. Closing the gap properly means giving the two frames a unique shared key (carrying
`nces_id_12` into the feature frame) — a tracked follow-up, not a blocker.

## Version history

**v3 → v4** adopted the two scenarios in `docs/RIGOR_SCENARIOS.md`. Both are now the default
spec in code (`COMPONENT_SPECS["v4"]`); pass `--spec v3` to reproduce the earlier index.

1. **AP performance re-specified as qualifying density** (scenario B). `ap_performance` switches
   from the raw mean exam score (`ap_score_nu`) to `ap_qualifying_density` — expected exams
   scoring 3+ per student, computed as `ap_tests_taken × P(score ≥ 3)` with P from a normal
   approximation on the school's mean score (within-school SD ≈ 1.2, continuity-corrected cut at
   2.5, winsorized at the 99th percentile). *Why:* a mean rewards gatekeeping — a school that
   sits only its strongest students posts a high mean, while an open-access school is penalised
   for breadth. Density fuses opportunity × performance and follows the College Board's own
   equity-metric logic. The SD ≈ 1.2 figure is a **documented approximation**: the College Board
   does not publish per-school score distributions.
2. **Verified IB folded into CRDC coursework** (scenario A). The standalone `ib` component was
   built on `ib_flag_candidate`, which never cleared `auto_accept` and therefore carried weight 0
   — inert. v4 replaces it with `ib_intensity_v2` (CRDC IB enrollment share, falling back to the
   human-adjudicated binary flag from `docs/IB_RESCUE.md`) inside `crdc_coursework`, where it
   carries real weight. This is what makes IB count at all; 94 previously unscorable schools gain
   a score.

**v2 → v3** added the two performance components in the first place (AP exam performance and
test performance), against a first pass built entirely from availability/participation. That
change was driven by the literature review's most consequential finding — Geiser & Santelices
(2004), §2.2: AP *exam performance*, not course availability, predicts college outcomes — and by
the Week-5 client meeting making the same point independently.

## Component mapping (v4)

| Component | Columns used | Source | Note |
|---|---|---|---|
| AP opportunity | `ap_tests_taken`, `number_of_ap_classes_offered_mid`, `ap_take_rate` | NU org export | offering + engagement |
| **AP performance** | `ap_qualifying_density` | NU org export (derived) | **v4** — replaces raw mean exam score |
| CRDC coursework | `ap_participation`, `dual_enrollment_rate`, **`ib_intensity_v2`** | CRDC + adjudicated IB | **v4** — IB folded in here |
| Test participation | `testtaker_rate`, `sat_participation_nu` | CRDC / NU | who sat the exam |
| Test performance | `sat_score_nu`, `act_composite_il` | NU / ISBE | score, not participation |
| ~~IB (standalone)~~ | `ib_flag_candidate` | IB scraper, fuzzy | retained only for the `ib_included` sensitivity scheme |

Each sub-feature is z-scored, sub-features within a component are averaged over whichever are
present (no imputation), and components are combined with per-row proportional weight
reallocation over whichever are available for that school. A school with none of the
active-weight components gets no score (logged `none`, not defaulted to a middle tier).

### Coverage caveat on the performance components

`ap_qualifying_density` and `sat_score_nu` are NU-recruiting-universe sourced (~31–33% coverage,
skewing affluent); `act_composite_il` is IL-only and thin (~3%). Proportional reallocation means
a performance-informed tier is only produced where performance data exists — uncovered schools
fall back to the opportunity/participation signals. The `availability_only` sensitivity scheme
(below) quantifies exactly how much the added performance signal moves tiers.

## Coverage

**21,951 / 34,392 schools (63.8%) get a score**; 12,441 have none of the five active-weight
components and are correctly left unscored.

| # active components available | schools |
|---|---|
| 0 (unscored) | 12,441 |
| 1 | 1,784 |
| 2 | 8,703 |
| 3 | 1,187 |
| 4 | 2,153 |
| 5 (full coverage) | 8,124 |

Component availability: AP opportunity 31.3%, AP performance 30.5%, CRDC coursework 52.4%,
test participation 62.2%, test performance 32.9%.

(CRDC coursework rises 47.7% → 52.4% versus v3: `ib_intensity_v2` is present for schools where
`ap_participation` and `dual_enrollment_rate` are not.)

## Nominal vs. effective weights

Computed on the 8,124-school full-coverage subset (needed for the covariance terms); composite
variance 0.2630.

| Component | Nominal weight | Effective weight |
|---|---|---|
| AP opportunity | 0.250 | 0.206 |
| **AP performance** | 0.200 | **0.310** |
| CRDC coursework | 0.200 | 0.174 |
| Test participation | 0.150 | 0.080 |
| **Test performance** | 0.200 | 0.230 |

**The two performance components pull the most effective weight** — AP performance in
particular contributes far more variance (0.310) than its assigned 0.20, while test
*participation* contributes almost nothing effective (0.080). This is empirical confirmation
of the literature: performance carries the signal; participation, being correlated with
everything else, is largely absorbed. The gap widened from v3 (0.285 → 0.310): qualifying
density is a higher-variance, more discriminating signal than a mean exam score.

## Sensitivity analysis — alternate weighting schemes vs. the default ("designed")

Spearman is on the continuous score (tiering-independent); "% changed" is on the natural-breaks
tiers (the shipped default):

| Scheme | Spearman rank corr. | Schools changed tier | % changed |
|---|---|---|---|
| `equal` (0.20 each) | 0.995 | 1,563 | 7.1% |
| **`availability_only`** (pre-Wk5 model, no performance) | **0.893** | **6,650** | **30.5%** |
| `performance_heavy` | 0.976 | 4,293 | 19.6% |
| `ib_included` | 0.972 | 9,911 | 45.2% |

**The headline number: adding exam-performance signal moves 30.5% of schools across tiers**
(`availability_only` → `designed`, Spearman 0.89). This is the direct answer to "how much did
the literature-motivated change matter?" — a lot. It is *not* a cosmetic change to the index.
(Under v3 this was 23.3%; the qualifying-density re-specification makes the performance axis
matter more, not less.)

Read the other rows as the reassuring half of the same story: the *weights themselves* are
largely not load-bearing (equal weighting reshuffles only 7.1% of schools, Spearman 0.995).
What matters is which components are in the index at all.

## CRDC-available vs. CRDC-unavailable scenario

Restricted to the 18,807 schools with CRDC signal today, recomputing tiers using only
NU-sourced signal (as if CRDC access were lost):

- 8,933 schools comparable both ways
- Spearman rank correlation: **0.89**
- **44.2% changed tier**

Still the key fragility to surface to the client: losing CRDC access reshuffles ~44% of the
CRDC-covered population's tiers. The dependency has fallen across versions (v1 52.5% → v4 44.2%)
as NU-sourced performance signal was added, but it remains material.

## Poverty / funding correlation with the rigor tier

The check the composite-indicator literature (§4.1) demands — does the tier just reproduce
socioeconomic ordering?

- `spearman(tier, child_poverty_saipe)` = **−0.110**
- `spearman(tier, per_resident_child_funding_state_local)` = **+0.054**
- `spearman(tier, per_pupil_state_local)` = **−0.062**

All weak. Note the trajectory: v1 −0.070 → v3 −0.137 → **v4 −0.110**. Adding performance
signal in v3 increased SES entanglement (expected — AP/SAT scores are more SES-correlated than
raw availability, lit review §2.3, §4.1 predicts exactly this), and the v4 qualifying-density
re-specification bought back roughly half of that increase, because density credits open-access
breadth where a mean score rewarded gatekeeping. At −0.11 the tier is far from a poverty proxy.

For context: the SAT score it is validated against correlates with poverty at −0.385 — **3.5×
stronger** (`BENCHMARKING.md`). The index is substantially less SES-confounded than the outcome
it tracks.

## How a score becomes a tier — the bucket boundaries

The composite gives every scored school a single `rigor_score` (z-score-based, centered ~0;
higher = more rigorous *relative to the average school in the scored population*). Turning that
continuous score into five ordinal tiers is a separate, explicit choice.

**Default: natural breaks (Jenks).** Jenks natural breaks is a 1-D clustering method (here via
1-D k-means, which is equivalent): given the scores and a target of 5 groups, it puts the
cut-points at the natural *gaps* in the distribution — minimizing variance within each tier and
maximizing it between tiers. The boundaries are found by the algorithm, not hand-set. This is
the client's "not equal buckets" request: tier sizes vary and the top tier stays genuinely
small. Actual v4 boundaries:

| Tier | `rigor_score` range | # schools |
|---|---|---|
| Below Average | −3.21 to −0.59 | 3,896 |
| Average | −0.59 to −0.00 | 8,905 |
| Demanding | −0.00 to 0.68 | 6,490 |
| Very Demanding | 0.68 to 1.91 | 2,365 |
| **Most Demanding** | **≥ 1.92** | **295** |

So "Most Demanding" means `rigor_score ≥ 1.92` — roughly 1.9 SD above the average school.
**The top tier tightened sharply from v3 (700 → 295 schools)**: qualifying density has a longer
right tail than a 1–5 mean score (max 10.33 vs. v3's ~4), so the natural-breaks algorithm finds
its highest cut further out. This is a real behavioural change worth flagging — "Most Demanding"
is a materially more exclusive label in v4 than in v3.

**Alternate: quantiles (equal fifths).** Also written to the output (`rigor_tier_*_quantile`):
forces ~4,390 schools per tier. Natural-breaks and quantile tiers agree on only **40.8%** of
scored schools — so the choice is consequential, not cosmetic (and less agreement than v3's 49%,
because the natural-breaks tiers are now more unevenly sized).

**Relative, not absolute — the key caveat.** Both schemes define tiers *relative to our scored
population*, not against a fixed external standard. A school is "Most Demanding" because it sits
at the top of this data, not because it cleared a fixed bar (e.g. "avg AP exam score ≥ 3.5 and
≥ 15 APs offered"). Two implications: (1) the cut-points would shift if re-run on a different
population — and ours is ~64% of schools, skewed toward NU's recruiting universe; (2) an
absolute / fixed-threshold scheme is a real alternative if the client wants a tier that does
*not* move when the population changes. We validate the relative cuts against a measure the
tiers were not built from — mean SAT rises 1,066 → 1,288 across the five tiers with no
inversions (`BENCHMARKING.md`) — evidence the boundaries track real differences even though they
are internally derived.

**Literature backing** (see `literature_review.md` §4.4): natural breaks — Jenks (1967), Fisher
(1958); the relative (norm-referenced) vs. absolute (criterion-referenced) choice — Glaser
(1963), Cizek & Bunch (2007); the composite-indicator framework the tiering sits inside — Nardo
et al. (2008, OECD/JRC handbook). The preference for natural breaks over equal quantiles is
grounded in Reardon/SEDA's caution (§4.1) against ranking schools that "differ only slightly."

## What this is not

- **Tier cut-points are relative, not absolute** — see "How a score becomes a tier" above. The
  default is natural breaks (Jenks); quantiles are provided as an alternate (`rigor_tier_*_quantile`).
  Neither anchors to a fixed external standard, and that is a deliberate open choice for the
  client, not settled.
- Not validated against any external rigor measure (none exists in this project).
- Naming: the tiers keep NU's own counselor vocabulary (Below Average … Most Demanding), but
  the model measures **opportunity + performance structure at the institution level**, not a
  student outcome — state this in Methods (lit review §2.2, §3.3 single-score lesson).
- The `ap_qualifying_density` normal approximation (SD ≈ 1.2) is an assumption, not a measured
  distribution. Per-course or per-school AP score distributions from the client would replace it
  with a real one — this is a standing data ask.

## Outputs

- `rigor_classification_v4_2026-07-24.csv` — every modeling-set row plus `rigor_score`,
  `rigor_tier_num`, `rigor_tier_label`, `rigor_n_components_used`,
  `rigor_components_available`, `rigor_weighting_scheme`, `rigor_component_spec`.
- `rigor_sensitivity_v4_2026-07-24.csv` — the alternate-scheme comparison table above.
- Downstream, both regenerated on v4: `benchmarking_v4_2026-07-26.csv` (`BENCHMARKING.md`),
  `rigor_analysis_v4_2026-07-26.csv` (`RIGOR_ANALYSIS.md`).
